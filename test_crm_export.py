#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRM CSV 导出功能测试（基于种子数据）"""
import requests, sys, csv, io
from urllib.parse import quote

BASE = 'http://localhost:5001/api'
PASS, FAIL = [], []

def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗ FAIL'} {name}" + (f"  [{detail}]" if detail and not cond else ''))

def export(etype, ids=None):
    r = requests.post(f'{BASE}/export/{etype}', json={'ids': ids} if ids else {}, timeout=15)
    return r

def parse_csv(text):
    assert text.startswith('\ufeff'), '缺少UTF-8 BOM'
    return list(csv.reader(io.StringIO(text.lstrip('\ufeff'))))

print('════ 导出功能测试（种子数据） ════')

# 1. 六种类型全部可导出
for etype in ['leads', 'opportunities', 'contacts', 'customers', 'activities', 'followups']:
    r = export(etype)
    ok = r.status_code == 200 and 'text/csv' in r.headers.get('Content-Type', '')
    rows = parse_csv(r.text) if ok else []
    check(f'导出{etype}', ok and len(rows) >= 2, f"status={r.status_code} rows={len(rows) if ok else '-'}")
    cd = r.headers.get('Content-Disposition', '')
    if etype == 'leads':
        check('Content-Disposition带RFC5987编码文件名', 'filename*=UTF-8\'\'' in cd and quote('线索') in cd, cd)
        check('leads表头正确', rows[0][:5] == ['ID', '标题', '招标编号', '预算(万)', '截止日期'], str(rows[0][:5]))
        check('leads数据行=5(种子)', len(rows) - 1 == 5, str(len(rows) - 1))
        check('中文内容正常(松材线虫)', any('松材线虫' in row[1] for row in rows[1:]))

# 2. 按 ids 筛选导出
leads = requests.get(f'{BASE}/leads', timeout=10).json()
ids = [leads[0]['id'], leads[2]['id']]
r = export('leads', ids)
rows = parse_csv(r.text) if r.status_code == 200 else []
check('按ids导出2条', r.status_code == 200 and len(rows) - 1 == 2, str(len(rows) - 1 if r.status_code == 200 else r.status_code))
check('ids筛选内容匹配', {rows[1][0], rows[2][0]} == {str(i) for i in ids}, str([rows[1][0], rows[2][0]]))

# 3. 状态映射（active→待转化）
r = export('leads')
rows = parse_csv(r.text)
status_col = rows[0].index('状态')
statuses = {row[status_col] for row in rows[1:]}
check('状态中文映射', statuses == {'待转化'}, str(statuses))

# 4. 关联数据带出（leads 行含客户名/联系人）
cust_col = rows[0].index('关联客户')
ct_col = rows[0].index('联系人')
check('线索导出带客户名', any('浙江省林业局' == row[cust_col] for row in rows[1:]))
check('线索导出带联系人', any('王处长' == row[ct_col] for row in rows[1:]))

# 5. 异常处理
r = export('notexist')
check('非法类型400', r.status_code == 400)
r = export('leads', [99999])
check('无匹配数据400+JSON错误', r.status_code == 400 and r.json().get('error') == '当前无数据可导出')

# 6. 含逗号/引号内容不破坏 CSV 结构（写一条带逗号内容的活动再导出）
requests.post(f'{BASE}/activities', json={'content': '测试,含逗号"引号"内容', 'method': '电话', 'time': '2026-08-15'}, timeout=10)
r = export('activities')
rows = parse_csv(r.text)
check('含逗号引号内容CSV结构完整', any('测试,含逗号"引号"内容' in row for row in rows[1:]), r.text[:200])

print()
print(f'════ 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 ════')
for f in FAIL:
    print('  ✗', f)
sys.exit(1 if FAIL else 0)
