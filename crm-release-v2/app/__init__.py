import os
from flask import Flask, send_from_directory, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user

db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config=None):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'forest-drone-crm-2026')
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base, 'instance', 'crm.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    if config:
        app.config.update(config)
    try:
        from flask_cors import CORS
        CORS(app)
    except ImportError:
        pass

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.session_protection = 'strong'

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.routes import api
    app.register_blueprint(api, url_prefix='/api')
    from app.routes.auth import auth
    app.register_blueprint(auth)

    @app.before_request
    def protect_api():
        p = request.path
        if p.startswith('/api/'):
            # 鉴权相关接口与健康检查对未登录开放
            if p.startswith('/api/auth/') or p == '/api/health':
                return None
            if not current_user.is_authenticated:
                return jsonify({'error': 'unauthorized', 'code': 401}), 401

    dist_dir = os.path.join(app.static_folder, 'dist')

    def _spa_dir():
        if os.path.isfile(os.path.join(dist_dir, 'index.html')):
            return dist_dir
        return app.static_folder

    @app.route('/')
    def serve_index():
        return send_from_directory(_spa_dir(), 'index.html')

    @app.route('/<path:path>')
    def serve_spa(path):
        d = _spa_dir()
        fp = os.path.join(d, path)
        if os.path.isfile(fp):
            return send_from_directory(d, path)
        return send_from_directory(d, 'index.html')

    with app.app_context():
        run_migrations(app)
        from app.services.seed import seed_if_empty, seed_admin
        seed_admin()
        seed_if_empty()
    return app


def run_migrations(app):
    """优先用 Alembic 升级 schema；若迁移缺失则降级为 create_all 兜底。"""
    try:
        from alembic.config import Config
        from alembic import command
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ini = os.path.join(base, 'alembic.ini')
        cfg = Config(ini)
        cfg.set_main_option('script_location', os.path.join(base, 'migrations'))
        cfg.set_main_option('sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI'])
        command.upgrade(cfg, 'head')
    except Exception as e:
        app.logger.warning('Alembic 迁移未执行（将使用 create_all 兜底）: %s', e)
    # 兜底：确保核心表存在
    try:
        inspector = db.inspect(db.engine)
        if 'users' not in inspector.get_table_names():
            db.create_all()
    except Exception:
        pass
