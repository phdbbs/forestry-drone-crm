from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import logging
import os

from app.errors import fail

db = SQLAlchemy()
logger = logging.getLogger('crm')

# SQLite 在文件/锁/磁盘层面出错时，池中连接已经不可用。
# 命中这些关键字说明是「连接已坏」而非「SQL 语法/约束问题」，应丢弃整个连接池重连。
_IO_ERROR_MARKERS = (
    'disk i/o error',
    'unable to open database file',
    'database disk image is malformed',
    # 检测到残留热日志、需要回滚却写不进去时的报错。
    # 曾经正是因为它不在这份名单里，导致连接池永不重建、服务只能人工重启。
    'attempt to write a readonly database',
    'readonly database',
    'database is locked',
    'database table is locked',
)

_io_recovery_installed = False


def _is_pool_poisoning_error(exc):
    """判断异常是否意味着「池中连接已坏、必须整个重建」。

    除了关键字匹配，凡是 sqlite3 的 OperationalError / DatabaseError 都算：
    它们都由文件、锁或磁盘层面引起，与业务 SQL 无关，重建池是无害的
    （最坏只是丢弃几个尚可用的连接，代价远小于让服务持续 500）。
    关键字匹配保留是为了兼容非 sqlite3 原生异常（如经过包装的错误）。
    """
    import sqlite3
    if isinstance(exc, (sqlite3.OperationalError, sqlite3.DatabaseError)):
        return True
    msg = str(exc).lower()
    return any(marker in msg for marker in _IO_ERROR_MARKERS)


def _install_io_error_recovery():
    """连接池坏掉后自动丢弃重建，使服务无需重启即可恢复。

    背景：数据库一旦出现热日志残留、磁盘瞬时抖动或锁异常，池中已建立的连接
    会进入不可用状态（例如 sqlite3.OperationalError: attempt to write a readonly
    database —— 它表示连接检测到热日志需要回滚、却写不进主库）。失效的是
    「池中的连接」本身，文件随后往往已经恢复正常，因此此后每个请求仍会继续失败，
    只有重启进程才能恢复，表象就是前端「数据全部消失」。

    这里在引擎层捕获这类错误并 dispose 连接池，下一个请求重新建连即可正常服务。

    Engine 上的监听是全局的，重复注册会叠加回调，故用模块级标志确保只装一次
    （测试会反复调用 create_app）。
    """
    global _io_recovery_installed
    if _io_recovery_installed:
        return
    _io_recovery_installed = True

    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, 'handle_error')
    def _drop_pool_on_io_error(exception_context):
        if _is_pool_poisoning_error(exception_context.original_exception):
            try:
                exception_context.engine.dispose()
                logger.warning(
                    'SQLite 连接异常，已丢弃连接池等待下次请求重建: %s',
                    exception_context.original_exception,
                )
            except Exception:
                # 自愈失败不应掩盖原始异常
                pass


def _heal_sqlite_on_startup(db_path):
    """启动时用一次性裸连接清理残留热日志，并把数据库切到 WAL 模式。

    为什么必须放在 SQLAlchemy 建池之前：
    服务进程或采集线程若在写事务中途被强杀（会话回收、kill、崩溃），DELETE 模式会
    留下「热日志」（crm.db-journal）。此后任何连接打开数据库，都要先把日志里的
    原始页回滚写回主库才能使用。若让池里的连接去做这件事，一旦回滚失败，坏连接
    就会被反复复用，导致全部接口 500 —— 表象正是「数据全部消失」，且必须人工干预
    才能恢复（此前两次故障都是这个机理）。这里用独立连接先完成回滚，
    异常只记录、不阻断启动，保证进入连接池的一定是干净状态。

    切到 WAL 之后：崩溃恢复不再依赖「把原始页写回主库」这种脆弱操作，
    且读写互不阻塞 —— 采集线程长时间写入时，前端读取不会再被拖垮。
    """
    import sqlite3
    if not os.path.exists(db_path):
        return
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=15)
        # 先做一次读取：若存在热日志，SQLite 会在此刻自动完成回滚（这正是目的）
        conn.execute('SELECT count(*) FROM sqlite_master').fetchone()
        conn.commit()
        mode = conn.execute('PRAGMA journal_mode=WAL').fetchone()[0]
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.commit()
        logger.info('SQLite 启动自愈完成：journal_mode=%s', mode)
    except Exception as e:
        # 自愈失败不阻断启动：应用照常拉起，由池层自愈兜底
        logger.warning('SQLite 启动自愈未完成（不阻断启动）: %s', e)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _configure_file_logging(app):
    """把服务日志落盘，便于故障回溯。

    此前日志只进终端：进程一旦被回收，故障现场（500 的真实堆栈）就无从查证，
    排查只能靠猜。这里追加一个轮转文件 handler，日志写到 instance/crm.log。
    """
    from logging.handlers import RotatingFileHandler
    log_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'crm.log'
    )
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        # 测试会反复 create_app，避免重复挂载同一文件 handler
        handler = None
        for h in app.logger.handlers:
            if isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '') == log_path:
                handler = h
                break
        if handler is None:
            handler = RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding='utf-8')
            handler.setFormatter(logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            ))
            handler.setLevel(logging.INFO)
            app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        # 模块级 logger（启动自愈、连接池重建等诊断信息）默认会被 root 的
        # WARNING 级别拦掉，导致 crm.log 一直是空的；这里显式接上同一个 handler
        if handler not in logger.handlers:
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        # 已有专用 handler，关掉向上传播，避免同一条日志被 root 重复输出
        logger.propagate = False
    except Exception as e:
        logger.warning('日志文件初始化失败（不影响服务）: %s', e)


