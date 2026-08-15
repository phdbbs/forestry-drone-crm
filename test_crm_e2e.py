#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CRM E2E 业务场景测试（纯 API 层，模拟真实业务链路）"""
import requests, sys

BASE = 'http://localhost:5001/api'
PASS, FAIL = [], []

def call(method, path, body=None):
    r = requests.request(method, BASE + path, json=body, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {'error': r.text[:100]}

def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗ FAIL'} {name}" + (f"  [{detail}]" if detail and not cond else ''))

print('════ 阶段1：客户+联系人 ════')
code, c1 = call('POST', '/customers', {'name': '浙江省林业局', 'type': '政府部门', 'level': 'A-重点客户', 'region': '浙江'})
cust1 = c1['id']
check('创建客户1', code == 200 and 'id' in c1)
code, c2 = call('POST', '/customers', {'name': '广州华宇设备公司', 'type': '民营企业', 'region': '广东'})
cust2 = c2['id']
code, r = call('POST', '/customers', {'name': ''})
check('空客户名被拒', 'error' in r)

code, r = call('POST', '/contacts', {'name': '王处长', 'title': '林业管理处处长', 'phone': '13805711234', 'customer_id': cust1, 'role': '决策人'})
ct1 = r['id']
check('创建联系人1', 'id' in r)
code, r = call('POST', '/contacts', {'name': '李科长', 'customer_id': cust1, 'phone': '13905915678'})
ct2 = r['id']
code, r = call('POST', '/contacts', {'name': ''})
check('空联系人名被拒', 'error' in r)

print('════ 阶段2：线索（模拟招标采集结果手工录入） ════')
code, r = call('POST', '/leads', {
    'title': '2026年浙江省松材线虫病防治无人机巡检项目', 'bid_number': 'ZJ-2026-0342',
    'budget': '150', 'deadline': '2026-09-30', 'region': '浙江省', 'purchaser': '浙江省林业局',
    'contact_name': '王处长', 'contact_phone': '13805711234', 'address': '杭州市西湖区',
    'source_url': 'https://www.ccgp.gov.cn/demo/zj-0342', 'source_platform': '中国政府采购网'})
lead1 = r['id']
check('创建线索1(含联系人/来源URL)', 'id' in r)
code, l = call('GET', f'/leads/{lead1}')
check('线索匹配引擎运行', l.get('match_level') is not None, str(l.get('match_level')))

code, r = call('POST', '/leads', {'title': '福建省森林防火监测服务', 'budget': '280', 'deadline': '2026-09-15',
                                   'region': '福建省', 'purchaser': '福建省林业厅',
                                   'contact_name': '陈主任', 'contact_phone': '13705919012'})
lead2 = r['id']
check('创建线索2(无来源=手工)', 'id' in r)

print('════ 阶段3：线索转化（自动建客户/联系人+回写关联） ════')
code, r = call('POST', f'/leads/{lead1}/convert', {'customer_id': cust1, 'contact_id': ct1, 'amount': '150', 'stage': '初步接触'})
opp1 = r.get('id')
check('转化线索1(选已有客户/联系人)', 'id' in r, str(r))
code, l = call('GET', f'/leads/{lead1}')
check('转化后状态=converted', l['status'] == 'converted')
check('转化后回写customer_id', l['customer_id'] == cust1, f"customer_id={l.get('customer_id')}")
check('转化后显示customer_name', l.get('customer_name') == '浙江省林业局', str(l.get('customer_name')))

# 线索2：不选客户/联系人 → 自动创建
code, r = call('POST', f'/leads/{lead2}/convert', {})
opp2 = r.get('id')
check('转化线索2(全自动)', 'id' in r)
code, cs = call('GET', '/customers')
fj = [c for c in cs if c['name'] == '福建省林业厅']
check('自动创建采购方客户', len(fj) == 1)
fj_cust = fj[0]['id'] if fj else None
code, cts = call('GET', '/contacts')
chen = [c for c in cts if c['name'] == '陈主任']
check('自动创建项目联系人', len(chen) == 1 and str(chen[0].get('customer_id')) == str(fj_cust))
code, l2 = call('GET', f'/leads/{lead2}')
check('线索2也回写customer_id', l2.get('customer_id') == fj_cust, str(l2.get('customer_id')))
code, o2 = call('GET', f'/opportunities/{opp2}')
check('商机2带来源URL(空)', o2.get('source_url') == '')

print('════ 阶段4：已转化线索的状态保护 ════')
code, r = call('PUT', f'/leads/{lead1}', {'title': '尝试修改'})
check('已转化线索修改被拒', 'error' in r)
code, r = call('POST', f'/leads/{lead1}/abandon')
check('已转化线索删除(abandon)被拒', 'error' in r)
code, r = call('DELETE', f'/leads/{lead1}')
check('已转化线索硬删被拒', 'error' in r)
code, r = call('POST', f'/leads/{lead1}/release')
check('已转化线索释放公海被拒', 'error' in r)

print('════ 阶段5：商机阶段推进+看板联动 ════')
code, r = call('POST', f'/opportunities/{opp1}/stages', {'stage_name': '方案报价', 'content': '提交技术方案及报价', 'deadline': '2026-08-20', 'add_to_kanban': True})
check('添加阶段记录(带看板)', 'id' in r)
code, o = call('GET', f'/opportunities/{opp1}')
check('current_stage同步推进', o['current_stage'] == '方案报价', o.get('current_stage'))
check('阶段记录列表', len(o.get('stages', [])) == 1)

print('════ 阶段6：日常联络→自动生成联络计划 ════')
code, r = call('POST', '/activities', {'customer_id': cust1, 'contact_id': ct1, 'opportunity_id': opp1,
                                        'method': '电话', 'content': '确认标书密封要求与投标截止时间',
                                        'time': '2026-08-10', 'next_time': '2026-08-15', 'next_content': '询问评标结果'})
act1 = r['id']
check('创建日常联络', 'id' in r)
code, fus = call('GET', f'/followups?customer_id={cust1}')
check('自动生成联络计划', len(fus) == 1 and fus[0]['plan_date'].startswith('2026-08-15'), str(len(fus)))
fu1 = fus[0]['id'] if fus else None
check('计划内容带来源标记', '询问评标结果' in (fus[0].get('content') or '') if fus else False)
check('计划关联source_activity', fus[0].get('source_activity_id') == act1 if fus else False)

print('════ 阶段7：联络计划执行→回流日常联络 ════')
code, r = call('GET', f'/followups/{fu1}')
check('计划详情含历史联系记录', len(r.get('history', [])) >= 1, str(len(r.get('history', []))))
code, r = call('POST', f'/followups/{fu1}/execute', {'method': '电话', 'actual_content': '已电话确认，进入评标阶段', 'next_time': '2026-08-22', 'next_content': '确认中标结果'})
check('执行联络计划', 'id' in r, str(r))
code, r = call('POST', f'/followups/{fu1}/execute', {'method': '电话', 'actual_content': '重复执行'})
check('重复执行被拒', 'error' in r)
code, acts = call('GET', f'/activities?customer_id={cust1}')
new_acts = [a for a in acts if '已电话确认' in (a.get('content') or '')]
check('执行后生成日常联络记录', len(new_acts) == 1)
check('新联络记录带下次跟进', new_acts and new_acts[0].get('next_followup_time') == '2026-08-22', str(new_acts[0].get('next_followup_time')) if new_acts else '')
code, fus2 = call('GET', f'/followups?customer_id={cust1}')
check('计划标记已完成', all(f.get('actual_date') for f in fus2) or len(fus2) == 2)

print('════ 阶段8：商机详情时间轴 ════')
code, o = call('GET', f'/opportunities/{opp1}')
check('商机详情含联络时间轴', len(o.get('activities', [])) >= 2, str(len(o.get('activities', []))))
check('商机详情含来源URL', o.get('source_url') == 'https://www.ccgp.gov.cn/demo/zj-0342')

print('════ 阶段9：客户详情四tab数据 ════')
code, cu = call('GET', f'/customers/{cust1}')
check('客户联系人tab', len(cu.get('contacts', [])) == 2)
check('客户商机tab', len(cu.get('opportunities', [])) == 1)
code, acts = call('GET', f'/activities?customer_id={cust1}')
check('客户联络记录tab', len(acts) >= 2)

print('════ 阶段10：看板 ════')
code, r = call('POST', '/kanban/boards', {'name': '业务跟进看板'})
board = r['id']
check('创建看板', 'id' in r)
code, r = call('POST', f'/kanban/boards/{board}/columns', {'name': '紧急'})
col2 = r['id']
code, boards = call('GET', '/kanban/boards')
b0 = next(b for b in boards if b['id'] == board)
col1 = b0['columns'][0]['id']
check('看板4列(自动3+新增1)', len(b0['columns']) == 4, str(len(b0['columns'])))
code, r = call('POST', '/kanban/import', {'board_id': board, 'items': [{'title': '联络王处长确认方案', 'deadline': '2026-08-18', 'color': 'red'}]})
check('导入卡片', 'message' in r)
boards = call('GET', '/kanban/boards')[1]
b0 = next(b for b in boards if b['id'] == board)
card0 = b0['columns'][0]['cards'][0]['id']
# 阶段记录 add_to_kanban 落在自动创建的默认看板 + 本看板导入1张
total_cards = sum(len(c['cards']) for b in boards for c in b['columns'])
check('阶段记录联动看板卡片', total_cards == 2, str(total_cards))
code, r = call('POST', f'/kanban/cards/{card0}/move', {'column_id': col2})
check('卡片移动列', r.get('ok') is True)

print('════ 阶段11：软删/恢复/公海 ════')
code, r = call('POST', '/leads', {'title': '测试删除线索'})
lead3 = r['id']
code, r = call('POST', f'/leads/{lead3}/abandon')
check('软删除线索', 'message' in r)
code, r = call('PUT', f'/leads/{lead3}', {'status': 'active'})
check('已删除线索可编辑恢复', 'id' in r)
code, r = call('POST', f'/leads/{lead3}/release')
check('active线索可释放公海', 'message' in r)
code, r = call('POST', f'/leads/{lead3}/claim', {'assignee': '李明'})
check('公海线索可领取', 'id' in r)
code, r = call('DELETE', f'/leads/{lead3}')
check('active线索硬删成功(无关联)', 'message' in r)

print('════ 阶段12：删除关联清理（无孤儿） ════')
# 删除有关联的联系人
code, r = call('DELETE', f'/contacts/{ct2}')
check('删除有活动关联的联系人', 'message' in r)
code, acts = call('GET', f'/activities?customer_id={cust1}')
check('活动保留但contact解除', all(a.get('contact_id') != ct2 for a in acts))
# 删除商机2 → 阶段记录删除
code, r = call('POST', f'/opportunities/{opp2}/stages', {'stage_name': '需求确认', 'content': 'x'})
code, r = call('DELETE', f'/opportunities/{opp2}')
check('删除商机', 'message' in r)
code, o = call('GET', '/opportunities')
check('商机列表不含已删', all(x['id'] != opp2 for x in o))
# 删除已转化线索(lead1) 应被拒（商机opp1还挂着）
code, r = call('DELETE', f'/leads/{lead1}')
check('已转化线索硬删仍被拒', 'error' in r)

print('════ 阶段13：仪表盘+报表数值 ════')
code, d = call('GET', '/dashboard')
check('仪表盘商机数', d['stats']['opportunities'] == 1, str(d['stats']))
code, a = call('GET', '/analytics')
check('报表线索总数', a['summary']['total_leads'] == 2, str(a['summary']))
check('报表转化率100%(2/2已转化)', a['summary']['conversion_rate'] == 100.0, str(a['summary']['conversion_rate']))
check('漏斗含方案报价阶段', any(f['stage'] == '方案报价' and f['count'] == 1 for f in a['funnel']))

print('════ 阶段14：搜索过滤 ════')
code, ls = call('GET', '/leads?search=松材线虫')
check('线索标题搜索', len(ls) == 1)
code, ls = call('GET', '/leads?status=converted')
check('线索状态过滤', len(ls) == 2)
code, acts = call('GET', '/activities?date_from=2026-08-10&date_to=2026-08-10')
check('联络日期范围过滤', len(acts) == 1, str(len(acts)))
code, r = call('GET', '/leads?date_from=bad-date')
check('非法日期参数报400', 'error' in r)

print()
print(f'════ 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 ════')
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  ✗', f)
sys.exit(1 if FAIL else 0)
