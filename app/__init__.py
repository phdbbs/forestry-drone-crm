from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def create_app(config=None):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('CRM_SECRET_KEY', 'forest-drone-crm-2026')
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'crm.db')
    # SQLite 不会自动创建父目录：全新环境首次启动前必须确保 instance/ 存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    _register_error_handlers(app)
    from app.routes import api
    app.register_blueprint(api, url_prefix='/api')

    @app.route('/')
    def serve_index():
        from flask import send_from_directory
        return send_from_directory(app.static_folder, 'index.html')

    @app.route('/<path:path>')
    def serve_spa(path):
        from flask import send_from_directory
        import os
        file_path = os.path.join(app.static_folder, path)
        if os.path.isfile(file_path):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')
    with app.app_context():
        db.create_all()
        _migrate_db()
        from app.services.seed import seed_if_empty
        seed_if_empty()
    return app

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

    @app.errorhandler(400)
    @app.errorhandler(404)
    def handle_http_error(e):
        return jsonify({"error": getattr(e, 'description', None) or '请求错误'}), e.code

    @app.errorhandler(KeyError)
    @app.errorhandler(ValueError)
    @app.errorhandler(IntegrityError)
    def handle_bad_request(e):
        db.session.rollback()
        return jsonify({"error": f"参数错误: {e}"}), 400

    @app.errorhandler(500)
    def handle_server_error(e):
        db.session.rollback()
        return jsonify({"error": "服务器内部错误"}), 500
