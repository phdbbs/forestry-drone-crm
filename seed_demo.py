#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OPC 财务系统 — 演示数据录入（纯 API 层，模拟真实业务场景）"""
import requests, io, sys

BASE = 'http://localhost:5000/api'

def call(method, path, body=None, files=None):
    r = requests.request(method, BASE + path, json=body, files=files, timeout=15)
    return r.json()

print('── 清空旧数据 ──')
call('POST', '/clear-all')

print('── 1. 客户与联系人 ──')
r = call('POST', '/customers', {'name': '深圳绿谷科技有限公司'}); client_id = r['data']['id']
call('POST', '/contacts', {'customer_id': client_id, 'name': '王经理（采购）'})
call('POST', '/contacts', {'customer_id': client_id, 'name': '刘会计（财务）'})
r = call('POST', '/customers', {'name': '广州华宇网络设备有限公司'}); sup_id = r['data']['id']
call('POST', '/contacts', {'customer_id': sup_id, 'name': '李工（销售）'})
r = call('POST', '/customers', {'name': '佛山宏图弱电工程队'}); sup2_id = r['data']['id']
call('POST', '/contacts', {'customer_id': sup2_id, 'name': '陈队长'})

print('── 2. 项目 ──')
r = call('POST', '/projects', {'name': '绿谷园区网络建设项目', 'supplier_id': sup_id, 'client_id': client_id})
proj1 = r['data']['id']
r = call('POST', '/projects', {'name': '绿谷办公楼综合布线', 'supplier_id': sup2_id, 'client_id': client_id})
proj2 = r['data']['id']

print('── 3. 合同（附件上传） ──')
pdf = io.BytesIO('%PDF-1.4 绿谷园区设备采购合同（演示）'.encode('utf-8'))
r = call('POST', '/upload', files={'file': ('绿谷采购合同.pdf', pdf, 'application/pdf')})
call('POST', '/contracts', {'title': '华宇设备采购合同', 'customer_id': sup_id, 'project_id': proj1,
                            'amount': 150000, 'file_path': r['data']['path']})
r2 = call('POST', '/upload', files={'file': ('绿谷销售合同.pdf', io.BytesIO('%PDF-1.4 销售合同'.encode('utf-8')), 'application/pdf')})
call('POST', '/contracts', {'title': '绿谷销售合同（一期）', 'customer_id': client_id, 'project_id': proj1,
                            'amount': 400000, 'file_path': r2['data']['path']})
call('POST', '/contracts', {'title': '宏图布线分包合同', 'customer_id': sup2_id, 'project_id': proj2, 'amount': 60000})

print('── 4. 对话式录入 ──')
# 付款15万 → 已付 + 待收票
r = call('POST', '/chat/parse', {'text': '绿谷园区网络建设项目 付款给华宇 15万'})
d = r['data']
call('POST', '/chat/confirm', {'action': d['action'], 'amount': d['amount'], 'project_id': proj1,
                               'customer_id': sup_id, 'description': '设备采购款（一期）', 'date': '2026-07-05'})
# 收款30万 → 已收 + 待开票
r = call('POST', '/chat/parse', {'text': '绿谷园区网络建设项目收到绿谷科技款30万'})
d = r['data']
call('POST', '/chat/confirm', {'action': '收款', 'amount': 300000, 'project_id': proj1,
                               'customer_id': client_id, 'description': '一期进度款', 'date': '2026-07-20'})
# 开票10万 → 已开 + 待收款
r = call('POST', '/chat/parse', {'text': '2026-08-01 给绿谷科技开票100000元'})
d = r['data']
call('POST', '/chat/confirm', {'action': '开票', 'amount': 100000, 'project_id': proj1,
                               'customer_id': client_id, 'date': '2026-08-01'})
# 收票5万 → 已收票 + 待付款
r = call('POST', '/chat/parse', {'text': '收到华宇发票50000'})
d = r['data']
call('POST', '/chat/confirm', {'action': '收票', 'amount': 50000, 'project_id': proj1,
                               'customer_id': sup_id, 'date': '2026-08-08'})
# 项目2：付款6万
r = call('POST', '/chat/parse', {'text': '绿谷办公楼综合布线 付给宏图工程队 6万'})
d = r['data']
call('POST', '/chat/confirm', {'action': '付款', 'amount': 60000, 'project_id': proj2,
                               'customer_id': sup2_id, 'description': '布线分包款', 'date': '2026-07-25'})
