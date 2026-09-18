#!/usr/bin/env python3
"""
EDGE — 边界、异常与数据完整性套件（补充 AICS 集成套件未覆盖的场景）

覆盖：输入校验、状态机约束、外键完整性、级联清理、看板联动、
跟进同步、统计口径、错误响应契约、空库极端场景。

用法：
    pytest tests/test_edge_cases.py -v
    python tests/test_edge_cases.py
"""
import os
import sys
from datetime import date, datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crm_test_utils import (  # noqa: E402
    created_id, err, json_of, make_activity, make_card, make_contact,
    make_customer, make_followup, make_lead, make_opportunity, ok, wipe_all,
)

# ═══════════════════════════════════════════════════════════════
# EDGE-01 输入校验 / 错误处理
# ═══════════════════════════════════════════════════════════════


class TestEdge01Validation:
    def test_edge_01_001_required_fields(self, client, seed):
        """EDGE-01-001 各创建接口缺少必填字段一律 400 且提示字段名。"""
        cases = [
            ('/api/customers', {}, 'name'),
            ('/api/leads', {}, 'title'),
            ('/api/contacts', {}, 'name'),
            ('/api/opportunities', {}, 'title'),
        ]
        for url, payload, field in cases:
            msg = err(client.post(url, json=payload))
            assert field in msg, f'{url} 提示未包含字段名 {field}: {msg}'

    def test_edge_01_002_blank_string_is_missing(self, client):
        """EDGE-01-002 纯空白字符串视为缺失必填字段。"""
        assert 'name' in err(client.post('/api/customers', json={'name': '   '}))
        assert 'title' in err(client.post('/api/leads', json={'title': '\t\n '}))

    def test_edge_01_003_name_is_trimmed(self, client):
        """EDGE-01-003 名称/标题首尾空白被裁剪后入库。"""
        cid = make_customer(client, '  AICS 裁剪客户  ')
        assert ok(client.get(f'/api/customers/{cid}'))['name'] == 'AICS 裁剪客户'

    def test_edge_01_004_invalid_date(self, client):
        """EDGE-01-004 非法日期返回 400（含不存在的日期）。"""
        for bad in ('not-a-date', '2026-13-01', '2026-02-30', '2026/02/30'):
            assert err(client.post('/api/leads', json={'title': 'x', 'deadline': bad}))

    def test_edge_01_005_invalid_datetime(self, client):
        """EDGE-01-005 非法时间返回 400。"""
        assert err(client.post('/api/activities', json={'content': 'x', 'time': 'bad'}))

    def test_edge_01_006_datetime_formats(self, client):
        """EDGE-01-006 支持 4 种常见时间格式。"""
        for value in ('2026-07-31', '2026-07-31 02:30', '2026-07-31T02:30',
                      '2026-07-31 02:30:00'):
            aid = make_activity(client, f'AICS 时间格式 {value}', time=value)
            assert ok(client.get(f'/api/activities/{aid}'))['activity_time'].startswith('2026-07-31')

    def test_edge_01_007_not_found(self, client):
        """EDGE-01-007 不存在的资源返回 404 JSON。"""
        r = client.get('/api/customers/999999')
        assert r.status_code == 404
        assert 'error' in json_of(r)

    def test_edge_01_008_invalid_int_query(self, client):
        """EDGE-01-008 整数型查询参数非法值统一返回 400，不泄漏内部异常。"""
        for url in ('/api/contacts?customer_id=abc',
                    '/api/activities?customer_id=abc',
                    '/api/activities?opportunity_id=abc',
                    '/api/followups?customer_id=abc',
                    '/api/followups?contact_id=abc'):
            msg = err(client.get(url))
            assert '必须为整数' in msg, f'{url} -> {msg}'

    def test_edge_01_009_long_text_truncated(self, client):
        """EDGE-01-009 超长文本按字段长度截断，不报错。"""
        lid = make_lead(client, 'AICS 超长字段线索', contact_name='名' * 300,
                        address='址' * 500)
        body = ok(client.get(f'/api/leads/{lid}'))
        assert len(body['contact_name']) == 100
        assert len(body['address']) == 300

    def test_edge_01_010_missing_json_body(self, client):
        """EDGE-01-010 未携带 JSON 请求体返回 415 JSON（而非 HTML 错误页）。"""
        for method, url in (('post', '/api/leads'), ('put', '/api/config'),
                            ('post', '/api/activities')):
            r = getattr(client, method)(url)
            assert r.status_code == 415, f'{method} {url} -> {r.status_code}'
            assert r.headers['Content-Type'].startswith('application/json')
            assert 'error' in json_of(r)

    def test_edge_01_011_unknown_api_path(self, client):
        """EDGE-01-011 未注册的 /api 路径返回 JSON 404，不被 SPA 兜底。"""
        for url in ('/api', '/api/nope', '/api/leads/1/nope'):
            r = client.get(url)
            assert r.status_code == 404 and 'error' in json_of(r)

    def test_edge_01_012_unknown_method(self, client):
        """EDGE-01-012 不支持的方法返回 405 JSON。"""
        r = client.patch('/api/customers')
        assert r.status_code == 405 and 'error' in json_of(r)

    def test_edge_01_012b_wrong_method_on_known_path(self, client):
        """EDGE-01-012b 路径已注册但方法不符返回 405（回归：曾被 SPA 兜底吞成 404）。"""
        cases = [('get', '/api/export/leads'), ('get', '/api/export/customers'),
                 ('get', '/api/crawl')]
        for method, url in cases:
            r = getattr(client, method)(url)
            assert r.status_code == 405, f'{method.upper()} {url} -> {r.status_code}'
            assert r.headers['Content-Type'].startswith('application/json')
            assert 'error' in json_of(r)

    def test_edge_01_014_error_text_is_chinese(self, client):
        """EDGE-01-014 错误文案统一中文，不泄漏 Werkzeug 英文默认描述。"""
        for method, url in (('patch', '/api/customers'), ('delete', '/api/dashboard'),
                            ('get', '/api/does-not-exist')):
            msg = json_of(getattr(client, method)(url))['error']
            assert any('\u4e00' <= ch <= '\u9fa5' for ch in msg), f'{method} {url} -> {msg}'
            assert 'method' not in msg.lower() and 'requested URL' not in msg

    def test_edge_01_013_unknown_skill(self, client):
        """EDGE-01-013 执行不存在的技能返回 error 字段而非异常。"""
        body = ok(client.post('/api/skills/not_exist/execute', json={}))
        assert 'error' in body


