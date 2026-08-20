"""CRM 生产环境入口（gunicorn 加载本模块）

与开发入口 app.py 的区别：
- SECRET_KEY 首次生成后持久化在 instance/secret_key，重启不变
- SQLite 生产调优：WAL 日志模式 + 忙等待超时，多线程下不再 database is locked
- 不启用 Flask 开发服务器与热重载
"""
import os
import secrets

from app import create_app, db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
KEY_FILE = os.path.join(INSTANCE_DIR, 'secret_key')

os.makedirs(INSTANCE_DIR, exist_ok=True)

if os.path.exists(KEY_FILE):
    with open(KEY_FILE, encoding='utf-8') as f:
        secret_key = f.read().strip()
else:
    secret_key = secrets.token_hex(32)
    with open(KEY_FILE, 'w', encoding='utf-8') as f:
        f.write(secret_key)
    os.chmod(KEY_FILE, 0o600)

app = create_app(config={
    'SECRET_KEY': secret_key,
    # SQLite 并发读写调优：忙时最多等 15 秒，避免 gunicorn 多线程下锁库报错
    'SQLALCHEMY_ENGINE_OPTIONS': {
        'connect_args': {'timeout': 15, 'check_same_thread': False},
        'pool_pre_ping': True,
    },
})

# WAL 模式持久写入库文件：读不阻塞写，生产必开
with app.app_context():
    from sqlalchemy import text
    with db.engine.connect() as conn:
        conn.execute(text('PRAGMA journal_mode=WAL'))
        conn.execute(text('PRAGMA busy_timeout=15000'))
        conn.commit()
