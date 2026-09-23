from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import logging
import os

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


def create_app(config=None):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('CRM_SECRET_KEY', 'forest-drone-crm-2026')
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'crm.db')
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
    _configure_file_logging(app)
    # 必须在建池/建表之前完成：清掉可能残留的热日志并切换 WAL。
    # 顺序错了就失去意义 —— 坏状态会先被连接池持有，之后难以清除。
    _heal_sqlite_on_startup(db_path)
    _install_io_error_recovery()
    _register_error_handlers(app)
    from app.routes import api
    app.register_blueprint(api, url_prefix='/api')

    @app.route('/')
    def serve_index():
        from flask import send_from_directory
        import os
        # 优先返回 Vue 构建产物 dist/index.html，不存在则回退旧版原型
        dist_index = os.path.join(app.static_folder, 'dist', 'index.html')
        if os.path.isfile(dist_index):
            return send_from_directory(os.path.join(app.static_folder, 'dist'), 'index.html')
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/<path:path>')
    def serve_spa(path):
        from flask import send_from_directory, jsonify
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
                    return jsonify({"error": "请求方法不被允许"}), 405
            return jsonify({"error": "接口不存在"}), 404
        # 依次查找 dist/ 与 static/ 下的静态文件；都未命中则回退 SPA 入口
        for base in (os.path.join(app.static_folder, 'dist'), app.static_folder):
            file_path = os.path.join(base, path)
            if os.path.isfile(file_path):
                return send_from_directory(base, path)
        dist_index = os.path.join(app.static_folder, 'dist', 'index.html')
        if os.path.isfile(dist_index):
            return send_from_directory(os.path.join(app.static_folder, 'dist'), 'index.html')
        return send_from_directory(app.static_folder, 'index.html')
    with app.app_context():
        _enable_sqlite_foreign_keys()
        db.create_all()
        _migrate_db()
        from app.services.seed import seed_if_empty
        seed_if_empty()
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
    ]
    with db.engine.connect() as conn:
        for table, column, col_type in migrations:
            try:
                cols = [c['name'] for c in inspector.get_columns(table)]
                if column not in cols:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}'))
            except Exception:
                pass
        conn.commit()

def _register_error_handlers(app):
    from flask import jsonify
    from sqlalchemy.exc import IntegrityError

    _HTTP_ERROR_TEXT = {
        400: '请求参数有误',
        404: '请求的资源不存在',
        405: '请求方法不被允许',
        415: '请求体必须为 JSON 格式',
    }

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(415)
    def handle_http_error(e):
        # abort(400, description=...) 传入的业务提示优先；若仍是 Werkzeug 的类默认
        # 描述（英文），则替换为统一中文文案，避免英文/内部细节透给前端
        desc = getattr(e, 'description', None)
        if desc and desc == getattr(type(e), 'description', None):
            desc = None
        return jsonify({"error": desc or _HTTP_ERROR_TEXT.get(e.code, '请求错误')}), e.code

    @app.errorhandler(KeyError)
    @app.errorhandler(ValueError)
    def handle_bad_request(e):
        db.session.rollback()
        return jsonify({"error": f"参数错误: {e}"}), 400

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        db.session.rollback()
        detail = str(getattr(e, 'orig', e) or e).upper()
        if 'FOREIGN KEY' in detail:
            return jsonify({"error": "关联对象不存在，请检查所选客户/联系人/商机等是否有效"}), 400
        if 'UNIQUE' in detail:
            return jsonify({"error": "数据已存在，请勿重复提交"}), 400
        return jsonify({"error": "数据完整性校验失败"}), 400

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
        return jsonify({"error": "服务器内部错误"}), 500