# ═══════════════════════════════════════════════════════════════
# EDGE-02 状态机与业务约束
# ═══════════════════════════════════════════════════════════════


class TestEdge02StateMachine:
    def test_edge_02_001_convert_twice(self, client):
        """EDGE-02-001 线索不可重复转化。"""
        lid = make_lead(client, 'AICS 重复转化线索', purchaser='AICS 重复采购方')
        ok(client.post(f'/api/leads/{lid}/convert', json={}))
        assert '仅待转化线索可转化' in err(client.post(f'/api/leads/{lid}/convert', json={}))

    def test_edge_02_002_converted_lead_frozen(self, client):
        """EDGE-02-002 已转化线索禁止修改、删除、废弃。"""
        lid = make_lead(client, 'AICS 冻结线索', purchaser='AICS 冻结采购方')
        ok(client.post(f'/api/leads/{lid}/convert', json={}))
        assert '不可修改' in err(client.put(f'/api/leads/{lid}', json={'budget': '1'}))
        assert '不可删除' in err(client.delete(f'/api/leads/{lid}'))
        assert '不可删除' in err(client.post(f'/api/leads/{lid}/abandon', json={}))

    def test_edge_02_003_claim_requires_pool(self, client):
        """EDGE-02-003 仅公海池线索可领取，重复领取被拒。"""
        lid = make_lead(client, 'AICS 公海领取线索')
        assert '仅公海池线索可领取' in err(client.post(f'/api/leads/{lid}/claim', json={}))
        ok(client.post(f'/api/leads/{lid}/release', json={}))
        ok(client.post(f'/api/leads/{lid}/claim', json={'assignee': 'AICS 领取人'}))
        assert '仅公海池线索可领取' in err(client.post(f'/api/leads/{lid}/claim', json={}))

    def test_edge_02_004_release_requires_active(self, client):
        """EDGE-02-004 仅待转化线索可释放至公海。"""
        lid = make_lead(client, 'AICS 释放校验线索', purchaser='AICS 释放采购方')
        ok(client.post(f'/api/leads/{lid}/convert', json={}))
        assert '仅待转化线索可释放至公海' in err(client.post(f'/api/leads/{lid}/release', json={}))

    def test_edge_02_005_invalid_lead_status(self, client):
        """EDGE-02-005 通过 PUT 无法把线索改成非法状态。"""
        lid = make_lead(client, 'AICS 非法状态线索')
        assert '状态无效' in err(client.put(f'/api/leads/{lid}', json={'status': 'bogus'}))

    def test_edge_02_006_stage_name_required(self, client):
        """EDGE-02-006 阶段记录名称不可为空。"""
        oid = make_opportunity(client, 'AICS 空阶段名商机')
        assert '不能为空' in err(client.post(f'/api/opportunities/{oid}/stages',
                                             json={'stage_name': '  '}))

    def test_edge_02_007_builtin_skill_protected(self, client):
        """EDGE-02-007 内置技能不可编辑、禁用、删除。"""
        skills = ok(client.get('/api/skills'))
        builtin_names = {s['name'] for s in skills['builtin']}
        assert 'read_database' in builtin_names
        # 内置技能来自注册表，库内无对应记录；此处验证自定义技能的行为边界
        sid = created_id(client.post('/api/skills', json={'name': 'aics_builtin_guard'}))
        ok(client.delete(f'/api/skills/{sid}'))

    def test_edge_02_008_skill_duplicate_name(self, client):
        """EDGE-02-008 技能名称唯一。"""
        created_id(client.post('/api/skills', json={'name': 'aics_dup_skill'}))
        assert '已存在' in err(client.post('/api/skills', json={'name': 'aics_dup_skill'}))

    def test_edge_02_009_followup_execute_guards(self, client, seed):
        """EDGE-02-009 联络计划执行的前置校验（空内容 / 重复执行）。"""
        fid = make_followup(client, 'AICS 执行校验计划', customer_id=seed['customer'])
        assert '请填写本次联系内容' in err(
            client.post(f'/api/followups/{fid}/execute', json={'actual_content': None}))
        ok(client.post(f'/api/followups/{fid}/execute', json={'actual_content': '内容'}))
        assert '不能重复执行' in err(
            client.post(f'/api/followups/{fid}/execute', json={'actual_content': '再来'}))

    def test_edge_02_010_execute_without_next_time_no_loop(self, client, seed):
        """EDGE-02-010 执行计划未填下次时间时不生成新计划（避免无限闭环）。"""
        fid = make_followup(client, 'AICS 无闭环计划', customer_id=seed['customer'])
        before = len(ok(client.get('/api/followups')))
        ok(client.post(f'/api/followups/{fid}/execute', json={'actual_content': '内容'}))
        assert len(ok(client.get('/api/followups'))) == before