def _configure_session(app):
    from datetime import timedelta
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        # Lax：顶层导航带 cookie（本机 http 访问够用），跨站 POST 不带，
        # 因而无需额外 CSRF token。将来上 HTTPS 再收紧为 Secure + Strict。
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )


# 登录前必须可访问，否则永远无法完成登录（登出幂等，未登录调用也不该报错）
_AUTH_EXEMPT = {'auth.status', 'auth.login', 'auth.setup', 'auth.logout'}

# 管理员专属：系统设置（AI 口令/采集目标/定时任务/备份）、技能、采集日志、账号管理、操作日志。
# 业务数据（线索/客户/联系人/商机/联络/看板）全员共享，不区分账号归属。
# 用路径前缀而不是逐个端点加装饰器：新增接口只要落在这些前缀下就默认受限。
# /api/track 故意不在这个名单里：埋点每个账号都要上报，普通销售点菜单不该吃 403。
_ADMIN_PREFIXES = ('/api/config', '/api/skills', '/api/crawl/logs', '/api/error-types',
                   '/api/users', '/api/news/collect-all', '/api/audit')
# 只限制写操作：阶段列表所有账号都要用来渲染商机页，改动配置才归管理员
_ADMIN_WRITE_PREFIXES = ('/api/stages',)
_WRITE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')


def _is_admin_only_request(request):
    path = request.path
    if path.startswith(_ADMIN_PREFIXES):
        return True
    return request.method in _WRITE_METHODS and path.startswith(_ADMIN_WRITE_PREFIXES)


def _install_auth_gate(app):
    """未登录拦截所有 /api/*，并区分管理员专属接口。

    此前 93 个端点全部匿名可读写：DELETE、改配置、触发采集都不需要身份，
    而服务监听 0.0.0.0，同网段任意设备都能直接操作数据。
    这里统一加一道闸，而不是逐个端点装饰，避免新接口默认漏保护。
    """
    from flask import request

    @app.before_request
    def _require_login():
        if app.config.get('AUTH_DISABLED'):
            return None
        if not request.path.startswith('/api/'):
            return None
        if request.method == 'OPTIONS':
            return None
        if request.endpoint in _AUTH_EXEMPT:
            return None
        from app.services.auth import current_user, is_admin
        user = current_user()
        if user is None:
            return fail("请先登录", 401)
        if _is_admin_only_request(request) and not is_admin(user):
            return fail("需要管理员权限", 403)


def _load_secret_key(instance_dir):
    """会话签名密钥：优先环境变量，其次读已落盘的随机密钥，都没有则新生成一个。

    这里原先是写死的默认值。启用会话鉴权后写死默认值意味着任何拿到源码的人
    都能伪造合法 cookie，口令等于白设，所以必须随机化并持久化
    （持久化才不会每次重启都把已登录设备踢下线）。
    """
    env = os.environ.get('CRM_SECRET_KEY')
    if env:
        return env
    path = os.path.join(instance_dir, 'secret_key')
    try:
        with open(path) as f:
            secret = f.read().strip()
        if secret:
            return secret
    except OSError:
        pass
    import secrets
    secret = secrets.token_hex(32)
    try:
        # 0600：仅当前用户可读，避免密钥被同机其他账号取走
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(secret)
    except OSError as e:
        logger.warning('会话密钥未能持久化到 %s（仅本次运行有效）: %s', path, e)
    return secret


