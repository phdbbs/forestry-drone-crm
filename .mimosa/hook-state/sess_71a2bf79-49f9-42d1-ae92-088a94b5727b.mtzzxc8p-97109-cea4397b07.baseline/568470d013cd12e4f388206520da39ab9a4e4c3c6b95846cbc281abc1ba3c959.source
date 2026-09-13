from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    app.run(
        debug=os.environ.get('CRM_DEBUG') == '1',
        host='0.0.0.0',
        port=int(os.environ.get('CRM_PORT', '5001')),
    )