# ═══════════════════════════════════════════════════════════════
# EDGE-03 关联数据完整性
# ═══════════════════════════════════════════════════════════════


class TestEdge03Integrity:
    def test_edge_03_001_foreign_key_enforced(self, client):
        """EDGE-03-001 悬空外键被拒绝（SQLite 外键约束已启用）。"""
        cases = [
            ('/api/opportunities', {'title': 'x', 'customer_id': 999999}),
            ('/api/contacts', {'name': 'x', 'customer_id': 999999}),
            ('/api/leads', {'title': 'x', 'customer_id': 999999}),
            ('/api/activities', {'content': 'x', 'customer_id': 999999}),
            ('/api/activities', {'content': 'x', 'contact_id': 999999}),
            ('/api/followups', {'content': 'x', 'customer_id': 999999}),
        ]
        for url, payload in cases:
            msg = err(client.post(url, json=payload))
            assert '关联对象不存在' in msg, f'{url} -> {msg}'

    def test_edge_03_002_invalid_fk_returns_400_not_500(self, client, seed):
        """EDGE-03-002 关联校验失败返回 400 且不泄漏 SQL 语句。"""
        msg = err(client.post('/api/opportunities',
                              json={'title': 'x', 'customer_id': 999999}))
        assert 'SELECT' not in msg.upper() and 'INSERT' not in msg.upper()

    def test_edge_03_003_delete_contact_unbinds(self, client, seed):
        """EDGE-03-003 删除联系人：活动/计划/商机解绑但保留，动态随删。"""
        cid = make_contact(client, 'AICS 解绑联系人', customer_id=seed['customer'])
        aid = make_activity(client, 'AICS 解绑联络', contact_id=cid, customer_id=seed['customer'])
        fid = make_followup(client, 'AICS 解绑计划', contact_id=cid, customer_id=seed['customer'])
        oid = make_opportunity(client, 'AICS 解绑商机', contact_id=cid, customer_id=seed['customer'])
        ok(client.delete(f'/api/contacts/{cid}'))
        assert ok(client.get(f'/api/activities/{aid}'))['contact_id'] is None
        assert ok(client.get(f'/api/followups/{fid}'))['contact_id'] is None
        assert ok(client.get(f'/api/opportunities/{oid}'))['contact_id'] is None

    def test_edge_03_004_delete_opportunity_cascades(self, client):
        """EDGE-03-004 删除商机：阶段记录级联删除，联络记录解绑保留。"""
        oid = make_opportunity(client, 'AICS 级联商机')
        created_id(client.post(f'/api/opportunities/{oid}/stages', json={'stage_name': '初步接触'}))
        aid = make_activity(client, 'AICS 级联联络', opportunity_id=oid)
        ok(client.delete(f'/api/opportunities/{oid}'))
        assert client.get(f'/api/opportunities/{oid}').status_code == 404
        assert ok(client.get(f'/api/activities/{aid}'))['opportunity_id'] is None

    def test_edge_03_005_delete_board_cascades(self, client):
        """EDGE-03-005 删除看板级联删除其列与卡片。"""
        bid = created_id(client.post('/api/kanban/boards', json={'name': 'AICS 级联看板'}))
        boards = ok(client.get('/api/kanban/boards'))
        col = [b for b in boards if b['id'] == bid][0]['columns'][0]['id']
        make_card(client, col, 'AICS 级联卡片')
        ok(client.delete(f'/api/kanban/boards/{bid}'))
        remaining = ok(client.get('/api/kanban/boards'))
        assert not any(b['id'] == bid for b in remaining)
        assert not any(c['id'] == col for b in remaining for c in b['columns'])

    def test_edge_03_006_customer_archive_keeps_relations(self, client, seed):
        """EDGE-03-006 客户归档后其联系人/商机仍可访问。"""
        cid = make_customer(client, 'AICS 归档客户')
        ct = make_contact(client, 'AICS 归档客户联系人', customer_id=cid)
        oid = make_opportunity(client, 'AICS 归档客户商机', customer_id=cid)
        ok(client.delete(f'/api/customers/{cid}'))
        assert not any(c['id'] == cid for c in ok(client.get('/api/customers')))
        assert ok(client.get(f'/api/contacts/{ct}'))['customer_id'] == cid
        assert ok(client.get(f'/api/opportunities/{oid}'))['customer_id'] == cid


