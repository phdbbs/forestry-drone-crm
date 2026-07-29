from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def create_app(config=None):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = 'forest-drone-crm-2026'
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'crm.db')
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
        ('opportunities', 'probability', 'INTEGER DEFAULT 20'),
        ('opportunities', 'expected_close', 'DATETIME'),
        ('contacts', 'role', "VARCHAR(50) DEFAULT ''"),
        ('contacts', 'tags', "TEXT DEFAULT ''"),
        ('contacts', 'avatar', "VARCHAR(10) DEFAULT ''"),
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
