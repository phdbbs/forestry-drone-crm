from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

# 网络卷上的 SQLite 出现 I/O 层错误时，池中连接已不可用。
# 命中这些关键字说明是 I/O 层故障（而非 SQL 语法/约束问题），应丢弃整个连接池重连。
_IO_ERROR_MARKERS = (
    'disk i/o error',
    'unable to open database file',
    'database disk image is malformed',
)

_io_recovery_installed = False


def _install_io_error_recovery():
    """I/O 故障后自动丢弃连接池，使服务无需重启即可恢复。

    背景：本项目数据库文件放在 SMB 网络卷上。挂载瞬时抖动会让连接池里
    已建立的连接失效（sqlite3.OperationalError: disk I/O error）。失效的是
    「池中的连接」本身，因此此后每个请求都会继续失败，只有重启进程才能恢复。
    挂载恢复后新建连接是正常的，所以这里在引擎层捕获 I/O 类错误并 dispose 连接池，
    下一个请求重新建连即可正常服务。

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
        msg = str(exception_context.original_exception).lower()
        if any(marker in msg for marker in _IO_ERROR_MARKERS):
            try:
                exception_context.engine.dispose()
            except Exception:
                # 自愈失败不应掩盖原始异常
                pass


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
        # 限制连接最长存活时间，避免长期持有网络卷上的文件描述符
        'pool_recycle': 300,
        # 网络卷上的锁竞争比本地磁盘慢，放宽等待时间
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
    """SQLite 默认不校验外键，开启后杜绝 customer_id/contact_id 等悬空引用。"""
    from sqlalchemy import event
    if db.engine.dialect.name != 'sqlite':
        return

    @event.listens_for(db.engine, 'connect')
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
        except Exception:
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
        db.session.rollback()
        return jsonify({"error": "服务器内部错误"}), 500