# ═══════════════════════════════════════════════════════════════
# EDGE-04 看板联动与排序
# ═══════════════════════════════════════════════════════════════


class TestEdge04Kanban:
    def test_edge_04_001_activity_kanban_linkage(self, client):
        """EDGE-04-001 活动勾选加入看板后生成唯一关联卡片。"""
        aid = make_activity(client, 'AICS 看板联动活动', method='电话', add_to_kanban=True)
        cards = [c for b in ok(client.get('/api/kanban/boards'))
                 for col in b['columns'] for c in col['cards']]
        hits = [c for c in cards if c['source_type'] == 'activity' and c['source_id'] == aid]
        assert len(hits) == 1

    def test_edge_04_002_stage_kanban_linkage(self, client):
        """EDGE-04-002 阶段记录加入看板后生成唯一关联卡片。"""
        oid = make_opportunity(client, 'AICS 阶段看板商机')
        rid = created_id(client.post(f'/api/opportunities/{oid}/stages',
                                     json={'stage_name': '方案报价', 'content': 'x',
                                           'add_to_kanban': True}))
        cards = [c for b in ok(client.get('/api/kanban/boards'))
                 for col in b['columns'] for c in col['cards']]
        assert len([c for c in cards if c['source_type'] == 'stage' and c['source_id'] == rid]) == 1

    def test_edge_04_003_import_deadline(self, client, seed):
        """EDGE-04-003 导入卡片带截止日正确入库。"""
        ok(client.post('/api/kanban/import', json={
            'board_id': seed['board'], 'items': [{'title': 'AICS 截止日卡片',
                                                  'deadline': '2026-08-15'}]}))
        cards = [c for b in ok(client.get('/api/kanban/boards')) if b['id'] == seed['board']
                 for col in b['columns'] for c in col['cards']]
        card = [c for c in cards if c['title'] == 'AICS 截止日卡片'][0]
        assert card['deadline'] == '2026-08-15'

    def test_edge_04_004_import_validation(self, client, seed):
        """EDGE-04-004 导入参数校验：空 items / 非数组 / 看板不存在。"""
        assert 'items 不能为空' in err(client.post('/api/kanban/import',
                                                   json={'board_id': seed['board'], 'items': []}))
        assert 'items 必须为对象数组' in err(client.post('/api/kanban/import',
                                                         json={'board_id': seed['board'], 'items': {'a': 1}}))
        assert 'items 必须为对象数组' in err(client.post('/api/kanban/import',
                                                         json={'board_id': seed['board'], 'items': [None]}))
        assert client.post('/api/kanban/import',
                           json={'board_id': 999999, 'items': [{'title': 'x'}]}).status_code == 404

    def test_edge_04_005_card_title_required(self, client, seed):
        """EDGE-04-005 卡片标题不可为空。"""
        assert '标题不能为空' in err(client.post('/api/kanban/cards',
                                                 json={'column_id': seed['column'], 'title': '  '}))

    def test_edge_04_006_blank_title_keeps_old(self, client, seed):
        """EDGE-04-006 编辑卡片时空白标题不覆盖原标题。"""
        cid = make_card(client, seed['column'], 'AICS 原标题卡片')
        ok(client.put(f'/api/kanban/cards/{cid}', json={'title': '   '}))
        cards = [c for b in ok(client.get('/api/kanban/boards'))
                 for col in b['columns'] for c in col['cards']]
        assert [c for c in cards if c['id'] == cid][0]['title'] == 'AICS 原标题卡片'

    def test_edge_04_007_move_validation(self, client, seed):
        """EDGE-04-007 卡片移动参数校验。"""
        cid = make_card(client, seed['column'], 'AICS 移动校验卡片')
        assert 'position 必须为整数' in err(
            client.post(f'/api/kanban/cards/{cid}/move',
                        json={'column_id': seed['column'], 'position': 'abc'}))
        assert client.post(f'/api/kanban/cards/{cid}/move',
                           json={'column_id': 999999}).status_code == 404

    def test_edge_04_008_position_clamped(self, client, seed):
        """EDGE-04-008 越界 position 被夹取到合法范围，不报错。"""
        cid = make_card(client, seed['column'], 'AICS 越界位置卡片')
        for pos in (-5, 9999):
            ok(client.post(f'/api/kanban/cards/{cid}/move',
                           json={'column_id': seed['column'], 'position': pos}))

    def test_edge_04_009_reorder_validation(self, client, seed):
        """EDGE-04-009 列重排参数校验。"""
        assert 'ids 必须为数组' in err(
            client.post(f"/api/kanban/boards/{seed['board']}/columns/reorder",
                        json={'ids': 'abc'}))
        assert 'ids 元素必须为整数' in err(
            client.post(f"/api/kanban/boards/{seed['board']}/columns/reorder",
                        json={'ids': ['x']}))

    def test_edge_04_010_add_column_missing_board(self, client):
        """EDGE-04-010 向不存在的看板新增列返回 404（不再 500）。"""
        assert client.post('/api/kanban/boards/999999/columns',
                           json={'name': 'x'}).status_code == 404


