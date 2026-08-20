"""生产环境入口：waitress 托管，SECRET_KEY 持久化到 instance/ 保证登录会话跨重启有效。"""
import os
import secrets

from app import create_app

base = os.path.dirname(os.path.abspath(__file__))
instance_dir = os.path.join(base, 'instance')
os.makedirs(instance_dir, exist_ok=True)

# 会话密钥：首次生成后持久保存，重启不掉登录
key_file = os.path.join(instance_dir, 'secret_key')
if not os.path.exists(key_file):
    with open(key_file, 'w') as f:
        f.write(secrets.token_hex(32))
try:
    with open(key_file) as f:
        os.environ.setdefault('SECRET_KEY', f.read().strip())
except OSError:
    pass

app = create_app()

if __name__ == '__main__':
    from waitress import serve
    port = int(os.environ.get('CRM_PORT', 5001))
    print(f'CRM 已启动: http://localhost:{port}  (默认账号 admin / admin123)')
    serve(app, host='0.0.0.0', port=port, threads=8)
