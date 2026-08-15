#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OPC 财务系统 E2E 业务场景测试（纯 API 层，不碰数据库）"""
import requests, json, sys, io

BASE = 'http://localhost:5000/api'
PASS, FAIL = [], []

def call(method, path, body=None, files=None, data=None):
    r = requests.request(method, BASE + path, json=body, files=files, data=data, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {'code': -1, 'msg': r.text[:120]}

def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗ FAIL'} {name}" + (f"  [{detail}]" if detail and not cond else ''))

def reset():
    code, j = call('POST', '/clear-all')
    assert j['code'] == 0, f'清空失败: {j}'

print('════ 阶段0：清空数据 ════')
reset()

print('════ 阶段1：客户+联系人 ════')
code, j = call('POST', '/customers', {'name': '深圳绿谷科技有限公司'})
check('创建客户方', j['code'] == 0 and j['data']['id'] > 0)
client_id = j['data']['id']

code, j = call('POST', '/customers', {'name': '广州华宇网络设备有限公司'})
sup_id = j['data']['id']
check('创建供应方', j['code'] == 0)

code, j = call('POST', '/contacts', {'customer_id': client_id, 'name': '王经理'})
check('添加联系人', j['code'] == 0)
code, j = call('POST', '/contacts', {'customer_id': sup_id, 'name': '李工'})
check('添加联系人2', j['code'] == 0)

code, j = call('POST', '/customers', {'name': ''})
check('空客户名被拒', j['code'] != 0, j.get('msg'))

print('════ 阶段2：项目 ════')
code, j = call('POST', '/projects', {'name': '绿谷园区网络建设项目', 'supplier_id': sup_id, 'client_id': client_id})
check('创建项目(自动编号)', j['code'] == 0 and j['data']['code'].startswith('P'))
proj_id = j['data']['id']

code, j = call('POST', '/projects', {'name': '测试空项目'})
empty_proj = j['data']['id']
check('创建空项目', j['code'] == 0)

print('════ 阶段3：合同（附件上传） ════')
fake_pdf = io.BytesIO(b'%PDF-1.4 fake contract content')
code, j = call('POST', '/upload', files={'file': ('华宇采购合同.pdf', fake_pdf, 'application/pdf')})
check('上传合同附件', j['code'] == 0 and j['data'].get('path'), json.dumps(j, ensure_ascii=False)[:100])
file_path = j['data']['path'] if j['code'] == 0 else None

code, j = call('POST', '/contracts', {'title': '华宇设备采购合同', 'customer_id': sup_id,
                                      'project_id': proj_id, 'amount': 150000, 'file_path': file_path})
check('创建合同(有附件→状态有)', j['code'] == 0 and j['data']['status'] == '有')
contract1 = j['data']['id']

code, j = call('POST', '/contracts', {'title': '绿谷销售合同', 'customer_id': client_id, 'project_id': proj_id, 'amount': 400000})
check('创建合同(无附件→状态无)', j['code'] == 0 and j['data']['status'] == '无')

code, j = call('GET', f'/projects/{proj_id}')
ci = j['data']['contract_info']
check('项目合同情况:供方有/需方有', ci['supplier_contract'] == '有' and ci['client_contract'] == '有', json.dumps(ci))

print('════ 阶段4：对话录入（语义识别+双记录关联） ════')
# 4.1 付款 → 已付 + 待收票
code, j = call('POST', '/chat/parse', {'text': '绿谷园区网络建设项目 付款给华宇 15万'})
r = j['data']
check('parse付款: 识别action/金额/项目', r['action'] == '付款' and r['amount'] == 150000 and r['project_id'] == proj_id,
      json.dumps({k: r.get(k) for k in ('action', 'amount', 'project_id', 'needs_confirm')}, ensure_ascii=False))
code, j = call('POST', '/chat/confirm', {'action': r['action'], 'amount': r['amount'], 'project_id': r['project_id'],
                                          'customer_id': sup_id, 'description': r['description'], 'date': r['date']})
items = j['data']['items']
pay_t, pay_inv = items[0]['data'], items[1]['data']
check('confirm付款→双记录', j['code'] == 0 and len(items) == 2)
check('付款=已付(completed)', pay_t['status'] == 'completed')
check('关联发票=待收票(pending)', pay_inv['status'] == 'pending' and pay_inv['type'] == 'in')
check('双向关联 t.linked_invoice', pay_t['linked_invoice_id'] == pay_inv['id'])
code, j = call('GET', f"/invoices/{pay_inv['id']}")
check('双向关联 inv.linked_transaction', j['data']['linked_transaction_id'] == pay_t['id'])

# 4.2 收款 → 已收 + 待开票
code, j = call('POST', '/chat/parse', {'text': '绿谷园区网络建设项目收到绿谷科技款30万'})
r = j['data']
check('parse收款含干扰词', r['action'] == '收款' and r['amount'] == 300000, f"action={r['action']} amount={r['amount']}")
code, j = call('POST', '/chat/confirm', {'action': '收款', 'amount': 300000, 'project_id': proj_id,
                                          'customer_id': client_id, 'description': '一期款', 'date': '2026-08-10'})
recv_t, recv_inv = j['data']['items'][0]['data'], j['data']['items'][1]['data']
check('收款=已收+待开票', recv_t['status'] == 'completed' and recv_inv['status'] == 'pending' and recv_inv['type'] == 'out')

# 4.3 开票 → 已开 + 待收款
code, j = call('POST', '/chat/parse', {'text': '2026-08-12 给绿谷科技开票100000元'})
r = j['data']
check('parse开票(日期+元)', r['action'] == '开票' and r['amount'] == 100000 and r['date'] == '2026-08-12',
      f"action={r['action']} amount={r['amount']} date={r['date']}")
code, j = call('POST', '/chat/confirm', {'action': '开票', 'amount': 100000, 'project_id': proj_id,
                                          'customer_id': client_id, 'date': r['date']})
inv_out, t_pend = j['data']['items'][0]['data'], j['data']['items'][1]['data']
check('开票=已开+待收款', inv_out['status'] == 'completed' and t_pend['status'] == 'pending' and t_pend['type'] == 'income')

# 4.4 收票 → 已收票 + 待付款
code, j = call('POST', '/chat/parse', {'text': '收到华宇发票50000'})
r = j['data']
check('parse收票(纯数字)', r['action'] == '收票' and r['amount'] == 50000, f"action={r['action']} amount={r['amount']}")
code, j = call('POST', '/chat/confirm', {'action': '收票', 'amount': 50000, 'project_id': proj_id, 'customer_id': sup_id})
inv_in, t_pay2 = j['data']['items'][0]['data'], j['data']['items'][1]['data']
check('收票=已收票+待付款', inv_in['status'] == 'completed' and t_pay2['status'] == 'pending' and t_pay2['type'] == 'expense')

print('════ 阶段5：表单录入+状态流转 ════')
code, j = call('POST', '/transactions', {'type': 'expense', 'amount': 8000, 'project_id': proj_id,
                                          'customer_id': sup_id, 'status': 'pending', 'description': '杂费'})
check('表单建应付', j['code'] == 0)
misc_t = j['data']['id']
code, j = call('PUT', f'/transactions/{misc_t}', {'status': 'completed'})
check('应付→已付', j['code'] == 0 and j['data']['status'] == 'completed')
code, j = call('PUT', f'/invoices/{pay_inv["id"]}', {'status': 'completed'})
check('待收票→已收票', j['code'] == 0 and j['data']['status'] == 'completed')

print('════ 阶段6：看板任务卡片 ════')
code, j = call('POST', f'/projects/{proj_id}/tasks', {'title': '设备到货验收'})
task1 = j['data']['id']
check('建任务1', j['code'] == 0)
code, j = call('POST', f'/projects/{proj_id}/tasks', {'title': '综合布线完工', 'description': '三期全部完成'})
task2 = j['data']['id']
code, j = call('POST', f'/projects/{proj_id}/tasks', {'title': '终验提交'})
task3 = j['data']['id']
code, j = call('POST', f'/tasks/{task1}/subtasks', {'title': '核对装箱单'})
sub1 = j['data']['id']
code, j = call('POST', f'/tasks/{task1}/subtasks', {'title': '加电测试'})
sub2 = j['data']['id']
check('建子任务', j['code'] == 0)
code, j = call('PUT', f'/subtasks/{sub1}', {'completed': True})
check('勾选子任务', j['code'] == 0 and j['data']['completed'] is True)
code, j = call('POST', f'/tasks/{task3}/move', {'direction': 'up'})
check('任务上移(task3↔task2)', j['code'] == 0)
code, j = call('GET', f'/projects/{proj_id}/tasks')
order = [t['id'] for t in j['data']]
check('排序结果[1,3,2]', order == [task1, task3, task2], str(order))
code, j = call('POST', f'/tasks/{task1}/move', {'direction': 'swap', 'target_id': task2})
check('拖拽swap交换', j['code'] == 0)
code, j = call('GET', f'/projects/{proj_id}/tasks')
top_task = j['data'][0]['id']
code, j = call('POST', f'/tasks/{top_task}/move', {'direction': 'up'})
check('首任务上移=边界容忍', j['code'] == 0 and '边界' in j['msg'], j.get('msg', ''))
code, j = call('GET', '/kanban')
cols = j['data']['open']
proj_in_kb = next(p for p in cols if p['id'] == proj_id)
check('看板返回任务+进度', len(proj_in_kb['tasks']) == 3)

print('════ 阶段7：财务汇总验证 ════')
code, j = call('GET', f'/projects/{proj_id}')
s = j['data']['summary']
check('已收=300000', s['income'] == 300000, str(s['income']))
check('已付=158000', s['expense'] == 158000, str(s['expense']))
check('待收=100000', s['pending_income'] == 100000, str(s['pending_income']))
check('待付=50000', s['pending_expense'] == 50000, str(s['pending_expense']))
check('利润=192000(进行中按收支)', s['profit'] == 300000 - 158000 + 100000 - 50000, str(s['profit']))
check('已开票=100000', s['invoice_out'] == 100000, str(s['invoice_out']))
check('已收票=200000', s['invoice_in'] == 200000, str(s['invoice_in']))
check('待开票=300000', s['pending_invoice_out'] == 300000, str(s['pending_invoice_out']))
check('待收票=0', s['pending_invoice_in'] == 0, str(s['pending_invoice_in']))
check('发票差=200000', s['invoice_diff'] == 100000 - 200000 + 300000 - 0, str(s['invoice_diff']))
invoice_diff = s['invoice_diff']

code, j = call('PUT', f'/projects/{proj_id}', {'status': 'close'})
s2 = j['data']['summary']
check('关闭后利润=发票差', s2['profit'] == invoice_diff, f"profit={s2['profit']} diff={invoice_diff}")
code, j = call('PUT', f'/projects/{proj_id}', {'status': 'open'})
check('重新打开恢复收支利润', j['data']['summary']['profit'] == 192000)

print('════ 阶段8：仪表盘联动 ════')
code, j = call('GET', '/dashboard')
d = j['data']
check('仪表盘已收=300000', d['income_completed'] == 300000, str(d['income_completed']))
check('仪表盘净利润=142000', d['profit'] == 300000 - 158000, str(d['profit']))
check('项目计数=2', d['project_count'] == 2)
check('合同有附件=1', d['contract_yes_count'] == 1 and d['contract_no_count'] == 1)

print('════ 阶段9：边界与异常 ════')
code, j = call('POST', '/transactions', {'type': 'income', 'amount': -100})
check('负数金额被拒', j['code'] != 0, f"code={j['code']} msg={j.get('msg')}")
code, j = call('POST', '/transactions', {'type': 'income'})
check('缺失金额被拒', j['code'] != 0, f"code={j['code']} msg={j.get('msg')}")
code, j = call('POST', '/invoices', {'type': 'out', 'amount': 0})
check('零金额被拒', j['code'] != 0, f"code={j['code']} msg={j.get('msg')}")
code, j = call('POST', '/chat/confirm', {'action': '收款', 'amount': -50})
check('对话负数金额被拒', j['code'] != 0)

code, j = call('POST', '/chat/parse', {'text': '2026-08-15 付款3000'})
r = j['data']
check('日期数字不误识别金额', r['amount'] == 3000, f"amount={r['amount']}")
code, j = call('POST', '/chat/parse', {'text': '今天收了一笔款没有说金额'})
r = j['data']
check('无金额→needs_confirm', r['needs_confirm'] and r['amount'] is None)
code, j = call('POST', '/chat/parse', {'text': '张三明天来公司'})
r = j['data']
check('无动作→needs_confirm', r['needs_confirm'] and not r['action'])

code, j = call('POST', '/chat/confirm', {'action': '打款', 'amount': 100})
check('非法action被拒', j['code'] != 0)

code, j = call('POST', f'/projects/{empty_proj}/tasks', {'title': '临时任务'})
tmp_task = j['data']['id']
code, j = call('DELETE', f'/projects/{empty_proj}')
check('删除有任务的项目成功', j['code'] == 0, j.get('msg', ''))
code, j = call('GET', f'/projects/{proj_id}')
check('主项目不受影响', j['code'] == 0)

code, j = call('DELETE', f'/transactions/{t_pend["id"]}')
check('删除被关联收支', j['code'] == 0, j.get('msg', ''))
code, j = call('GET', f"/invoices/{inv_out['id']}")
check('发票引用已清理', j['data']['linked_transaction_id'] is None, str(j['data']['linked_transaction_id']))

code, j = call('DELETE', f'/customers/{client_id}')
check('删除关联客户被拒', j['code'] != 0)

code, j = call('DELETE', f'/projects/{proj_id}')
check('删除关联项目被拒', j['code'] != 0)

code, j = call('POST', '/projects', {'name': 'X', 'code': 'P0001'})
check('重复项目编号被拒', j['code'] != 0, j.get('msg', ''))

code, j = call('GET', '/projects/99999')
check('404返回JSON', j['code'] != 0 and '不存在' in j['msg'])
code, j = call('PUT', '/subtasks/99999', {'completed': True})
check('子任务404', j['code'] != 0)

print()
print(f'════ 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 ════')
if FAIL:
    print('失败项：')
    for f in FAIL:
        print('  ✗', f)
sys.exit(1 if FAIL else 0)
