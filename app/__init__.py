from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config['SECRET_KEY'] = 'forest-drone-crm-2026'
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'crm.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
        from app.services.seed import seed_if_empty
        seed_if_empty()
    return app
