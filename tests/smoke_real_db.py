#!/usr/bin/env python3
"""真实数据库副本冒烟脚本（端到端）。

用途：在**不触碰真实库**的前提下，把 instance/crm.db 复制到临时目录，
用测试客户端跑一遍主链路，验证：
  1. 所有列表/聚合/详情接口返回 2xx 且为 JSON（或导出接口为 CSV）；
  2. 任何请求都不会返回 5xx；
  3. 任何请求都不会返回 HTML（SPA 兜底不得吞掉 API 错误）；
  4. 错误语义正确：404 路径不存在 / 405 方法不符 / 400 参数非法 / 415 非 JSON 请求体。

真实库有 251 条线索，数据形态与 seed 演示数据差异很大，
单测跑的是 seed 数据，因此这层冒烟用于兜住"真实数据下才暴露"的问题。

用法：
    python tests/smoke_real_db.py [数据库路径]
"""
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'instance', 'crm.db')

if not os.path.isfile(DB):
    print(f'找不到数据库文件: {DB}')
    sys.exit(2)

tmpdir = tempfile.mkdtemp(prefix='crm-smoke-')
db_copy = os.path.join(tmpdir, 'crm.db')
shutil.copy(DB, db_copy)

from app import create_app  # noqa: E402

app = create_app({'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + db_copy, 'TESTING': True})
client = app.test_client()
failures = []


def check(method, url, expect=None, json_body=None):
    """断言状态码、响应类型与"绝不为 HTML/5xx"。"""
    kwargs = {'json': json_body} if json_body is not None else {}
    resp = getattr(client, method)(url, **kwargs)
    ctype = resp.headers.get('Content-Type', '')
    body = resp.get_data(as_text=True)
    is_data = 'json' in ctype or 'csv' in ctype
    problem = []
    if resp.status_code >= 500:
        problem.append(f'5xx({resp.status_code})')
    if not is_data:
        problem.append(f'非 JSON/CSV: {ctype}')
    if expect is not None and resp.status_code != expect:
        problem.append(f'期望 {expect}，实际 {resp.status_code}')
    if problem:
        failures.append(f'{method.upper()} {url} -> {"; ".join(problem)} | {body[:120]}')
        print(f'  FAIL {resp.status_code} {method.upper():6} {url}')
    else:
        print(f'  ok   {resp.status_code} {method.upper():6} {url}')
    return resp


print('— 列表 / 聚合接口 —')
for url in ('/api/dashboard', '/api/customers', '/api/leads', '/api/leads?status=active',
            '/api/leads?status=converted', '/api/leads?status=abandoned',
            '/api/leads?status=pool', '/api/leads?region=浙江', '/api/leads?level=高匹配',
            '/api/leads?search=无人机', '/api/opportunities', '/api/contacts',
            '/api/activities', '/api/followups', '/api/kanban/boards', '/api/analytics',
            '/api/daily-brief', '/api/config', '/api/skills', '/api/crawl/status',
            '/api/suggestions'):
    check('get', url, expect=200)

print('\n— 导出接口（POST + ids）—')
for etype in ('leads', 'customers', 'opportunities', 'contacts', 'activities', 'followups'):
    check('post', f'/api/export/{etype}', expect=200, json_body={'ids': []})

print('\n— 详情接口（真实主键）—')
ids = {}
for name, url in (('lead', '/api/leads'), ('customer', '/api/customers'),
                  ('contact', '/api/contacts'), ('opportunity', '/api/opportunities'),
                  ('board', '/api/kanban/boards')):
    payload = client.get(url).get_json()
    rows = payload if isinstance(payload, list) else (
        payload.get('items') or payload.get('data') or [])
    if rows:
        ids[name] = rows[0]['id']

for url in (f"/api/leads/{ids.get('lead')}",
            f"/api/customers/{ids.get('customer')}",
            f"/api/customers/{ids.get('customer')}/news",
            f"/api/contacts/{ids.get('contact')}",
            f"/api/opportunities/{ids.get('opportunity')}"):
    if not url.endswith('None'):
        check('get', url, expect=200)

print('\n— 错误语义 —')
check('get', '/api/does-not-exist', expect=404)        # 未注册路径
check('get', '/api/export/leads', expect=405)          # 路径存在但仅支持 POST
check('delete', '/api/dashboard', expect=405)          # 路径存在但方法不符
check('get', '/api/kanban/boards/1', expect=405)       # 看板详情仅支持 DELETE
check('post', '/api/customers', expect=400, json_body={})                # 缺必填
check('post', '/api/customers', expect=400, json_body={'name': '   '})   # 空白名
check('post', '/api/leads', expect=400, json_body={'title': ''})         # 缺必填
check('get', '/api/activities?customer_id=abc', expect=400)              # 非法整数参数
check('get', '/api/followups?customer_id=abc', expect=400)
check('post', '/api/leads', expect=400,
      json_body={'title': '冒烟-孤儿引用', 'customer_id': 999999})  # 外键悬空必须拒绝
check('post', '/api/customers', expect=415)            # 非 JSON 请求体

shutil.rmtree(tmpdir, ignore_errors=True)
print()
if failures:
    print(f'冒烟失败：{len(failures)} 项')
    for item in failures:
        print('  -', item)
    sys.exit(1)
print('冒烟通过：主链路无 5xx、无 HTML、错误语义正确')