def create_app(config=None):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    instance_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance'
    )
    app.config['SECRET_KEY'] = _load_secret_key(instance_dir)
    db_path = os.path.join(instance_dir, 'crm.db')
    # SQLite 不会自动创建父目录：全新环境首次启动前必须确保 instance/ 存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # 数据库文件位于网络卷（SMB）上时，挂载一旦瞬时抖动，
    # 连接池中已持有的连接会失效并抛出 sqlite3.OperationalError: disk I/O error；
    # 由于失效的是池中连接本身，此后所有请求都会持续失败，只能重启进程才恢复。
    # 下面的配置让连接池能自愈，无需重启。
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        # 取用连接前先做一次轻量探测，失效连接会被丢弃并重建
        'pool_pre_ping': True,
        # 限制连接最长存活时间：坏连接最多存活 1 分钟就会被换掉，
        # 而不是像原先那样躺 5 分钟继续污染每个请求
        'pool_recycle': 60,
        # SQLite 是单文件库，连接数没有必要开大；池子小一点，
        # 持有可能失效的文件句柄也更少
        'pool_size': 5,
        'max_overflow': 5,
        'pool_timeout': 30,
        # 网络卷/磁盘锁竞争比内存慢，放宽等待时间，避免瞬时竞争直接报 locked
        'connect_args': {'timeout': 30},
    }
    _configure_session(app)
    # 鉴权默认开启；测试通过 config 里的 AUTH_DISABLED 显式关闭
    app.config['AUTH_DISABLED'] = os.environ.get('CRM_AUTH_DISABLED') == '1'
    if config:
        app.config.update(config)
    cors_origins = os.environ.get('CRM_CORS_ORIGINS', '')
    if cors_origins:
        try:
            from flask_cors import CORS
            CORS(app, origins=[o.strip() for o in cors_origins.split(',') if o.strip()])
        except ImportError:
            pass
    db.init_app(app)
    from app.services.softdelete import install as install_soft_delete_filter
    install_soft_delete_filter()
    _configure_file_logging(app)
    # 必须在建池/建表之前完成：清掉可能残留的热日志并切换 WAL。
    # 顺序错了就失去意义 —— 坏状态会先被连接池持有，之后难以清除。
    _heal_sqlite_on_startup(db_path)
    _install_io_error_recovery()
    _register_error_handlers(app)
    from app.routes import api
    app.register_blueprint(api, url_prefix='/api')
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    from app.routes.users import users_bp
    app.register_blueprint(users_bp, url_prefix='/api')
    from app.routes.audit import audit_bp
    app.register_blueprint(audit_bp, url_prefix='/api')
    _install_auth_gate(app)
    from app.services.audit import install_audit
    install_audit(app)

    def _missing_dist_response():
        # v3.0 内联 SPA（static/index.html）已下线归档至 deprecated/，
        # Vue 构建产物是唯一入口；缺失时不再静默回退旧原型，而是给出明确修复指引。
        return fail("前端构建产物缺失", 503, 'dist_missing',
                    detail="请在 frontend/ 目录执行 npm install && npm run build，产物会输出到 app/static/dist/")

    @app.route('/')
    def serve_index():
        from flask import send_from_directory
        import os
        # 返回 Vue 构建产物 dist/index.html（唯一入口）
        dist_index = os.path.join(app.static_folder, 'dist', 'index.html')
        if os.path.isfile(dist_index):
            return send_from_directory(os.path.join(app.static_folder, 'dist'), 'index.html')
        return _missing_dist_response()

    @app.route('/<path:path>')
    def serve_spa(path):
        from flask import send_from_directory
        import os
        # 未注册的 /api/* 必须返回 JSON 404，不能被 SPA 兜底吞成 200 HTML，
        # 否则前端 fetch 拿到 HTML 会解析失败、掩盖接口拼写错误。
        # 该兜底路由同时允许 GET，会抢在 Flask 的方法仲裁之前命中，
        # 因此这里要主动区分"路径不存在(404)"与"路径存在但方法不符(405)"。
        if path == 'api' or path.startswith('api/'):
            # 该兜底路由自身允许 GET，会抢在 Flask 的方法仲裁之前命中，
            # 因此要主动区分"路径不存在(404)"与"路径存在但方法不符(405)"
            adapter = app.url_map.bind('localhost')
            for method in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE'):
                try:
                    endpoint, _ = adapter.match('/' + path, method=method)
                except Exception:
                    continue
                if endpoint != 'serve_spa':
                    return fail("请求方法不被允许", 405)
            return fail("接口不存在", 404)
        # 依次查找 dist/ 与 static/ 下的静态文件；都未命中则回退 SPA 入口
        for base in (os.path.join(app.static_folder, 'dist'), app.static_folder):
            file_path = os.path.join(base, path)
            if os.path.isfile(file_path):
                return send_from_directory(base, path)
        # 静态资源（尤其 /assets/*.js 分块）找不到时必须返回真 404，
        # 绝不能兜底成 index.html：HTML 顶替 JS 会让浏览器动态 import 抛出
        # 难以定位的 MIME/解析错误，前端"点击菜单没反应"多源于此。
        if path.startswith('assets/') or path.endswith(('.js', '.css', '.svg', '.png', '.ico', '.woff', '.woff2')):
            return fail("静态资源不存在", 404, 'asset_not_found', detail=path)
        dist_index = os.path.join(app.static_folder, 'dist', 'index.html')
        if os.path.isfile(dist_index):
            return send_from_directory(os.path.join(app.static_folder, 'dist'), 'index.html')
        return _missing_dist_response()
    with app.app_context():
        _enable_sqlite_foreign_keys()
        db.create_all()
        _migrate_db()
        # 上次进程若在采集中途退出，日志会永远停在 running；启动时补记为中断
        try:
            from app.services.crawl_log import mark_stale_logs
            mark_stale_logs()
        except Exception as e:
            logger.warning('清理残留采集日志失败（不影响服务）: %s', e)
        from app.services.seed import seed_if_empty
        seed_if_empty()
        # 补归档：凌晨那次定时任务可能没跑成（首次上线、服务停机、机器休眠），
        # 不补的话设置页的汇总表会缺一截，看起来就像功能压根没生效。
        try:
            from app.services.audit import ensure_recent_summaries
            ensure_recent_summaries()
        except Exception as e:
            logger.warning('操作日志汇总补齐失败（不影响服务）: %s', e)

    # 定时任务（采集/备份）在生产启动时开启；测试环境由 CRM_DISABLE_SCHEDULER=1 关闭
    from app.services.scheduler import init_scheduler
    init_scheduler(app)
    return app