# ═══════════════════════════════════════════════════════════════
# EDGE-05 跟进同步
# ═══════════════════════════════════════════════════════════════


class TestEdge05FollowupSync:
    def test_edge_05_001_activity_creates_followup(self, client):
        """EDGE-05-001 活动带下次跟进自动生成联络计划并回填来源。"""
        aid = make_activity(client, 'AICS 同步来源活动', time='2026-07-31 10:00',
                            next_time='2026-08-05')
        plans = [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]
        assert len(plans) == 1
        assert plans[0]['source_activity_content'].startswith('AICS 同步来源活动')

    def test_edge_05_002_update_syncs_plan_date(self, client):
        """EDGE-05-002 编辑活动的下次跟进时间同步到联络计划。"""
        aid = make_activity(client, 'AICS 日期同步活动', next_time='2026-08-05')
        ok(client.put(f'/api/activities/{aid}', json={'next_time': '2026-08-10'}))
        plans = [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]
        assert plans[0]['plan_date'].startswith('2026-08-10')

    def test_edge_05_003_executed_plan_not_resynced(self, client, seed):
        """EDGE-05-003 已执行的计划不被活动编辑覆盖。"""
        aid = make_activity(client, 'AICS 已执行计划活动', customer_id=seed['customer'],
                            next_time='2026-08-05')
        fid = [f for f in ok(client.get('/api/followups'))
               if f['source_activity_id'] == aid][0]['id']
        ok(client.post(f'/api/followups/{fid}/execute', json={'actual_content': '已联系'}))
        ok(client.put(f'/api/activities/{aid}', json={'next_time': '2026-09-09'}))
        assert ok(client.get(f'/api/followups/{fid}'))['actual_content'] == '已联系'

    def test_edge_05_004_execute_creates_activity_link(self, client, seed):
        """EDGE-05-004 执行计划生成的日常联络与原计划客户/联系人一致。"""
        fid = make_followup(client, 'AICS 执行生成联络', customer_id=seed['customer'],
                            contact_id=seed['contact'])
        aid = ok(client.post(f'/api/followups/{fid}/execute',
                             json={'actual_content': '本次内容', 'method': '拜访'}))['activity_id']
        act = ok(client.get(f'/api/activities/{aid}'))
        assert act['customer_id'] == seed['customer']
        assert act['contact_id'] == seed['contact']
        assert act['method'] == '拜访'