# 项目2：收款8万
call('POST', '/chat/confirm', {'action': '收款', 'amount': 80000, 'project_id': proj2,
                               'customer_id': client_id, 'description': '布线工程款', 'date': '2026-08-10'})

print('── 5. 表单录入+状态流转 ──')
r = call('POST', '/transactions', {'type': 'expense', 'amount': 8000, 'project_id': proj1,
                                   'customer_id': sup_id, 'status': 'completed', 'date': '2026-07-15',
                                   'description': '现场辅料及杂费'})
r = call('POST', '/transactions', {'type': 'expense', 'amount': 2500, 'project_id': proj1,
                                   'customer_id': sup_id, 'status': 'completed', 'date': '2026-08-02',
                                   'description': '交通差旅'})
# 找到待收票（华宇关联），确认为已收票
invs = call('GET', f'/invoices?project_id={proj1}')['data']
for i in invs:
    if i['type'] == 'in' and i['status'] == 'pending' and i['linked_transaction_code']:
        call('PUT', f"/invoices/{i['id']}", {'status': 'completed'})
        break

print('── 6. 看板任务卡片 ──')
tasks1 = [('设备到货验收', '华宇首批设备到货，组织三方验收', ['核对装箱单', '加电测试', '性能抽检']),
          ('综合布线完工', None, ['桥架安装', '光缆敷设', '配线端接']),
          ('终验资料提交', '整理竣工资料提交业主', [])]
for title, desc, subs in tasks1:
    r = call('POST', f'/projects/{proj1}/tasks', {'title': title, 'description': desc})
    tid = r['data']['id']
    for s in subs:
        call('POST', f'/tasks/{tid}/subtasks', {'title': s})
# 勾选部分子任务（体现进度）
tasks = call('GET', f'/projects/{proj1}/tasks')['data']
call('PUT', f"/subtasks/{tasks[0]['subtasks'][0]['id']}", {'completed': True})
call('PUT', f"/subtasks/{tasks[0]['subtasks'][1]['id']}", {'completed': True})
call('PUT', f"/subtasks/{tasks[1]['subtasks'][0]['id']}", {'completed': True})
call('PUT', f"/subtasks/{tasks[1]['subtasks'][1]['id']}", {'completed': True})
call('PUT', f"/subtasks/{tasks[1]['subtasks'][2]['id']}", {'completed': True})
call('POST', f'/projects/{proj2}/tasks', {'title': '桥架安装完成确认'})
r = call('POST', f'/projects/{proj2}/tasks', {'title': '与业主对量结算'})

print('── 7. 项目2关闭（演示业务闭环守卫） ──')
# 直接关闭会被守卫拦截：还有待收票/待开票未处理
r = call('PUT', f'/projects/{proj2}', {'status': 'close'})
print(f"   守卫拦截 → {r['msg']}")
# 正确流程：先完成项目2全部挂起发票（收宏图票6万 / 给绿谷开票8万），再关闭
for i in call('GET', f'/invoices?project_id={proj2}')['data']:
    if i['status'] == 'pending':
        call('PUT', f"/invoices/{i['id']}", {'status': 'completed'})
r = call('PUT', f'/projects/{proj2}', {'status': 'close'})
print(f"   处理挂起后关闭 → {r['msg']}")

print()
print('══ 演示数据汇总 ══')
d = call('GET', '/dashboard')['data']
print(f"客户 {d['customer_count']} | 项目 {d['project_count']}（进行中 {d['project_open_count']}/已完成 {d['project_close_count']}）| 合同 {d['contract_count']}（有附件 {d['contract_yes_count']}）")
print(f"已收 {d['income_completed']:,.0f} | 已付 {d['expense_completed']:,.0f} | 净利润 {d['profit']:,.0f}")
for pid, name in [(proj1, '绿谷园区网络建设'), (proj2, '绿谷办公楼综合布线')]:
    p = call('GET', f'/projects/{pid}')['data']
    s = p['summary']
    print(f"[{'已关闭' if p['status'] == 'close' else '进行中'}] {name}: 利润 {s['profit']:,.0f} | 发票差 {s['invoice_diff']:,.0f} | 待收 {s['pending_income']:,.0f} | 待付 {s['pending_expense']:,.0f}")