def _enable_sqlite_foreign_keys():
    """配置每个 SQLite 连接：外键校验 + WAL + 锁等待。

    WAL 是这里最关键的一项。默认的 DELETE 模式下一个写事务会阻塞其他连接读取，
    采集线程持续写入时前端就会大面积超时/报错；WAL 下读写互不阻塞，
    且崩溃后的恢复由 -wal 文件自动完成，不再依赖脆弱的「回滚主库」操作。
    """
    from sqlalchemy import event
    if db.engine.dialect.name != 'sqlite':
        return

    @event.listens_for(db.engine, 'connect')
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            # SQLite 默认不校验外键，开启后杜绝 customer_id/contact_id 等悬空引用
            cursor.execute('PRAGMA foreign_keys=ON')
            # 崩溃后自动恢复；读写互不阻塞
            cursor.execute('PRAGMA journal_mode=WAL')
            # WAL 下 NORMAL 兼顾安全与写入开销（FULL 会让每次提交都 fsync）
            cursor.execute('PRAGMA synchronous=NORMAL')
            # 锁等待：瞬时竞争时排队而不是立刻抛 database is locked
            cursor.execute('PRAGMA busy_timeout=30000')
            cursor.close()
        except Exception:
            # 连接级 PRAGMA 失败不应阻断连接建立（例如库文件只读时）
            pass

