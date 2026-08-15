#!/usr/bin/env python3
"""
CRM v2.0 补充测试：错误处理、输入校验、看板联动、跟进同步、数据分析正确性。
与 test_aics.py 互补，覆盖原有 AICS 套件未触及的边界场景。
"""
import sys
import os
import tempfile
import atexit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db

_db_fd, _db_path = tempfile.mkstemp(suffix='.db')
os.close(_db_fd)
atexit.register(lambda: os.unlink(_db_path) if os.path.exists(_db_path) else None)

app = create_app(config={'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + _db_path})
client = app.test_client()

results = {"pass": 0, "fail": 0, "errors": []}

def check(cid, desc, cond, detail=''):
    if cond:
        results["pass"] += 1
        print(f"  PASS {cid}: {desc}")
    else:
        results["fail"] += 1
        results["errors"].append(f"[{cid}] {desc} -> {detail}")
        print(f"  FAIL {cid}: {desc} -> {detail}")

print("\n=== EDGE-01: 输入校验 / 错误处理 ===")
r = client.post('/api/customers', json={})
check("EDGE-01-001", "缺 name 建客户返回 400", r.status_code == 400, f"status={r.status_code}")

r = client.post('/api/leads', json={})
check("EDGE-01-002", "缺 title 建线索返回 400", r.status_code == 400, f"status={r.status_code}")

r = client.post('/api/leads', json={"title": "x", "deadline": "not-a-date"})
check("EDGE-01-003", "非法日期建线索返回 400", r.status_code == 400, f"status={r.status_code}")

r = client.post('/api/contacts', json={})
check("EDGE-01-004", "缺 name 建联系人返回 400", r.status_code == 400, f"status={r.status_code}")

r = client.post('/api/activities', json={"content": "t-format", "time": "2026-07-31T02:30"})
check("EDGE-01-005", "T 分隔时间格式可解析", r.status_code == 200, f"status={r.status_code} body={r.get_json()}")

r = client.get('/api/customers/99999')
check("EDGE-01-006", "不存在资源返回 404", r.status_code == 404, f"status={r.status_code}")

r = client.post('/api/leads/1/convert', json={})
r2 = client.post('/api/leads/1/convert', json={})
check("EDGE-01-007", "重复转化返回 400", r.status_code == 200 and r2.status_code == 400,
      f"first={r.status_code} second={r2.status_code}")

client.post('/api/leads/2/release', json={})
r = client.post('/api/leads/2/claim', json={"assignee": "张三"})
r2 = client.post('/api/leads/2/claim', json={})
check("EDGE-01-008", "领取/重复领取状态正确", r.status_code == 200 and r2.status_code == 400,
      f"claim={r.status_code} duplicate={r2.status_code}")

r = client.post('/api/kanban/import', json={"board_id": 999, "items": [{"title": "x"}]})
check("EDGE-01-009", "导入到不存在看板返回 404", r.status_code == 404, f"status={r.status_code}")

r = client.post('/api/kanban/import', json={"board_id": 1, "items": []})
check("EDGE-01-010", "空 items 导入返回 400", r.status_code == 400, f"status={r.status_code}")

r = client.post('/api/skills/not_exist/execute', json={})
body = r.get_json() or {}
check("EDGE-01-011", "未知技能返回错误信息", 'error' in body, f"body={body}")

print("\n=== EDGE-02: 数据分析正确性 ===")
with app.app_context():
    from app.models import Opportunity
    db.session.add(Opportunity(title="丢单测试", customer_id=1, amount="50万", current_stage="已丢单"))
    db.session.add(Opportunity(title="签约测试", customer_id=1, amount="80万", current_stage="合同签约"))
    db.session.commit()
data = client.get('/api/analytics').get_json()
wl = {w['name']: w['value'] for w in data['win_loss']}
total = data['summary']['total_opportunities']
check("EDGE-02-001", "赢/丢单不重复计数", wl['进行中'] == total - wl['赢单'] - wl['丢单'],
      f"win_loss={wl} total={total}")
check("EDGE-02-002", "漏斗包含数据中出现的阶段", any(f['stage'] in ('合同签约', '已丢单') for f in data['funnel']),
      f"funnel_stages={[f['stage'] for f in data['funnel']]}")

print("\n=== EDGE-03: 看板联动与截止日 ===")
r = client.post('/api/activities', json={"content": "看板联动活动", "method": "电话", "add_to_kanban": True})
check("EDGE-03-001", "活动 add_to_kanban 创建成功", r.status_code == 200, f"status={r.status_code}")
boards = client.get('/api/kanban/boards').get_json()
cards = [x for col in boards[0]['columns'] for x in col['cards']]
act_cards = [x for x in cards if x.get('source_type') == 'activity' and x.get('source_id') == r.get_json().get('id')]
check("EDGE-03-002", "活动联动生成看板卡片", len(act_cards) == 1, f"cards={act_cards}")

r = client.post('/api/opportunities/1/stages', json={"stage_name": "方案报价", "content": "x", "add_to_kanban": True})
check("EDGE-03-003", "阶段记录 add_to_kanban 创建成功", r.status_code == 200, f"status={r.status_code}")
boards = client.get('/api/kanban/boards').get_json()
cards = [x for col in boards[0]['columns'] for x in col['cards']]
stage_cards = [x for x in cards if x.get('source_type') == 'stage' and x.get('source_id') == r.get_json().get('id')]
check("EDGE-03-004", "阶段记录联动生成看板卡片", len(stage_cards) == 1, f"cards={stage_cards}")

r = client.post('/api/kanban/import', json={"board_id": 1, "items": [{"title": "截止日卡片", "deadline": "2026-08-15"}]})
check("EDGE-03-005", "导入卡片带截止日成功", r.status_code == 200, f"status={r.status_code}")
boards = client.get('/api/kanban/boards').get_json()
cards = [x for col in boards[0]['columns'] for x in col['cards']]
dl_cards = [x for x in cards if x['title'] == '截止日卡片']
check("EDGE-03-006", "导入卡片截止日已入库", dl_cards and dl_cards[0].get('deadline') == '2026-08-15',
      f"cards={dl_cards}")

print("\n=== EDGE-04: 跟进计划同步 ===")
r = client.post('/api/activities', json={"content": "跟进联动", "time": "2026-07-31 10:00", "next_time": "2026-08-05"})
aid = r.get_json().get('id')
fups = client.get('/api/followups').get_json()
fu = [f for f in fups if f.get('source_activity_id') == aid]
check("EDGE-04-001", "活动自动生成跟进计划", len(fu) == 1, f"followups={fu}")

r = client.put(f'/api/activities/{aid}', json={"next_time": "2026-08-10"})
check("EDGE-04-002", "更新活动成功", r.status_code == 200, f"status={r.status_code}")
fups = client.get('/api/followups').get_json()
fu = [f for f in fups if f.get('source_activity_id') == aid]
check("EDGE-04-003", "更新活动同步跟进计划日期", fu and fu[0].get('plan_date', '').startswith('2026-08-10'),
      f"plan_date={fu[0].get('plan_date') if fu else None}")

print("\n=== EDGE-05: 接口契约 ===")
r = client.get('/api/skills')
body = r.get_json() or {}
check("EDGE-05-001", "技能接口返回 builtin/custom 结构", isinstance(body, dict) and 'builtin' in body and 'custom' in body,
      f"keys={list(body.keys()) if isinstance(body, dict) else None}")

r = client.get('/api/kanban/boards?search=业务跟进')
check("EDGE-05-002", "看板 search 参数生效", len(r.get_json()) == 1, f"count={len(r.get_json())}")

r = client.get('/api/customers')
check("EDGE-05-003", "默认不再放开任意来源 CORS", r.headers.get('Access-Control-Allow-Origin') != '*',
      f"ACAO={r.headers.get('Access-Control-Allow-Origin')}")

r = client.post('/api/config/test-ai', json={})
check("EDGE-05-004", "未配置 API Key 返回 400", r.status_code == 400, f"status={r.status_code}")

total = results["pass"] + results["fail"]
print(f"\n{'='*60}")
print(f"  EDGE CASE TEST REPORT")
print(f"  Total:  {total}  Passed: {results['pass']}  Failed: {results['fail']}")
print(f"{'='*60}")
for err in results["errors"]:
    print(f"  - {err}")
print()
sys.exit(0 if results["fail"] == 0 else 1)
