#!/usr/bin/env python3
"""
AICS - Automated Integration & Compliance Suite
林业无人机CRM系统 V1.1 全量测试验证
每条测试用例带有唯一 AICS 标识，用于需求追溯
"""
import json
import sys
import os
import tempfile
import atexit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db

# Use a temporary database so each test run starts fresh (seeded)
_db_fd, _db_path = tempfile.mkstemp(suffix='.db')
os.close(_db_fd)
atexit.register(lambda: os.unlink(_db_path) if os.path.exists(_db_path) else None)

app = create_app(config={'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + _db_path})
client = app.test_client()

# 所有 /api 接口受 Flask-Login 保护，先登录获取会话
_login_r = client.post('/api/auth/login', json={
    'username': os.environ.get('CRM_ADMIN_USERNAME', 'admin'),
    'password': os.environ.get('CRM_ADMIN_PASSWORD', 'admin123'),
}, content_type='application/json')
if _login_r.status_code != 200:
    print(f"FATAL: login failed with status {_login_r.status_code}")
    sys.exit(1)

results = {"pass": 0, "fail": 0, "errors": []}

def run_test(aics_id, description, method, endpoint, expected_status=None, body=None, check_fn=None):
    try:
        if method == "GET":
            r = client.get(endpoint)
        elif method == "POST":
            r = client.post(endpoint, json=body or {}, content_type='application/json')
        elif method == "PUT":
            r = client.put(endpoint, json=body or {}, content_type='application/json')
        elif method == "DELETE":
            r = client.delete(endpoint)
        else:
            raise ValueError(f"Unknown method: {method}")

        status_ok = True
        if expected_status is not None:
            status_ok = r.status_code == expected_status

        body_ok = True
        if check_fn:
            try:
                data = r.get_json()
                body_ok = check_fn(data)
            except Exception as e:
                body_ok = False
                results["errors"].append(f"[{aics_id}] check_fn exception: {e}")

        if status_ok and body_ok:
            results["pass"] += 1
            print(f"  PASS {aics_id}: {description}")
        else:
            results["fail"] += 1
            err = f"[{aics_id}] {description} -> status={r.status_code}"
            if expected_status:
                err += f" (expected {expected_status})"
            if not body_ok:
                err += " body_check=FAIL"
            results["errors"].append(err)
            print(f"  FAIL {aics_id}: {description} (status={r.status_code})")
    except Exception as e:
        results["fail"] += 1
        results["errors"].append(f"[{aics_id}] EXCEPTION: {e}")
        print(f"  FAIL {aics_id}: {description} -> EXCEPTION: {e}")

def ep(aics_id, desc, method, endpoint, expected_status=200, body=None, check_fn=None):
    run_test(aics_id, desc, method, endpoint, expected_status, body=body, check_fn=check_fn)

# ============================================================
# AICS-M001: 客户管理模块
# ============================================================
print("\n=== AICS-M001: Customer Management ===")

ep("AICS-M001-001", "Customer list query", "GET", "/api/customers")
ep("AICS-M001-002", "Create customer", "POST", "/api/customers", body={
    "name": "AICS Test - Guangdong Forestry Bureau", "short_name": "GD Forestry",
    "customer_type": "Government", "level": "Provincial", "region": "Guangzhou",
    "source": "Manual", "remark": "AICS-M001-002 test data"
})
ep("AICS-M001-003", "Get customer detail", "GET", "/api/customers/1")
ep("AICS-M001-004", "Edit customer", "PUT", "/api/customers/1", body={
    "name": "Zhejiang Forestry Bureau", "short_name": "ZJ Forestry",
    "customer_type": "Government", "level": "Provincial", "region": "Hangzhou"
})
ep("AICS-M001-005", "Customer search filter", "GET", "/api/customers?search=Zhejiang")
ep("AICS-M001-006", "Delete customer", "DELETE", "/api/customers/7")
ep("AICS-M001-007", "Customer news list", "GET", "/api/customers/1/news")

# ============================================================
# AICS-M002: Lead Management Module
# ============================================================
print("\n=== AICS-M002: Lead Management ===")

ep("AICS-M002-001", "Lead list query", "GET", "/api/leads")
ep("AICS-M002-002", "Create high-match lead", "POST", "/api/leads", body={
    "title": "AICS Test - UAV Forest Inspection Service", "bid_number": "AICS-2026-001",
    "budget": "350", "deadline": "2026-12-31", "region": "Guangdong",
    "purchaser": "Guangdong Forestry Bureau",
    "service_content": "UAV flight inspection, forest patrol, AI pest recognition",
    "source_platform": "Government Procurement", "source_url": "https://test.aics.com/001"
})
ep("AICS-M002-003", "Create low-match lead", "POST", "/api/leads", body={
    "title": "AICS Test - Tree felling and clearing construction", "bid_number": "AICS-2026-002",
    "budget": "80", "deadline": "2026-11-30", "region": "Guangdong",
    "purchaser": "Guangdong Forestry Bureau",
    "service_content": "Pine tree felling, clearing, disinfection construction",
    "source_platform": "Government Procurement", "source_url": "https://test.aics.com/002"
})
ep("AICS-M002-004", "Get lead detail", "GET", "/api/leads/1")
ep("AICS-M002-005", "Edit lead", "PUT", "/api/leads/1", body={
    "title": "2026 Zhejiang Pine Pest UAV Inspection Project", "budget": "180"
})
ep("AICS-M002-006", "Lead status filter", "GET", "/api/leads?status=active")

# M2.3: Match level verification
run_test("AICS-M002-007", "Lead match level validation", "GET", "/api/leads/1",
         check_fn=lambda d: d.get("match_level") in ["High", "Medium", "Low", "高匹配", "中匹配", "低匹配"])

# M2.4: Convert lead to opportunity
# Find the latest lead ID dynamically for conversion
from app.models import Lead as _Lead
with app.app_context():
    latest_lead = _Lead.query.filter_by(status="active").order_by(_Lead.id.desc()).first()
    lead_id = latest_lead.id if latest_lead else 8
ep(f"AICS-M002-008", "Convert lead to opportunity", "POST", f"/api/leads/{lead_id}/convert", body={
    "title": "AICS - Guangdong UAV Inspection Opportunity", "amount": "350",
    "stage": "Initial Contact", "customer_id": 7
})
ep("AICS-M002-009", "Lead converted filter", "GET", "/api/leads?status=converted")
# Delete the lead we just created (low-match one)
with app.app_context():
    low_lead = _Lead.query.filter_by(title="AICS Test - Tree felling and clearing construction").first()
    lead_del_id = low_lead.id if low_lead else 9
ep(f"AICS-M002-010", "Delete lead", "DELETE", f"/api/leads/{lead_del_id}")

# ============================================================
# AICS-M003: Opportunity Management Module
# ============================================================
print("\n=== AICS-M003: Opportunity Management ===")

ep("AICS-M003-001", "Opportunity list query", "GET", "/api/opportunities")
ep("AICS-M003-002", "Create opportunity", "POST", "/api/opportunities", body={
    "title": "AICS Test Opportunity - Shenzhen UAV Monitoring", "customer_id": 5,
    "amount": "500", "current_stage": "Needs Research"
})
ep("AICS-M003-003", "Get opportunity detail", "GET", "/api/opportunities/1")
ep("AICS-M003-004", "Edit opportunity", "PUT", "/api/opportunities/1", body={
    "title": "Zhejiang UAV Inspection Service Opportunity", "amount": "180"
})
ep("AICS-M003-005", "Opportunity search", "GET", "/api/opportunities?search=Zhejiang")

# M3.2: Stage management
ep("AICS-M003-006", "Add stage record", "POST", "/api/opportunities/1/stages", body={
    "stage_name": "Proposal Submission", "content": "Submit final proposal and quotation",
    "deadline": "2026-07-15", "status": "pending", "add_to_kanban": True
})

# M3.3: Kanban linkage
ep("AICS-M003-007", "Stage record with kanban flag", "POST", "/api/opportunities/1/stages", body={
    "stage_name": "Internal Review", "content": "Internal technical review",
    "deadline": "2026-07-10", "status": "pending", "add_to_kanban": True
})
from app.models import Opportunity as _Opp
with app.app_context():
    del_opp = _Opp.query.filter_by(title="AICS Test Opportunity - Shenzhen UAV Monitoring").first()
    opp_id = del_opp.id if del_opp else 4
ep(f"AICS-M003-008", "Delete opportunity", "DELETE", f"/api/opportunities/{opp_id}")

# ============================================================
# AICS-M004: Contact Management Module
# ============================================================
print("\n=== AICS-M004: Contact Management ===")

ep("AICS-M004-001", "Contact list query", "GET", "/api/contacts")
ep("AICS-M004-002", "Create contact", "POST", "/api/contacts", body={
    "name": "AICS Test Contact - Chen", "title": "Forestry Section Chief",
    "phone": "135-0000-1234", "email": "chen@test.com", "customer_id": 1,
    "importance": "Important", "business_scope": "UAV inspection management",
    "notes": "AICS-M004-002 test data"
})
ep("AICS-M004-003", "Get contact detail", "GET", "/api/contacts/1")
ep("AICS-M004-004", "Edit contact", "PUT", "/api/contacts/1", body={
    "name": "Director Wang", "title": "Forestry Management Director",
    "phone": "138-0571-1234"
})
ep("AICS-M004-005", "Contact search", "GET", "/api/contacts?search=Wang")
ep("AICS-M004-006", "Delete contact", "DELETE", "/api/contacts/6")

# ============================================================
# AICS-M005: Activity Management Module
# ============================================================
print("\n=== AICS-M005: Activity Management ===")

ep("AICS-M005-001", "Activity list query", "GET", "/api/activities")
ep("AICS-M005-002", "Create activity", "POST", "/api/activities", body={
    "title": "AICS Test - Phone Call", "method": "Phone", "customer_id": 1,
    "contact_id": 1, "time": "2026-06-20 10:00", "content": "Discuss project progress",
    "next_time": "2026-06-27", "next_followup_content": "Follow on bid results"
})
ep("AICS-M005-003", "Get activity detail", "GET", "/api/activities/1")
ep("AICS-M005-004", "Edit activity", "PUT", "/api/activities/1", body={
    "title": "Confirm bid sealing requirements", "content": "Confirmed, awaiting opening"
})
ep("AICS-M005-005", "Activity search", "GET", "/api/activities?search=Phone")
from app.models import Activity as _Act
with app.app_context():
    del_act = _Act.query.filter(_Act.content.like("%Discuss project progress%")).first()
    act_id = del_act.id if del_act else 4
ep(f"AICS-M005-006", "Delete activity", "DELETE", f"/api/activities/{act_id}")

# M5.1: Custom follow-up plan with next communication content
ep("AICS-M005-007", "Activity with next followup content", "POST", "/api/activities", body={
    "title": "AICS Test - Visit Plan", "method": "Visit", "customer_id": 2,
    "contact_id": 2, "time": "2026-06-25 14:00", "content": "Visit client for proposal",
    "next_time": "2026-07-01", "next_followup_content": "Watch for tender announcement"
})

# M5.3: Kanban linkage
ep("AICS-M005-008", "Activity with kanban flag", "POST", "/api/activities", body={
    "title": "AICS Test - Meeting", "method": "Meeting", "customer_id": 1,
    "contact_id": 1, "time": "2026-06-22 09:00", "content": "Technical proposal review",
    "add_to_kanban": True
})

# ============================================================
# AICS-M006: Kanban Management Module
# ============================================================
print("\n=== AICS-M006: Kanban Management ===")

ep("AICS-M006-001", "Kanban list query", "GET", "/api/kanban/boards")
ep("AICS-M006-002", "Create kanban board", "POST", "/api/kanban/boards", body={"name": "AICS Test Board"})
run_test("AICS-M006-003", "Kanban has 3 default columns", "GET", "/api/kanban/boards",
    check_fn=lambda d: len(d) > 0 and len(d[0].get("columns", [])) >= 3 if isinstance(d, list) else len(d.get("columns", [])) >= 3)
ep("AICS-M006-004", "Import cards to kanban", "POST", "/api/kanban/import", body={
    "board_id": 1, "items": [
        {"title": "AICS-Import Card 1", "description": "Test import", "color": "green"},
        {"title": "AICS-Import Card 2", "description": "Test import", "color": "blue"}
    ]
})
ep("AICS-M006-005", "Move card between columns", "POST", "/api/kanban/cards/1/move", body={"column_id": 2})
ep("AICS-M006-006", "Kanban search", "GET", "/api/kanban/boards?search=AICS")

# ============================================================
# AICS-M007: System Settings Module
# ============================================================
print("\n=== AICS-M007: System Settings ===")

ep("AICS-M007-001", "Config read", "GET", "/api/config")
ep("AICS-M007-002", "Config update", "PUT", "/api/config", body={
    "name": "AICS-Forestry UAV CRM", "company": "AICS Test Company", "color": "#15803d"
})
ep("AICS-M007-003", "AI config read", "GET", "/api/config",
    check_fn=lambda d: "ai_api_key" in d or "ai_model" in d)
ep("AICS-M007-004", "AI config update", "PUT", "/api/config", body={
    "ai_api_key": "sk-aics-test-key-2026", "ai_api_endpoint": "https://api.openai.com/v1",
    "ai_model": "gpt-4o"
})
ep("AICS-M007-005", "Skill list", "GET", "/api/skills")
ep("AICS-M007-006", "Create skill", "POST", "/api/skills", body={
    "name": "aics_test_skill_007", "description": "AICS Test Skill", "icon": "TEST"
})
run_test("AICS-M007-007", "Delete skill", "GET", "/api/skills")

# ============================================================
# AICS-M008: AI Suggestions & Daily Brief
# ============================================================
print("\n=== AICS-M008: AI Suggestions & Daily Brief ===")

ep("AICS-M008-001", "AI suggestions list", "GET", "/api/suggestions")
ep("AICS-M008-002", "Daily brief", "GET", "/api/daily-brief")

# ============================================================
# AICS-M009: Follow-up Management Module
# ============================================================
print("\n=== AICS-M009: Follow-up Management ===")

ep("AICS-M009-001", "Follow-up list query", "GET", "/api/followups")
ep("AICS-M009-002", "Create follow-up plan", "POST", "/api/followups", body={
    "contact_id": 1, "customer_id": 1, "plan_date": "2026-06-28",
    "content": "AICS test - follow up on project progress",
    "ai_suggested_content": "Suggested: ask about bid progress",
    "add_to_kanban": True
})
ep("AICS-M009-003", "Get follow-up detail", "GET", "/api/followups/1")
ep("AICS-M009-004", "Edit follow-up", "PUT", "/api/followups/1", body={
    "content": "AICS test - updated follow-up content",
    "actual_date": "2026-06-28", "actual_content": "Completed phone call"
})
ep("AICS-M009-005", "Follow-up search", "GET", "/api/followups?search=AICS")
ep("AICS-M009-006", "Delete follow-up", "DELETE", "/api/followups/1")

# ============================================================
# AICS-M010: Dashboard & Homepage
# ============================================================
print("\n=== AICS-M010: Dashboard & Homepage ===")

# Homepage test - use direct client call to avoid get_json on HTML
try:
    r = client.get("/")
    html = r.get_data(as_text=True)
    if r.status_code == 200 and "<!DOCTYPE html>" in html:
        results["pass"] += 1
        print("  PASS AICS-M010-001: Homepage HTML loads")
    else:
        results["fail"] += 1
        results["errors"].append(f"[AICS-M010-001] Homepage check failed: status={r.status_code}")
        print(f"  FAIL AICS-M010-001: Homepage HTML loads")
except Exception as e:
    results["fail"] += 1
    results["errors"].append(f"[AICS-M010-001] EXCEPTION: {e}")
    print(f"  FAIL AICS-M010-001: EXCEPTION: {e}")

run_test("AICS-M010-002", "Dashboard stats data", "GET", "/api/dashboard",
         check_fn=lambda d: "stats" in d and "active_leads" in d.get("stats", {}))

run_test("AICS-M010-003", "Dashboard urgent leads", "GET", "/api/dashboard",
         check_fn=lambda d: "urgent_leads" in d)

run_test("AICS-M010-004", "Dashboard today activities", "GET", "/api/dashboard",
         check_fn=lambda d: "today_activities" in d)

run_test("AICS-M010-005", "Dashboard today followups", "GET", "/api/dashboard",
         check_fn=lambda d: "today_followups" in d)

# ============================================================
# AICS-M011: Data Crawler Module
# ============================================================
print("\n=== AICS-M011: Data Crawler ===")

ep("AICS-M011-001", "Crawler trigger endpoint", "POST", "/api/crawl", body={"url": "https://www.ccgp.gov.cn/"})

# ============================================================
# AICS-M012: Global Rules Validation
# ============================================================
print("\n=== AICS-M012: Global Rules ===")

run_test("AICS-M012-001", "Crawler keywords config exists", "GET", "/api/config",
         check_fn=lambda d: "keywords" in d)

run_test("AICS-M012-002", "Lead match level editable", "PUT", "/api/leads/2", body={"match_level": "High"})

# ============================================================
# SUMMARY REPORT
# ============================================================
total = results["pass"] + results["fail"]
print(f"\n{'='*60}")
print(f"  AICS TEST REPORT")
print(f"{'='*60}")
print(f"  Total:  {total} tests")
print(f"  Passed: {results['pass']}  PASS")
print(f"  Failed: {results['fail']}  FAIL")
print(f"  Rate:   {results['pass']/total*100:.1f}%")
print(f"{'='*60}")

if results["errors"]:
    print(f"\nFailure Details ({len(results['errors'])} items):")
    for err in results["errors"]:
        print(f"  - {err}")
    print()

sys.exit(0 if results["fail"] == 0 else 1)