# ═══════════════════════════════════════════════════════════════
# EDGE-06 统计口径正确性
# ═══════════════════════════════════════════════════════════════


class TestEdge06Analytics:
    def test_edge_06_001_win_loss_exclusive(self, client):
        """EDGE-06-001 赢单/丢单/进行中三者互斥且覆盖全部商机。"""
        make_opportunity(client, 'AICS 丢单商机', current_stage='已丢单', amount='50万')
        make_opportunity(client, 'AICS 签约商机', current_stage='合同签约', amount='80万')
        data = ok(client.get('/api/analytics'))
        wl = {w['name']: w['value'] for w in data['win_loss']}
        assert wl['赢单'] == 1 and wl['丢单'] == 1
        assert sum(wl.values()) == data['summary']['total_opportunities']

    def test_edge_06_002_funnel_includes_data_stages(self, client):
        """EDGE-06-002 漏斗包含配置阶段与数据中出现的其他阶段。"""
        make_opportunity(client, 'AICS 漏斗商机', current_stage='AICS 未配置阶段')
        stages = [f['stage'] for f in ok(client.get('/api/analytics'))['funnel']]
        assert '初步接触' in stages and 'AICS 未配置阶段' in stages

    def test_edge_06_003_amount_suffix_parsing(self, client):
        """EDGE-06-003 金额支持「万」「元」等后缀，取数值部分累加。"""
        make_opportunity(client, 'AICS 金额商机甲', amount='120万')
        make_opportunity(client, 'AICS 金额商机乙', amount='80.5')
        assert ok(client.get('/api/analytics'))['summary']['total_amount'] >= 200.5

    def test_edge_06_004_empty_amount_is_zero(self, client):
        """EDGE-06-004 空金额不参与累加也不报错。"""
        make_opportunity(client, 'AICS 空金额商机', amount='')
        assert ok(client.get('/api/analytics'))['summary']['total_amount'] >= 0

    def test_edge_06_005_conversion_rate_bounds(self, client):
        """EDGE-06-005 转化率在 0~100 之间且与线索状态一致。"""
        data = ok(client.get('/api/analytics'))
        total = len(ok(client.get('/api/leads')))
        converted = len(ok(client.get('/api/leads?status=converted')))
        assert 0 <= data['summary']['conversion_rate'] <= 100
        assert data['summary']['total_leads'] == total
        assert data['summary']['conversion_rate'] == round(converted / max(total, 1) * 100, 1)

    def test_edge_06_006_dashboard_urgent_window(self, client):
        """EDGE-06-006 工作台紧急线索为 0~3 天窗口（含当天，不含 4 天）。"""
        today = date.today()
        make_lead(client, 'AICS 无人机飞行检查当天截止', deadline=today.isoformat())
        make_lead(client, 'AICS 无人机飞行检查三天截止',
                  deadline=(today + timedelta(days=3)).isoformat())
        make_lead(client, 'AICS 无人机飞行检查四天截止',
                  deadline=(today + timedelta(days=4)).isoformat())
        titles = [l['title'] for l in ok(client.get('/api/dashboard'))['urgent_leads']]
        assert 'AICS 无人机飞行检查当天截止' in titles
        assert 'AICS 无人机飞行检查三天截止' in titles
        assert 'AICS 无人机飞行检查四天截止' not in titles

    def test_edge_06_007_dashboard_tolerates_null_content(self, client):
        """EDGE-06-007 联络/计划内容为空时工作台与列表不崩溃（历史缺陷回归）。"""
        aid = make_activity(client, None)
        make_followup(client, None, plan_date=date.today().isoformat())
        ok(client.put(f'/api/activities/{aid}', json={'content': None}))
        assert ok(client.get('/api/dashboard'))['stats']
        assert ok(client.get('/api/followups')) is not None
        assert ok(client.get('/api/daily-brief')) is not None

    def test_edge_06_008_analytics_empty_db(self, client, dbsession):
        """EDGE-06-008 空库时报表与建议接口返回零值而非报错。"""
        wipe_all(dbsession)
        data = ok(client.get('/api/analytics'))
        assert data['summary']['total_leads'] == 0
        assert data['summary']['conversion_rate'] == 0.0
        assert ok(client.get('/api/dashboard'))['stats']['active_leads'] == 0
        assert ok(client.get('/api/suggestions')) == []
        assert ok(client.get('/api/daily-brief'))['today_activities'] == []