def _migrate_db():
    """Add new columns for v3.0 to existing databases."""
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    # 逻辑删除：所有业务表补 is_deleted。NOT NULL + DEFAULT 保证既有行落到 0（未删除），
    # 也让读取过滤器可以用确定的 is_deleted = 0 比较，不必处理 NULL。
    soft_delete_tables = (
        'customers', 'customer_news', 'contact_news', 'crawl_logs', 'leads',
        'opportunities', 'opportunity_stages', 'stage_records', 'contacts',
        'activities', 'kanban_boards', 'kanban_columns', 'kanban_cards',
        'skills', 'followups', 'lead_operations',
    )
    migrations = [
        ('leads', 'match_score', 'INTEGER DEFAULT 0'),
        ('leads', 'assignee', "VARCHAR(50) DEFAULT ''"),
        ('leads', 'contact_name', "VARCHAR(100) DEFAULT ''"),
        ('leads', 'contact_phone', "VARCHAR(100) DEFAULT ''"),
        ('leads', 'address', "VARCHAR(300) DEFAULT ''"),
        ('opportunities', 'probability', 'INTEGER DEFAULT 20'),
        ('opportunities', 'expected_close', 'DATETIME'),
        ('opportunities', 'source_url', 'VARCHAR(1000)'),
        ('contacts', 'role', "VARCHAR(50) DEFAULT ''"),
        ('contacts', 'tags', "TEXT DEFAULT ''"),
        ('contacts', 'avatar', "VARCHAR(10) DEFAULT ''"),
        ('customer_news', 'source_name', "VARCHAR(200) DEFAULT ''"),
        ('customer_news', 'event_time', 'DATETIME'),
        ('leads', 'bid_type', "VARCHAR(50) DEFAULT ''"),
        ('leads', 'winner', "VARCHAR(200) DEFAULT ''"),
        ('leads', 'serial_no', "VARCHAR(20) DEFAULT ''"),
        ('leads', 'full_text', 'TEXT'),
        ('leads', 'reason', "VARCHAR(300) DEFAULT ''"),
        # 采集日志：完整上下文 + 已分类报错（详见 app/services/crawl_log.py）
        ('crawl_logs', 'keywords', "VARCHAR(500) DEFAULT ''"),
        ('crawl_logs', 'range_start', "VARCHAR(30) DEFAULT ''"),
        ('crawl_logs', 'range_end', "VARCHAR(30) DEFAULT ''"),
        ('crawl_logs', 'duration_ms', 'INTEGER DEFAULT 0'),
        ('crawl_logs', 'error_types', "TEXT DEFAULT ''"),
        ('crawl_logs', 'error_detail', "TEXT DEFAULT ''"),
        # 操作留痕：历史行无法追溯操作人，统一补成「系统」而不是留空，
        # 这样列表里的「操作用户」列永远有值，前端不必再判空。
        ('activities', 'operator', "VARCHAR(50) NOT NULL DEFAULT '系统'"),
        ('followups', 'operator', "VARCHAR(50) NOT NULL DEFAULT '系统'"),
        ('followups', 'executed_by', "VARCHAR(50) DEFAULT ''"),
        ('contacts', 'lead_id', 'INTEGER'),
    ] + [(t, 'is_deleted', 'BOOLEAN NOT NULL DEFAULT 0') for t in soft_delete_tables]
    with db.engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                cols = [c['name'] for c in inspector.get_columns(table)]
                if column not in cols:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
            except Exception:
                pass
        # 索引：db.create_all() 只会为"新建表"建索引，已存在的旧表必须显式补建。
        # 命名与 SQLAlchemy index=True 自动生成的 ix_<table>_<column> 保持一致，
        # 保证新旧库最终状态相同。均为高频查询列（线索列表过滤/排序、采集查重、
        # 外键关联、看板/日程时间轴）。
        for stmt in [
            "CREATE INDEX IF NOT EXISTS ix_customers_name ON customers (name)",
            "CREATE INDEX IF NOT EXISTS ix_customer_news_customer_id ON customer_news (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_contact_news_contact_id ON contact_news (contact_id)",
            "CREATE INDEX IF NOT EXISTS ix_contact_news_customer_id ON contact_news (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_leads_match_level ON leads (match_level)",
            "CREATE INDEX IF NOT EXISTS ix_leads_source_url ON leads (source_url)",
            "CREATE INDEX IF NOT EXISTS ix_leads_customer_id ON leads (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_leads_created_at ON leads (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_leads_status_created_at ON leads (status, created_at)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_serial_no ON leads (serial_no) WHERE serial_no != ''",
            "CREATE INDEX IF NOT EXISTS ix_opportunities_lead_id ON opportunities (lead_id)",
            "CREATE INDEX IF NOT EXISTS ix_opportunities_customer_id ON opportunities (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_opportunities_contact_id ON opportunities (contact_id)",
            "CREATE INDEX IF NOT EXISTS ix_opportunities_current_stage ON opportunities (current_stage)",
            "CREATE INDEX IF NOT EXISTS ix_opportunities_created_at ON opportunities (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_stage_records_opportunity_id ON stage_records (opportunity_id)",
            "CREATE INDEX IF NOT EXISTS ix_contacts_customer_id ON contacts (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_contacts_lead_id ON contacts (lead_id)",
            "CREATE INDEX IF NOT EXISTS ix_lead_operations_lead_id ON lead_operations (lead_id)",
            "CREATE INDEX IF NOT EXISTS ix_lead_operations_created_at ON lead_operations (created_at)",
            "CREATE INDEX IF NOT EXISTS ix_activities_customer_id ON activities (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_activities_contact_id ON activities (contact_id)",
            "CREATE INDEX IF NOT EXISTS ix_activities_opportunity_id ON activities (opportunity_id)",
            "CREATE INDEX IF NOT EXISTS ix_activities_lead_id ON activities (lead_id)",
            "CREATE INDEX IF NOT EXISTS ix_activities_activity_time ON activities (activity_time)",
            "CREATE INDEX IF NOT EXISTS ix_kanban_columns_board_id ON kanban_columns (board_id)",
            "CREATE INDEX IF NOT EXISTS ix_kanban_cards_column_id ON kanban_cards (column_id)",
            "CREATE INDEX IF NOT EXISTS ix_followups_contact_id ON followups (contact_id)",
            "CREATE INDEX IF NOT EXISTS ix_followups_customer_id ON followups (customer_id)",
            "CREATE INDEX IF NOT EXISTS ix_followups_opportunity_id ON followups (opportunity_id)",
            "CREATE INDEX IF NOT EXISTS ix_followups_lead_id ON followups (lead_id)",
            "CREATE INDEX IF NOT EXISTS ix_followups_plan_date ON followups (plan_date)",
            # 用户名唯一只约束未删除账号：账号是逻辑删除的，硬唯一会让删掉的
            # 账号永远占住用户名。users 表由 create_all 建，这里兜底补建。
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username ON users (username) WHERE is_deleted = 0",
        ]:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass
        conn.commit()

