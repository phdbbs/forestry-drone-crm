#!/bin/bash
# 启动脚本：安装依赖 -> Alembic 迁移 -> 启动 Flask
set -e
cd "$(dirname "$0")"

pip install -r requirements.txt

# 迁移数据库（create_app 内部也会自动迁移，这里再显式跑一次便于排查）
python -m alembic upgrade head || true

exec python -c "from app import create_app; app = create_app(); app.run(host='0.0.0.0', port=${PORT:-5001}, use_reloader=False)"