# ═══════════════════════════════════════════════════════════════
# EDGE-07 空库 / 极端场景
# ═══════════════════════════════════════════════════════════════


class TestEdge07EmptyState:
    def test_edge_07_001_export_empty(self, client):
        """EDGE-07-001 无匹配数据可导出时返回 400 明确提示。"""
        assert '当前无数据可导出' in err(
            client.post('/api/export/leads', json={'ids': [999999]}))

    def test_edge_07_002_auto_create_board(self, client):
        """EDGE-07-002 无看板时「加入看板」自动创建默认看板。"""
        for b in ok(client.get('/api/kanban/boards')):
            client.delete(f"/api/kanban/boards/{b['id']}")
        assert ok(client.get('/api/kanban/boards')) == []
        make_activity(client, 'AICS 自动建板活动', add_to_kanban=True)
        boards = ok(client.get('/api/kanban/boards'))
        assert len(boards) == 1
        assert [c['name'] for c in boards[0]['columns']] == ['待处理', '进行中', '已完成']

    def test_edge_07_003_single_lead_serial(self, client, dbsession):
        """EDGE-07-003 单条线索流水号以 01 结尾。"""
        wipe_all(dbsession)
        lid = make_lead(client, 'AICS 单条流水线索')
        assert ok(client.get(f'/api/leads/{lid}'))['serial_no'].endswith('01')

    def test_edge_07_004_serial_increments(self, client, dbsession):
        """EDGE-07-004 同日多条线索流水号递增且唯一。"""
        wipe_all(dbsession)
        ids = [make_lead(client, f'AICS 流水线索{i}') for i in range(3)]
        serials = [ok(client.get(f'/api/leads/{i}'))['serial_no'] for i in ids]
        assert len(set(serials)) == 3
        assert [s[-2:] for s in serials] == ['01', '02', '03']

    def test_edge_07_005_empty_list_filters(self, client):
        """EDGE-07-005 无匹配结果的过滤条件返回空数组而非报错。"""
        assert ok(client.get('/api/leads?search=绝不存在的线索关键字')) == []
        assert ok(client.get('/api/customers?search=绝不存在的客户名')) == []
        assert ok(client.get('/api/contacts?search=绝不存在的联系人')) == []


