"""gunicorn 生产配置

worker 选择说明：后端为 SQLite，多 worker 进程各自持有连接易触发
database is locked；故采用「1 worker + 8 线程」兼顾并发与数据安全。
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

bind = f"0.0.0.0:{os.environ.get('CRM_PORT', '5001')}"
workers = 1
threads = 8
timeout = 60
graceful_timeout = 30
keepalive = 5

preload_app = True

accesslog = os.path.join(LOG_DIR, 'access.log')
errorlog = os.path.join(LOG_DIR, 'error.log')
loglevel = 'info'
access_log_format = '%(t)s %(h)s "%(r)s" %(s)s %(b)s %(M)sms'

# 长期运行防内存缓慢增长
max_requests = 2000
max_requests_jitter = 200