def _register_error_handlers(app):
    from sqlalchemy.exc import IntegrityError
    from app.errors import http_error

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(415)
    def handle_http_error(e):
        # 统一形状由 http_error 负责：abort(400, description=...) 的业务提示优先，
        # 若仍是 Werkzeug 的类默认描述（英文），则替换为中文兜底文案
        return http_error(e)

    @app.errorhandler(KeyError)
    def handle_missing_param(e):
        db.session.rollback()
        # KeyError 的 str() 带引号且只有字段名，直接拼进文案会像内部报错
        key = str((e.args or [''])[0]).strip("'\"")
        return fail(f"请求参数有误: {key}" if key else "请求参数有误", 400, 'missing_param')

    @app.errorhandler(ValueError)
    def handle_bad_value(e):
        db.session.rollback()
        # 服务层用 ValueError 承载业务校验文案（如「口令至少 6 位」），可直接给用户看
        return fail(str(e) or "请求参数有误", 400, 'bad_param')

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        db.session.rollback()
        raw = str(getattr(e, 'orig', e) or e).upper()
        if 'FOREIGN KEY' in raw:
            return fail("关联对象不存在，请检查所选客户/联系人/商机等是否有效", 400, 'bad_reference')
        if 'UNIQUE' in raw:
            return fail("数据已存在，请勿重复提交", 400, 'duplicate')
        return fail("数据完整性校验失败", 400, 'integrity_error')

    @app.errorhandler(500)
    def handle_server_error(e):
        # rollback 自身也可能因连接已坏而失败，不能让清理动作掩盖原始错误
        try:
            db.session.rollback()
        except Exception:
            pass
        import traceback
        orig = getattr(e, 'original_exception', None) or e
        try:
            detail = ''.join(traceback.format_exception(type(orig), orig, orig.__traceback__))
        except Exception:
            detail = str(orig)
        # 落盘完整堆栈：接口只返回通用文案，不记日志就等于故障无法回溯
        app.logger.error('服务器内部错误: %s\n%s', orig, detail)
        return fail("服务器内部错误", 500)