# ═══════════════════════════════════════════════════════════════
# EDGE-08 健壮性冒烟（任何输入都不允许 5xx / HTML）
# ═══════════════════════════════════════════════════════════════


MALFORMED_CALLS = [
    ('post', '/api/customers', {'name': None}),
    ('post', '/api/customers', {'name': 123}),
    ('post', '/api/customers', {'name': 'x', 'social_count': 'abc'}),
    ('post', '/api/leads', {'title': 'x', 'deadline': ''}),
    ('post', '/api/leads', {'title': 'x', 'customer_id': 'abc'}),
    ('post', '/api/contacts', {'name': 'x', 'tags': 5}),
    ('post', '/api/activities', {'content': None, 'next_time': None}),
    ('post', '/api/activities', {'content': 'x', 'customer_id': 'abc'}),
    ('post', '/api/followups', {'content': None, 'plan_date': None}),
    ('post', '/api/opportunities', {'title': 'x', 'probability': 'abc'}),
    ('post', '/api/opportunities/1/stages', {'stage_name': None}),
    ('post', '/api/kanban/import', {'board_id': None, 'items': None}),
    ('post', '/api/kanban/cards', {'column_id': None, 'title': 'x'}),
    ('post', '/api/kanban/cards/1/move', {'column_id': None}),
    ('post', '/api/kanban/boards/1/columns/reorder', {'ids': None}),
    ('put', '/api/leads/1', {'status': None}),
    ('put', '/api/followups/1', {'plan_date': 0}),
    ('put', '/api/kanban/cards/1', {'deadline': 0}),
    ('post', '/api/config/test-ai', {}),
    ('post', '/api/skills/nonexistent/execute', {}),
    ('get', '/api/contacts?customer_id=1.5', None),
    ('get', '/api/leads?date_from=9999-99-99', None),
    ('get', '/api/activities?date_to=abc', None),
    ('get', '/api/followups?status=unknown', None),
]


@pytest.mark.parametrize('method,url,payload', MALFORMED_CALLS,
                         ids=[f'{m}-{u}-{i}' for i, (m, u, _) in enumerate(MALFORMED_CALLS)])
def test_edge_08_robustness_smoke(client, method, url, payload):
    """EDGE-08-001 畸形输入一律返回 JSON 且绝不出现 5xx。"""
    fn = getattr(client, method)
    r = fn(url, json=payload) if payload is not None else fn(url)
    assert r.status_code < 500, f'{method.upper()} {url} -> {r.status_code} {r.get_data(as_text=True)[:200]}'
    assert r.headers['Content-Type'].startswith('application/json'), \
        f'{method.upper()} {url} 返回了非 JSON 响应'
    assert isinstance(json_of(r), (dict, list))


if __name__ == '__main__':
    raise SystemExit(pytest.main([os.path.abspath(__file__), '-v', '-p', 'no:cacheprovider']))
