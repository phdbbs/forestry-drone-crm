#!/bin/bash
cd /Users/wl/Documents/CRM
source .venv/bin/activate
python -c "
from app import create_app
app = create_app()
app.run(host='0.0.0.0', port=5001, use_reloader=False)
"
