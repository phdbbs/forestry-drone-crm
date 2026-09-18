#!/usr/bin/env python3
"""
AICS — Automated Integration & Compliance Suite（集成与合规套件）

林业无人机业务 CRM 系统全模块集成测试。每条用例带唯一 AICS 标识，用于需求追溯
（PRD：docs/crm_3.1_pr.md 第五章「主要 API」、第七章「测试与验收标准」）。

用法：
    pytest tests/test_aics.py -v            # 推荐
    python tests/test_aics.py               # 兼容旧入口，等价于 pytest -v

设计原则：
    * 不硬编码主键 —— 一律通过 seed / 创建接口动态取 ID，避免数据变动导致误报；
    * 断言业务语义 —— 不只看 HTTP 200，还校验落库结果与接口契约；
    * 零外网依赖 —— 采集/AI 全部打桩，可离线、可重复执行。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crm_test_utils import (  # noqa: E402
    created_id, err, json_of, make_activity, make_card, make_contact,
    make_customer, make_followup, make_lead, make_opportunity, ok,
)

# ═══════════════════════════════════════════════════════════════
# AICS-M001 客户管理
# ═══════════════════════════════════════════════════════════════


class TestAICSM001Customer:
    def test_m001_001_list(self, client):
        """AICS-M001-001 客户列表返回数组，含联系人/新闻计数。"""
        rows = ok(client.get('/api/customers'))
        assert isinstance(rows, list) and len(rows) >= 6
        first = rows[0]
        for key in ('id', 'name', 'type', 'level', 'region', 'contact_count', 'news_count'):
            assert key in first, f"缺少字段 {key}"

    def test_m001_002_create(self, client):
        """AICS-M001-002 新增客户。"""
        cid = make_customer(client, 'AICS 测试客户-广东林业局', short_name='粤林',
                            type='政府部门', level='A-重点客户', region='广东',
                            address='广州市天河区', website='https://example.com',
                            capital='5000万', years='10', social_count=120,
                            scope='林业调查', ip='专利3项', dept='资源处',
                            source='手工录入', remark='AICS-M001-002')
        assert isinstance(cid, int) and cid > 0

    def test_m001_003_detail(self, client, seed):
        """AICS-M001-003 客户详情含基本信息 + 联系人 + 商机 + 新闻。"""
        body = ok(client.get(f"/api/customers/{seed['customer']}"))
        assert body['id'] == seed['customer']
        assert isinstance(body['contacts'], list)
        assert isinstance(body['opportunities'], list)
        assert isinstance(body['news'], list)
        assert 'website' in body and 'capital' in body and 'scope' in body

    def test_m001_004_update(self, client, seed):
        """AICS-M001-004 编辑客户字段。"""
        cid = seed['customer']
        ok(client.put(f'/api/customers/{cid}', json={
            'short_name': 'AICS-改', 'level': 'B-重要客户', 'region': '浙江'}))
        body = ok(client.get(f'/api/customers/{cid}'))
        assert body['short_name'] == 'AICS-改'
        assert body['level'] == 'B-重要客户'
        assert body['region'] == '浙江'

    def test_m001_005_search(self, client):
        """AICS-M001-005 客户名称搜索过滤。"""
        make_customer(client, 'AICS 唯一客户-搜索验证')
        rows = ok(client.get('/api/customers?search=AICS 唯一客户'))
        assert len(rows) == 1 and rows[0]['name'] == 'AICS 唯一客户-搜索验证'

    def test_m001_006_delete_is_archive(self, client):
        """AICS-M001-006 删除客户 = 归档（列表不再出现，详情仍可读）。"""
        cid = make_customer(client, 'AICS 待归档客户')
        ok(client.delete(f'/api/customers/{cid}'))
        names = [c['name'] for c in ok(client.get('/api/customers'))]
        assert 'AICS 待归档客户' not in names
        assert ok(client.get(f'/api/customers/{cid}'))['name'] == 'AICS 待归档客户'

    def test_m001_007_news_endpoint(self, client, seed):
        """AICS-M001-007 客户新闻列表接口可用。"""
        assert isinstance(ok(client.get(f"/api/customers/{seed['customer']}/news")), list)

    def test_m001_008_customer_news_shape(self, client, dbsession, seed):
        """AICS-M001-008 客户新闻字段契约（采集时间/来源/标题/摘要）。"""
        from datetime import datetime
        from app.models import CustomerNews
        dbsession.add(CustomerNews(customer_id=seed['customer'], title='AICS 新闻标题',
                                   content='正文', url='https://example.com/n1',
                                   source_name='示例来源', change_type='news',
                                   publish_date=datetime(2026, 5, 1),
                                   event_time=datetime(2026, 5, 1)))
        dbsession.commit()
        rows = ok(client.get(f"/api/customers/{seed['customer']}/news"))
        assert len(rows) == 1
        assert rows[0]['source_name'] == '示例来源'
        assert rows[0]['title'] == 'AICS 新闻标题'
        assert rows[0]['event_time'] == '2026-05-01'
        assert rows[0]['crawled_at']


# ═══════════════════════════════════════════════════════════════
# AICS-M002 线索管理
# ═══════════════════════════════════════════════════════════════


class TestAICSM002Lead:
    def test_m002_001_list(self, client):
        """AICS-M002-001 线索列表字段完整。"""
        rows = ok(client.get('/api/leads'))
        assert len(rows) >= 5
        for key in ('id', 'title', 'budget', 'deadline', 'days_left', 'region',
                    'match_level', 'match_score', 'status', 'serial_no'):
            assert key in rows[0], f"缺少字段 {key}"

    def test_m002_002_high_match(self, client):
        """AICS-M002-002 高匹配线索：含高匹配关键词时评级为高匹配。"""
        lid = make_lead(client, 'AICS 无人机飞行检查与林区巡检项目',
                        service_content='无人机飞行检查、林区巡检、航拍核查',
                        budget='350', deadline='2026-12-31', region='广东',
                        purchaser='广东省林业局')
        body = ok(client.get(f'/api/leads/{lid}'))
        assert body['match_level'] == '高匹配'
        assert body['match_score'] >= 70
        assert '无人机飞行检查' in (body['match_keywords'] or '')

    def test_m002_003_low_match(self, client):
        """AICS-M002-003 低匹配线索：仅含低匹配关键词。"""
        lid = make_lead(client, 'AICS 林木砍伐与清运施工项目',
                        service_content='林木砍伐、清运、消杀施工')
        body = ok(client.get(f'/api/leads/{lid}'))
        assert body['match_level'] == '低匹配'
        assert body['match_score'] <= 30

    def test_m002_004_get_detail(self, client, seed):
        """AICS-M002-004 线索详情。"""
        body = ok(client.get(f"/api/leads/{seed['lead_active']}"))
        assert body['id'] == seed['lead_active'] and body['title']
        assert 'match_reason' in body and 'source_url' in body

    def test_m002_005_update(self, client, seed):
        """AICS-M002-005 编辑线索（待转化可改）。"""
        lid = seed['lead_active']
        ok(client.put(f'/api/leads/{lid}', json={'budget': '180', 'region': '浙江省'}))
        body = ok(client.get(f'/api/leads/{lid}'))
        assert body['budget'] == '180' and body['region'] == '浙江省'

    def test_m002_006_status_filter(self, client):
        """AICS-M002-006 按状态过滤。"""
        make_lead(client, 'AICS 状态过滤-待转化')
        for row in ok(client.get('/api/leads?status=active')):
            assert row['status'] == 'active'

    def test_m002_007_serial_no_format(self, client):
        """AICS-M002-007 流水号格式：年1+月1+日2+流水2 = 6 位。"""
        lid = make_lead(client, 'AICS 流水号格式校验')
        serial = ok(client.get(f'/api/leads/{lid}'))['serial_no']
        assert len(serial) >= 6 and serial.isalnum()

    def test_m002_008_convert_auto_create(self, client, seed):
        """AICS-M002-008 转商机：未指定客户/联系人时按采购方与项目联系人自动创建。"""
        lid = make_lead(client, 'AICS 转化自动建客户线索',
                        purchaser='AICS 转化采购单位', contact_name='张项目',
                        contact_phone='13800000001', source_url='https://example.com/bid/1')
        oid = created_id(client.post(f'/api/leads/{lid}/convert', json={'amount': '350'}))
        opp = ok(client.get(f'/api/opportunities/{oid}'))
        assert opp['customer_name'] == 'AICS 转化采购单位'
        assert opp['contact_name'] == '张项目'
        assert opp['source_url'] == 'https://example.com/bid/1'
        # 线索状态与客户回写
        lead = ok(client.get(f'/api/leads/{lid}'))
        assert lead['status'] == 'converted'
        assert lead['customer_id'] == opp['customer_id']

    def test_m002_009_converted_filter(self, client):
        """AICS-M002-009 已转化线索可按状态查询。"""
        lid = make_lead(client, 'AICS 已转化过滤线索', purchaser='AICS 过滤采购方')
        created_id(client.post(f'/api/leads/{lid}/convert', json={}))
        converted = ok(client.get('/api/leads?status=converted'))
        assert any(r['id'] == lid for r in converted)
        assert all(r['status'] == 'converted' for r in converted)

    def test_m002_010_converted_cannot_modify_or_delete(self, client):
        """AICS-M002-010 已转化线索不可修改、不可删除（后端 400 拦截）。"""
        lid = make_lead(client, 'AICS 已转化保护线索', purchaser='AICS 保护采购方')
        created_id(client.post(f'/api/leads/{lid}/convert', json={}))
        assert '不可修改' in err(client.put(f'/api/leads/{lid}', json={'title': 'x'}))
        assert '不可删除' in err(client.delete(f'/api/leads/{lid}'))

    def test_m002_011_convert_winner_list(self, client):
        """AICS-M002-011 中标公告转化：多家中标单位 + 采购单位全部建/匹配客户。"""
        lid = make_lead(client, 'AICS 中标公告转化', purchaser='AICS 招标采购方')
        oid = created_id(client.post(f'/api/leads/{lid}/convert', json={
            'winner_customer_names': ['AICS 中标甲', 'AICS 中标乙'],
            'purchaser_customer_names': ['AICS 招标采购方'],
        }))
        opp = ok(client.get(f'/api/opportunities/{oid}'))
        assert opp['customer_name'] == 'AICS 中标甲'
        lead = ok(client.get(f'/api/leads/{lid}'))
        assert lead['related_customer_ids'].count(',') == 2

    def test_m002_012_convert_reason_written_to_activity(self, client):
        """AICS-M002-012 转化原因写入该商机的首条联络记录。"""
        lid = make_lead(client, 'AICS 转化原因线索', purchaser='AICS 原因采购方')
        oid = created_id(client.post(f'/api/leads/{lid}/convert',
                                     json={'reason': 'AICS 转化原因说明'}))
        opp = ok(client.get(f'/api/opportunities/{oid}'))
        assert any(a['method'] == '转化' and a['content'] == 'AICS 转化原因说明'
                   for a in opp['activities'])

    def test_m002_013_abandon_and_restore(self, client):
        """AICS-M002-013 废弃线索后可恢复为待转化并再次转化。"""
        lid = make_lead(client, 'AICS 废弃恢复线索', purchaser='AICS 恢复采购方')
        ok(client.post(f'/api/leads/{lid}/abandon', json={'reason': 'AICS 废弃原因'}))
        assert ok(client.get(f'/api/leads/{lid}'))['status'] == 'abandoned'
        ok(client.put(f'/api/leads/{lid}', json={'status': 'active'}))
        assert ok(client.get(f'/api/leads/{lid}'))['status'] == 'active'
        assert created_id(client.post(f'/api/leads/{lid}/convert', json={}))

    def test_m002_014_release_and_claim(self, client):
        """AICS-M002-014 释放至公海池后可领取。"""
        lid = make_lead(client, 'AICS 公海池线索')
        ok(client.post(f'/api/leads/{lid}/release', json={}))
        assert ok(client.get(f'/api/leads/{lid}'))['status'] == 'pool'
        ok(client.post(f'/api/leads/{lid}/claim', json={'assignee': 'AICS 领取人'}))
        body = ok(client.get(f'/api/leads/{lid}'))
        assert body['status'] == 'active'

    def test_m002_015_search_and_region(self, client):
        """AICS-M002-015 搜索与地区过滤。"""
        make_lead(client, 'AICS 搜索目标线索', region='广西壮族自治区')
        assert len(ok(client.get('/api/leads?search=AICS 搜索目标线索'))) == 1
        rows = ok(client.get('/api/leads?region=广西'))
        assert rows and all('广西' in (r['region'] or '') for r in rows)

    def test_m002_016_date_range_filter(self, client):
        """AICS-M002-016 创建时间范围过滤（含两种日期格式）。"""
        make_lead(client, 'AICS 日期过滤线索')
        today = __import__('datetime').date.today().isoformat()
        assert any(r['title'] == 'AICS 日期过滤线索'
                   for r in ok(client.get(f'/api/leads?date_from={today}&date_to={today}')))
        # 斜杠格式同样可解析
        slash = today.replace('-', '/')
        assert ok(client.get(f'/api/leads?date_from={slash}')) is not None
        # 范围外
        assert not any(r['title'] == 'AICS 日期过滤线索'
                       for r in ok(client.get('/api/leads?date_to=2000-01-01')))

    def test_m002_017_delete_active_lead_clears_refs(self, client, dbsession):
        """AICS-M002-017 删除待转化线索并解除商机/联络的悬空引用。"""
        from app.models import Lead, Opportunity
        lead = Lead(title='AICS 待删除线索', status='active')
        dbsession.add(lead)
        dbsession.flush()
        opp = Opportunity(title='AICS 引用待删线索的商机', lead_id=lead.id)
        dbsession.add(opp)
        dbsession.commit()
        lid, oid = lead.id, opp.id
        ok(client.delete(f'/api/leads/{lid}'))
        assert client.get(f'/api/leads/{lid}').status_code == 404
        assert ok(client.get(f'/api/opportunities/{oid}'))['lead_id'] is None


# ═══════════════════════════════════════════════════════════════
# AICS-M003 商机管理
# ═══════════════════════════════════════════════════════════════


class TestAICSM003Opportunity:
    def test_m003_001_list(self, client):
        """AICS-M003-001 商机列表字段完整（含阶段记录）。"""
        rows = ok(client.get('/api/opportunities'))
        assert len(rows) >= 2
        for key in ('id', 'title', 'amount', 'current_stage', 'probability',
                    'expected_close', 'customer_name', 'stages'):
            assert key in rows[0], f"缺少字段 {key}"

    def test_m003_002_create(self, client, seed):
        """AICS-M003-002 新建商机。"""
        oid = make_opportunity(client, 'AICS 新建商机-深圳无人机监测',
                               customer_id=seed['customer'], amount='500',
                               current_stage='需求调研', probability=40)
        body = ok(client.get(f'/api/opportunities/{oid}'))
        assert body['amount'] == '500' and body['current_stage'] == '需求调研'
        assert body['probability'] == 40

    def test_m003_003_detail_with_lead(self, client):
        """AICS-M003-003 商机详情带回线索标题与来源链接。"""
        lid = make_lead(client, 'AICS 商机来源线索', source_url='https://example.com/bid/9',
                        purchaser='AICS 来源采购方')
        oid = created_id(client.post(f'/api/leads/{lid}/convert', json={}))
        body = ok(client.get(f'/api/opportunities/{oid}'))
        assert body['lead_title'] == 'AICS 商机来源线索'
        assert body['source_url'] == 'https://example.com/bid/9'
        assert isinstance(body['stages'], list) and isinstance(body['activities'], list)

    def test_m003_004_update_fields(self, client, seed):
        """AICS-M003-004 行内编辑商机（标题/金额/赢率/预计关闭）。"""
        oid = seed['opportunity']
        ok(client.put(f'/api/opportunities/{oid}', json={
            'title': 'AICS 编辑后商机', 'amount': '180', 'probability': 66,
            'expected_close': '2026-12-31'}))
        body = ok(client.get(f'/api/opportunities/{oid}'))
        assert body['title'] == 'AICS 编辑后商机'
        assert body['amount'] == '180' and body['probability'] == 66
        assert body['expected_close'] == '2026-12-31'

    def test_m003_005_stage_change_writes_record(self, client, seed):
        """AICS-M003-005 阶段变更自动写入流转记录，时间轴可追溯。"""
        oid = make_opportunity(client, 'AICS 阶段流转商机', current_stage='初步接触')
        ok(client.put(f'/api/opportunities/{oid}', json={'current_stage': '方案报价'}))
        stages = ok(client.get(f'/api/opportunities/{oid}'))['stages']
        assert any('方案报价' in (s['stage'] or '') and s['status'] == 'completed' for s in stages)
        # 同阶段重复提交不产生冗余记录
        before = len(stages)
        ok(client.put(f'/api/opportunities/{oid}', json={'current_stage': '方案报价'}))
        assert len(ok(client.get(f'/api/opportunities/{oid}'))['stages']) == before

    def test_m003_006_add_stage_record(self, client):
        """AICS-M003-006 添加阶段记录并同步商机当前阶段。"""
        oid = make_opportunity(client, 'AICS 阶段记录商机')
        rid = created_id(client.post(f'/api/opportunities/{oid}/stages', json={
            'stage_name': '方案评审', 'content': '提交终版方案与报价',
            'deadline': '2026-07-15', 'status': 'pending'}))
        body = ok(client.get(f'/api/opportunities/{oid}'))
        assert body['current_stage'] == '方案评审'
        rec = [s for s in body['stages'] if s['id'] == rid][0]
        assert rec['deadline'] == '2026-07-15' and rec['status'] == 'pending'

    def test_m003_007_stage_record_to_kanban(self, client):
        """AICS-M003-007 阶段记录可一键加入看板。"""
        oid = make_opportunity(client, 'AICS 阶段入看板商机')
        rid = created_id(client.post(f'/api/opportunities/{oid}/stages', json={
            'stage_name': '内部评审', 'content': '技术评审', 'add_to_kanban': True}))
        cards = [c for b in ok(client.get('/api/kanban/boards')) for col in b['columns'] for c in col['cards']]
        assert any(c['source_type'] == 'stage' and c['source_id'] == rid for c in cards)

    def test_m003_008_delete(self, client):
        """AICS-M003-008 删除商机（阶段记录级联删除，联络记录解绑保留）。"""
        oid = make_opportunity(client, 'AICS 待删除商机')
        created_id(client.post(f'/api/opportunities/{oid}/stages', json={'stage_name': '初步接触'}))
        aid = make_activity(client, 'AICS 关联该商机的联络', opportunity_id=oid)
        ok(client.delete(f'/api/opportunities/{oid}'))
        assert client.get(f'/api/opportunities/{oid}').status_code == 404
        assert ok(client.get(f'/api/activities/{aid}'))['opportunity_id'] is None

    def test_m003_009_stage_dict_crud(self, client):
        """AICS-M003-009 商机阶段字典增删改查。"""
        stages = ok(client.get('/api/stages'))
        assert len(stages) == 8
        sid = created_id(client.post('/api/stages', json={'name': 'AICS 自定义阶段'}))
        ok(client.put(f'/api/stages/{sid}', json={'name': 'AICS 自定义阶段-改', 'sort_order': 99}))
        assert any(s['name'] == 'AICS 自定义阶段-改' for s in ok(client.get('/api/stages')))
        ok(client.delete(f'/api/stages/{sid}'))
        assert not any(s['name'] == 'AICS 自定义阶段-改' for s in ok(client.get('/api/stages')))

    def test_m003_010_stage_requires_name(self, client):
        """AICS-M003-010 阶段记录缺 stage_name 返回 400。"""
        oid = make_opportunity(client, 'AICS 空阶段商机')
        assert '不能为空' in err(client.post(f'/api/opportunities/{oid}/stages', json={}))

    def test_m003_011_kanban_pipeline(self, client):
        """AICS-M003-011 管道图按配置阶段统计（配置阶段 + 数据中出现的阶段）。"""
        make_opportunity(client, 'AICS 管道商机', current_stage='AICS 特殊阶段')
        funnel = ok(client.get('/api/analytics'))['funnel']
        names = [f['stage'] for f in funnel]
        assert '初步接触' in names and 'AICS 特殊阶段' in names


# ═══════════════════════════════════════════════════════════════
# AICS-M004 联系人管理
# ═══════════════════════════════════════════════════════════════


class TestAICSM004Contact:
    def test_m004_001_list(self, client):
        """AICS-M004-001 联系人列表字段完整。"""
        rows = ok(client.get('/api/contacts'))
        assert len(rows) >= 5
        for key in ('id', 'name', 'title', 'phone', 'role', 'importance',
                    'customer_id', 'customer_name', 'avatar'):
            assert key in rows[0], f"缺少字段 {key}"

    def test_m004_002_create(self, client, seed):
        """AICS-M004-002 新建联系人（自动生成头像首字）。"""
        cid = make_contact(client, 'AICS 陈科长', title='林业科科长',
                           phone='135-0000-1234', email='chen@example.com',
                           customer_id=seed['customer'], importance='重要',
                           business_scope='无人机巡检管理', notes='AICS-M004-002')
        body = ok(client.get(f'/api/contacts/{cid}'))
        assert body['name'] == 'AICS 陈科长' and body['avatar'] == 'A'
        assert body['customer_name']

    def test_m004_003_detail_with_news(self, client, seed):
        """AICS-M004-003 联系人详情含 news / contact_news 两个板块。"""
        body = ok(client.get(f"/api/contacts/{seed['contact']}"))
        assert 'news' in body and 'contact_news' in body
        assert isinstance(body['contact_news'], list)

    def test_m004_004_update(self, client, seed):
        """AICS-M004-004 编辑联系人。"""
        cid = seed['contact']
        ok(client.put(f'/api/contacts/{cid}', json={
            'title': 'AICS 新职位', 'phone': '138-0571-9999', 'role': '决策人'}))
        body = ok(client.get(f'/api/contacts/{cid}'))
        assert body['title'] == 'AICS 新职位' and body['phone'] == '138-0571-9999'

    def test_m004_005_search_and_cascade(self, client, seed):
        """AICS-M004-005 联系人按姓名搜索 + 按客户级联筛选。"""
        make_contact(client, 'AICS 搜索联系人', customer_id=seed['customer'])
        make_contact(client, 'AICS 其他客户联系人', customer_id=seed['customer2'])
        assert len(ok(client.get('/api/contacts?search=AICS 搜索联系人'))) == 1
        rows = ok(client.get(f"/api/contacts?customer_id={seed['customer']}"))
        assert rows and all(r['customer_id'] == seed['customer'] for r in rows)

    def test_m004_006_delete_clears_refs(self, client, seed):
        """AICS-M004-006 删除联系人：动态新闻随删，活动/计划/商机解绑保留。"""
        cid = make_contact(client, 'AICS 待删除联系人', customer_id=seed['customer'])
        aid = make_activity(client, 'AICS 关联联络', contact_id=cid, customer_id=seed['customer'])
        fid = make_followup(client, 'AICS 关联计划', contact_id=cid, customer_id=seed['customer'])
        ok(client.delete(f'/api/contacts/{cid}'))
        assert client.get(f'/api/contacts/{cid}').status_code == 404
        assert ok(client.get(f'/api/activities/{aid}'))['contact_id'] is None
        assert ok(client.get(f'/api/followups/{fid}'))['contact_id'] is None


# ═══════════════════════════════════════════════════════════════
# AICS-M005 活动记录（日常联络）
# ═══════════════════════════════════════════════════════════════


class TestAICSM005Activity:
    def test_m005_001_list(self, client):
        """AICS-M005-001 日常联络列表字段完整。"""
        rows = ok(client.get('/api/activities'))
        assert len(rows) >= 2
        for key in ('id', 'method', 'content', 'activity_time', 'customer_name',
                    'contact_name', 'opportunity_title', 'next_followup_time'):
            assert key in rows[0], f"缺少字段 {key}"

    def test_m005_002_create(self, client, seed):
        """AICS-M005-002 新建日常联络。"""
        aid = make_activity(client, 'AICS 讨论项目进展', method='电话',
                            customer_id=seed['customer'], contact_id=seed['contact'],
                            time='2026-06-20 10:00')
        body = ok(client.get(f'/api/activities/{aid}'))
        assert body['method'] == '电话' and body['content'] == 'AICS 讨论项目进展'
        assert body['activity_time'].startswith('2026-06-20 10:00')

    def test_m005_003_detail_and_update(self, client, seed):
        """AICS-M005-003 详情与编辑。"""
        aid = make_activity(client, 'AICS 详情联络', method='拜访', customer_id=seed['customer'])
        ok(client.put(f'/api/activities/{aid}', json={
            'content': 'AICS 编辑后内容', 'method': '会议'}))
        body = ok(client.get(f'/api/activities/{aid}'))
        assert body['content'] == 'AICS 编辑后内容' and body['method'] == '会议'

    def test_m005_004_search_and_filters(self, client, seed):
        """AICS-M005-004 内容搜索 / 客户 / 商机 / 日期范围过滤。"""
        make_activity(client, 'AICS 可搜索的联络内容', customer_id=seed['customer'])
        assert len(ok(client.get('/api/activities?search=AICS 可搜索的联络内容'))) == 1
        rows = ok(client.get(f"/api/activities?customer_id={seed['customer']}"))
        assert all(r['customer_id'] == seed['customer'] for r in rows)
        today = __import__('datetime').date.today().isoformat()
        assert ok(client.get(f'/api/activities?date_from={today}&date_to={today}')) is not None

    def test_m005_005_auto_followup(self, client, seed):
        """AICS-M005-005 新建联络时带「下次跟进」自动生成联络计划。"""
        aid = make_activity(client, 'AICS 自动计划联络', customer_id=seed['customer'],
                            contact_id=seed['contact'], time='2026-06-25 14:00',
                            next_time='2026-07-01', next_content='AICS 关注招标公告')
        plans = [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]
        assert len(plans) == 1
        assert plans[0]['content'] == 'AICS 关注招标公告'
        assert plans[0]['plan_date'].startswith('2026-07-01')
        assert plans[0]['source_activity_method'] == ''
        assert 'AICS 自动计划联络' in plans[0]['ai_suggested_content']

    def test_m005_006_activity_to_kanban(self, client):
        """AICS-M005-006 联络可一键加入看板。"""
        aid = make_activity(client, 'AICS 入看板联络', method='会议', add_to_kanban=True)
        cards = [c for b in ok(client.get('/api/kanban/boards')) for col in b['columns'] for c in col['cards']]
        assert any(c['source_type'] == 'activity' and c['source_id'] == aid for c in cards)

    def test_m005_007_activity_and_followup_both_to_kanban(self, client):
        """AICS-M005-007 同时勾选下次跟进与看板时生成两张卡片。"""
        aid = make_activity(client, 'AICS 双卡片联络', next_time='2026-08-01',
                            next_content='AICS 二次回访', add_to_kanban=True)
        cards = [c for b in ok(client.get('/api/kanban/boards')) for col in b['columns'] for c in col['cards']]
        types = {(c['source_type'], c['source_id']) for c in cards}
        assert ('activity', aid) in types
        plans = [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]
        assert ('followup', plans[0]['id']) in types

    def test_m005_008_update_syncs_followup(self, client, seed):
        """AICS-M005-008 编辑联络的下次跟进时间会同步联络计划。"""
        aid = make_activity(client, 'AICS 同步计划联络', customer_id=seed['customer'],
                            time='2026-07-31 10:00', next_time='2026-08-05')
        ok(client.put(f'/api/activities/{aid}', json={'next_time': '2026-08-10'}))
        plans = [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]
        assert plans and plans[0]['plan_date'].startswith('2026-08-10')

    def test_m005_009_clear_next_time_removes_plan(self, client, seed):
        """AICS-M005-009 清空下次跟进时间时删除未执行的联动计划。"""
        aid = make_activity(client, 'AICS 清空计划联络', customer_id=seed['customer'],
                            next_time='2026-08-20')
        assert [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]
        ok(client.put(f'/api/activities/{aid}', json={'next_time': None}))
        assert not [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]

    def test_m005_010_add_next_time_later_creates_plan(self, client, seed):
        """AICS-M005-010 原无下次跟进、编辑时新增则补建联络计划。"""
        aid = make_activity(client, 'AICS 补建计划联络', customer_id=seed['customer'])
        assert not [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]
        ok(client.put(f'/api/activities/{aid}', json={'next_time': '2026-09-01'}))
        plans = [f for f in ok(client.get('/api/followups')) if f['source_activity_id'] == aid]
        assert len(plans) == 1 and plans[0]['plan_date'].startswith('2026-09-01')

    def test_m005_011_delete(self, client):
        """AICS-M005-011 删除日常联络。"""
        aid = make_activity(client, 'AICS 待删除联络')
        ok(client.delete(f'/api/activities/{aid}'))
        assert client.get(f'/api/activities/{aid}').status_code == 404


# ═══════════════════════════════════════════════════════════════
# AICS-M006 看板管理
# ═══════════════════════════════════════════════════════════════


class TestAICSM006Kanban:
    def test_m006_001_boards(self, client):
        """AICS-M006-001 看板列表含列与卡片。"""
        boards = ok(client.get('/api/kanban/boards'))
        assert boards and len(boards[0]['columns']) == 3
        assert {'id', 'name', 'sort_order', 'cards'} <= set(boards[0]['columns'][0])

    def test_m006_002_create_board(self, client):
        """AICS-M006-002 新建看板自动生成 待处理/进行中/已完成 三列。"""
        bid = created_id(client.post('/api/kanban/boards', json={'name': 'AICS 测试看板'}))
        board = [b for b in ok(client.get('/api/kanban/boards')) if b['id'] == bid][0]
        assert [c['name'] for c in board['columns']] == ['待处理', '进行中', '已完成']

    def test_m006_003_search(self, client):
        """AICS-M006-003 看板名称搜索。"""
        client.post('/api/kanban/boards', json={'name': 'AICS 可搜索看板'})
        assert len(ok(client.get('/api/kanban/boards?search=AICS 可搜索看板'))) == 1

    def test_m006_004_create_card(self, client, seed):
        """AICS-M006-004 新建卡片（含标签颜色与截止日）。"""
        cid = make_card(client, seed['column'], 'AICS 新卡片', description='描述',
                        color='green', deadline='2026-08-15')
        cards = [c for b in ok(client.get('/api/kanban/boards')) for col in b['columns'] for c in col['cards']]
        card = [c for c in cards if c['id'] == cid][0]
        assert card['color'] == 'green' and card['deadline'] == '2026-08-15'

    def test_m006_005_import_cards(self, client, seed):
        """AICS-M006-005 批量导入卡片到看板首列。"""
        before = len(ok(client.get('/api/kanban/boards'))[0]['columns'][0]['cards'])
        ok(client.post('/api/kanban/import', json={'board_id': seed['board'], 'items': [
            {'title': 'AICS 导入卡片1', 'description': '测试导入', 'color': 'green'},
            {'title': 'AICS 导入卡片2', 'description': '测试导入', 'color': 'blue'},
        ]}))
        after = len(ok(client.get('/api/kanban/boards'))[0]['columns'][0]['cards'])
        assert after == before + 2

    def test_m006_006_move_card(self, client, seed):
        """AICS-M006-006 卡片跨列移动。"""
        cid = make_card(client, seed['column'], 'AICS 移动卡片')
        board = ok(client.get('/api/kanban/boards'))[0]
        target = board['columns'][1]['id']
        ok(client.post(f'/api/kanban/cards/{cid}/move', json={'column_id': target}))
        board = ok(client.get('/api/kanban/boards'))[0]
        assert any(c['id'] == cid for c in board['columns'][1]['cards'])

    def test_m006_007_move_card_position(self, client, seed):
        """AICS-M006-007 卡片移动到指定位置并按顺序重排。"""
        col = seed['column']
        ids = [make_card(client, col, f'AICS 排序卡片{i}') for i in range(3)]
        ok(client.post(f'/api/kanban/cards/{ids[2]}/move', json={'column_id': col, 'position': 0}))
        board = ok(client.get('/api/kanban/boards'))[0]
        cards = [c['id'] for c in board['columns'][0]['cards']]
        ordered = [i for i in cards if i in ids]
        assert ordered == [ids[2], ids[0], ids[1]]

    def test_m006_008_update_card_and_column(self, client, seed):
        """AICS-M006-008 编辑卡片与列名。"""
        cid = make_card(client, seed['column'], 'AICS 编辑卡片')
        ok(client.put(f'/api/kanban/cards/{cid}', json={'title': 'AICS 编辑后卡片',
                                                        'deadline': '2026-09-09'}))
        ok(client.put(f"/api/kanban/columns/{seed['column']}", json={'name': 'AICS 改名列'}))
        board = ok(client.get('/api/kanban/boards'))[0]
        col = [c for c in board['columns'] if c['id'] == seed['column']][0]
        assert col['name'] == 'AICS 改名列'
        assert [c for c in col['cards'] if c['id'] == cid][0]['title'] == 'AICS 编辑后卡片'

    def test_m006_009_add_column_and_reorder(self, client, seed):
        """AICS-M006-009 新增列并调整列顺序。"""
        bid = seed['board']
        new_id = created_id(client.post(f'/api/kanban/boards/{bid}/columns', json={'name': 'AICS 新列'}))
        board = [b for b in ok(client.get('/api/kanban/boards')) if b['id'] == bid][0]
        ids = [c['id'] for c in board['columns']]
        assert ids[-1] == new_id
        ok(client.post(f'/api/kanban/boards/{bid}/columns/reorder', json={'ids': list(reversed(ids))}))
        board = [b for b in ok(client.get('/api/kanban/boards')) if b['id'] == bid][0]
        assert [c['id'] for c in board['columns']] == list(reversed(ids))

    def test_m006_010_delete_card_column_board(self, client, seed):
        """AICS-M006-010 删除卡片 / 列 / 看板。"""
        cid = make_card(client, seed['column'], 'AICS 待删卡片')
        ok(client.delete(f'/api/kanban/cards/{cid}'))
        new_col = created_id(client.post(f"/api/kanban/boards/{seed['board']}/columns",
                                         json={'name': 'AICS 待删列'}))
        ok(client.delete(f'/api/kanban/columns/{new_col}'))
        new_board = created_id(client.post('/api/kanban/boards', json={'name': 'AICS 待删看板'}))
        ok(client.delete(f'/api/kanban/boards/{new_board}'))
        assert not any(b['id'] == new_board for b in ok(client.get('/api/kanban/boards')))

    def test_m006_011_auto_create_board(self, client):
        """AICS-M006-011 无任何看板时「加入看板」自动建默认看板，不静默失败。"""
        for b in ok(client.get('/api/kanban/boards')):
            client.delete(f"/api/kanban/boards/{b['id']}")
        assert ok(client.get('/api/kanban/boards')) == []
        aid = make_activity(client, 'AICS 自动建看板联络', add_to_kanban=True)
        boards = ok(client.get('/api/kanban/boards'))
        assert boards and any(c['source_id'] == aid
                              for col in boards[0]['columns'] for c in col['cards'])


# ═══════════════════════════════════════════════════════════════
# AICS-M007 系统设置
# ═══════════════════════════════════════════════════════════════


class TestAICSM007Settings:
    def test_m007_001_config_read(self, client):
        """AICS-M007-001 读取系统配置（key → {value, description}）。"""
        cfg = ok(client.get('/api/config'))
        assert 'keywords' in cfg and 'value' in cfg['keywords']
        assert 'ai_model' in cfg

    def test_m007_002_config_update(self, client):
        """AICS-M007-002 更新与新增配置项。"""
        ok(client.put('/api/config', json={'keywords': 'AICS关键词1,AICS关键词2',
                                           'AICS 新配置': 'AICS 新值'}))
        cfg = ok(client.get('/api/config'))
        assert cfg['keywords']['value'] == 'AICS关键词1,AICS关键词2'
        assert cfg['AICS 新配置']['value'] == 'AICS 新值'

    def test_m007_003_options(self, client):
        """AICS-M007-003 下拉选项配置（客户类型/等级/区域）。"""
        opts = ok(client.get('/api/options'))
        assert set(opts) == {'customer_types', 'customer_levels', 'regions'}
        assert len(opts['regions']) >= 30
        # 支持 JSON 覆盖与逗号分隔两种存储
        ok(client.put('/api/config', json={'opt_customer_types': '["AICS类型A","AICS类型B"]'}))
        assert ok(client.get('/api/options'))['customer_types'] == ['AICS类型A', 'AICS类型B']
        ok(client.put('/api/config', json={'opt_regions': '甲省,乙省'}))
        assert ok(client.get('/api/options'))['regions'] == ['甲省', '乙省']

    def test_m007_004_skill_list(self, client):
        """AICS-M007-004 技能列表：内置技能 + 自定义技能。"""
        body = ok(client.get('/api/skills'))
        assert 'builtin' in body and 'custom' in body
        names = [s['name'] for s in body['builtin']]
        assert {'read_database', 'analyze_data', 'crawl_leads',
                'get_config', 'update_config'} <= set(names)

    def test_m007_005_skill_crud(self, client):
        """AICS-M007-005 自定义技能创建 / 编辑 / 启停 / 删除。"""
        sid = created_id(client.post('/api/skills', json={
            'name': 'aics_test_skill', 'description': 'AICS 技能', 'icon': '🔧'}))
        ok(client.put(f'/api/skills/{sid}', json={'description': 'AICS 技能-改'}))
        assert ok(client.post(f'/api/skills/{sid}/toggle'))['is_active'] is False
        assert ok(client.post(f'/api/skills/{sid}/toggle'))['is_active'] is True
        ok(client.delete(f'/api/skills/{sid}'))
        assert not any(s['id'] == sid for s in ok(client.get('/api/skills'))['custom'])

    def test_m007_006_skill_execute(self, client):
        """AICS-M007-006 执行内置技能 read_database / analyze_data / get_config。"""
        db_data = ok(client.post('/api/skills/read_database/execute', json={}))
        assert {'customers', 'leads', 'opportunities', 'contacts', 'activities'} <= set(db_data)
        summary = ok(client.post('/api/skills/analyze_data/execute', json={}))
        assert summary['summary']['leads'] == len(db_data['leads'])
        assert ok(client.post('/api/skills/get_config/execute', json={}))['ai_model']

    def test_m007_007_skill_update_config(self, client):
        """AICS-M007-007 执行 update_config 技能可写入配置。"""
        ok(client.post('/api/skills/update_config/execute',
                       json={'keywords': 'AICS技能写入关键词'}))
        assert ok(client.get('/api/config'))['keywords']['value'] == 'AICS技能写入关键词'

    def test_m007_008_crawl_targets(self, client):
        """AICS-M007-008 采集站点配置读写。"""
        defaults = ok(client.get('/api/config/crawl-targets'))
        assert defaults and 'url' in defaults[0]
        ok(client.put('/api/config/crawl-targets', json=[
            {'name': 'AICS 站点', 'url': 'https://example.com/list', 'enabled': True,
             'keywords': '无人机,林业'}]))
        saved = ok(client.get('/api/config/crawl-targets'))
        assert saved[0]['name'] == 'AICS 站点' and saved[0]['enabled'] is True


# ═══════════════════════════════════════════════════════════════
# AICS-M008 智能建议与每日简报
# ═══════════════════════════════════════════════════════════════


class TestAICSM008Suggestion:
    def test_m008_001_suggestions_shape(self, client):
        """AICS-M008-001 智能建议字段与排序（high → medium → low）。"""
        items = ok(client.get('/api/suggestions'))
        assert isinstance(items, list) and items
        for s in items:
            assert {'type', 'title', 'content', 'priority', 'date'} <= set(s)
        order = {'high': 0, 'medium': 1, 'low': 2}
        assert [order[i['priority']] for i in items] == sorted(order[i['priority']] for i in items)

    def test_m008_002_suggestion_lead_deadline(self, client):
        """AICS-M008-002 临近截止的线索产生高优先级建议。"""
        from datetime import date, timedelta
        due = date.today() + timedelta(days=2)
        make_lead(client, 'AICS 即将截止线索', deadline=due.isoformat())
        items = ok(client.get('/api/suggestions'))
        hit = [s for s in items if s['type'] == 'lead_deadline'
               and 'AICS 即将截止线索' in s['title']]
        assert hit and hit[0]['priority'] == 'high'

    def test_m008_003_suggestion_new_contact(self, client, seed):
        """AICS-M008-003 无联络记录的联系人产生 new_contact 建议。"""
        make_contact(client, 'AICS 新联系人待联络', customer_id=seed['customer'])
        items = ok(client.get('/api/suggestions'))
        assert any(s['type'] == 'new_contact' and 'AICS 新联系人待联络' in s['title']
                   for s in items)

    def test_m008_004_daily_brief(self, client):
        """AICS-M008-004 每日简报四个板块齐全。"""
        body = ok(client.get('/api/daily-brief'))
        assert set(body) == {'today_activities', 'today_followups',
                             'overdue_followups', 'upcoming_deadlines'}

    def test_m008_005_daily_brief_content(self, client, seed):
        """AICS-M008-005 每日简报内容正确：今日联络、逾期计划、7 日内截止线索。"""
        from datetime import date, datetime, timedelta
        today = date.today()
        make_activity(client, 'AICS 今日联络', customer_id=seed['customer'],
                      time=datetime.now().strftime('%Y-%m-%d %H:%M'))
        make_followup(client, 'AICS 逾期计划', customer_id=seed['customer'],
                      plan_date=(today - timedelta(days=3)).isoformat())
        make_lead(client, 'AICS 七日内截止线索',
                  deadline=(today + timedelta(days=5)).isoformat())
        body = ok(client.get('/api/daily-brief'))
        assert any('AICS 今日联络' in (a['title'] or '') for a in body['today_activities'])
        assert any('AICS 今日联络' in (a['content'] or '') for a in body['today_activities'])
        assert any(a['content'] == 'AICS 逾期计划' for a in body['overdue_followups'])
        assert any(l['title'] == 'AICS 七日内截止线索' for l in body['upcoming_deadlines'])


# ═══════════════════════════════════════════════════════════════
# AICS-M009 联络计划
# ═══════════════════════════════════════════════════════════════


class TestAICSM009FollowUp:
    def test_m009_001_list(self, client):
        """AICS-M009-001 联络计划列表字段完整（含来源活动信息）。"""
        rows = ok(client.get('/api/followups'))
        assert rows
        for key in ('id', 'plan_date', 'content', 'customer_name', 'contact_name',
                    'source_activity_id', 'source_activity_content', 'add_to_kanban'):
            assert key in rows[0], f"缺少字段 {key}"

    def test_m009_002_create(self, client, seed):
        """AICS-M009-002 新建联络计划。"""
        fid = make_followup(client, 'AICS 新建计划内容', customer_id=seed['customer'],
                            contact_id=seed['contact'], plan_date='2026-06-28',
                            ai_content='AICS 建议内容', add_to_kanban=True)
        body = ok(client.get(f'/api/followups/{fid}'))
        assert body['content'] == 'AICS 新建计划内容'
        assert body['ai_suggested_content'] == 'AICS 建议内容'
        cards = [c for b in ok(client.get('/api/kanban/boards')) for col in b['columns'] for c in col['cards']]
        assert any(c['source_type'] == 'followup' and c['source_id'] == fid for c in cards)

    def test_m009_003_detail_with_history(self, client, seed):
        """AICS-M009-003 计划详情含该客户/联系人历史联系记录。"""
        make_activity(client, 'AICS 历史联络记录', customer_id=seed['customer'],
                      contact_id=seed['contact'])
        fid = make_followup(client, 'AICS 历史计划', customer_id=seed['customer'],
                            contact_id=seed['contact'], plan_date='2026-07-01')
        body = ok(client.get(f'/api/followups/{fid}'))
        assert any(h['content'] == 'AICS 历史联络记录' for h in body['history'])

    def test_m009_004_update(self, client, seed):
        """AICS-M009-004 编辑联络计划。"""
        fid = make_followup(client, 'AICS 待编辑计划', customer_id=seed['customer'])
        ok(client.put(f'/api/followups/{fid}', json={
            'content': 'AICS 编辑后计划', 'plan_date': '2026-07-15'}))
        body = ok(client.get(f'/api/followups/{fid}'))
        assert body['content'] == 'AICS 编辑后计划'
        assert body['plan_date'] == '2026-07-15'

    def test_m009_005_search_and_status_filter(self, client, seed):
        """AICS-M009-005 内容搜索与 pending/done 状态过滤。"""
        make_followup(client, 'AICS 可搜索计划', customer_id=seed['customer'])
        assert len(ok(client.get('/api/followups?search=AICS 可搜索计划'))) == 1
        assert all(f['actual_date'] is None for f in ok(client.get('/api/followups?status=pending')))

    def test_m009_006_execute_creates_activity(self, client, seed):
        """AICS-M009-006 执行联络计划：标记完成 + 自动生成日常联络 + 闭环下一条计划。"""
        fid = make_followup(client, 'AICS 待执行计划', customer_id=seed['customer'],
                            contact_id=seed['contact'], plan_date='2026-07-01')
        aid = ok(client.post(f'/api/followups/{fid}/execute', json={
            'actual_content': 'AICS 本次联系内容', 'method': '电话',
            'next_time': '2026-07-20', 'next_content': 'AICS 下次联系内容'}))['activity_id']
        plan = ok(client.get(f'/api/followups/{fid}'))
        assert plan['actual_date'] and plan['actual_content'] == 'AICS 本次联系内容'
        act = ok(client.get(f'/api/activities/{aid}'))
        assert act['content'] == 'AICS 本次联系内容' and act['method'] == '电话'
        # 闭环：生成下一条计划
        follow = [f for f in ok(client.get('/api/followups'))
                  if f['content'] == 'AICS 下次联系内容']
        assert len(follow) == 1 and follow[0]['plan_date'].startswith('2026-07-20')
        # 已完成计划进入 done 过滤
        assert any(f['id'] == fid for f in ok(client.get('/api/followups?status=done')))

    def test_m009_007_execute_requires_content(self, client, seed):
        """AICS-M009-007 执行计划必须填写本次联系内容。"""
        fid = make_followup(client, 'AICS 空执行计划', customer_id=seed['customer'])
        assert '请填写本次联系内容' in err(
            client.post(f'/api/followups/{fid}/execute', json={'actual_content': '   '}))

    def test_m009_008_execute_twice_blocked(self, client, seed):
        """AICS-M009-008 已完成计划不可重复执行。"""
        fid = make_followup(client, 'AICS 重复执行计划', customer_id=seed['customer'])
        ok(client.post(f'/api/followups/{fid}/execute', json={'actual_content': '第一次'}))
        assert '不能重复执行' in err(
            client.post(f'/api/followups/{fid}/execute', json={'actual_content': '第二次'}))

    def test_m009_009_delete(self, client, seed):
        """AICS-M009-009 删除联络计划。"""
        fid = make_followup(client, 'AICS 待删除计划', customer_id=seed['customer'])
        ok(client.delete(f'/api/followups/{fid}'))
        assert client.get(f'/api/followups/{fid}').status_code == 404


# ═══════════════════════════════════════════════════════════════
# AICS-M010 工作台与首页
# ═══════════════════════════════════════════════════════════════


class TestAICSM010Dashboard:
    def test_m010_001_homepage(self, client):
        """AICS-M010-001 首页返回 SPA HTML。"""
        r = client.get('/')
        assert r.status_code == 200 and '<!DOCTYPE html>' in r.get_data(as_text=True)

    def test_m010_002_spa_fallback_and_static(self, client):
        """AICS-M010-002 前端路由回退到 SPA 入口，静态资源可直接访问。"""
        assert client.get('/leads').status_code == 200
        assert client.get('/assets/index-CVvyZIj2.css').status_code == 200

    def test_m010_003_stats(self, client):
        """AICS-M010-003 统计卡数据齐全且活跃线索数与列表一致。"""
        body = ok(client.get('/api/dashboard'))
        stats = body['stats']
        assert {'active_leads', 'opportunities', 'today_activities',
                'urgent_leads', 'today_followups'} <= set(stats)
        assert stats['active_leads'] == len(ok(client.get('/api/leads?status=active')))
        assert stats['opportunities'] == len(ok(client.get('/api/opportunities')))

    def test_m010_004_urgent_leads_window(self, client):
        """AICS-M010-004 紧急线索窗口为 0~3 天（当天截止也算紧急）。"""
        from datetime import date, timedelta
        today = date.today()
        make_lead(client, 'AICS 今天截止线索', deadline=today.isoformat())
        make_lead(client, 'AICS 三天后截止线索', deadline=(today + timedelta(days=3)).isoformat())
        make_lead(client, 'AICS 四天后截止线索', deadline=(today + timedelta(days=4)).isoformat())
        titles = [l['title'] for l in ok(client.get('/api/dashboard'))['urgent_leads']]
        assert 'AICS 今天截止线索' in titles
        assert 'AICS 三天后截止线索' in titles
        assert 'AICS 四天后截止线索' not in titles

    def test_m010_005_today_activities_and_followups(self, client, seed):
        """AICS-M010-005 今日联络与今日待联络列表。"""
        from datetime import datetime
        make_activity(client, 'AICS 今日待办联络', customer_id=seed['customer'],
                      time=datetime.now().strftime('%Y-%m-%d %H:%M'))
        make_followup(client, 'AICS 今日待联络计划', customer_id=seed['customer'],
                      plan_date=datetime.now().strftime('%Y-%m-%d'))
        body = ok(client.get('/api/dashboard'))
        assert any('AICS 今日待办联络' in a['content'] for a in body['today_activities'])
        assert any(f['content'] == 'AICS 今日待联络计划' for f in body['today_followups'])

    def test_m010_006_kanban_deadline_reminder(self, client, seed):
        """AICS-M010-006 看板截止提醒仅包含有截止日的卡片。"""
        make_card(client, seed['column'], 'AICS 有截止日卡片', deadline='2026-09-30')
        body = ok(client.get('/api/dashboard'))
        assert all(c['deadline'] for c in body['kanban_cards'])
        assert any(c['title'] == 'AICS 有截止日卡片' for c in body['kanban_cards'])

    def test_m010_007_opportunities_sorted_desc(self, client):
        """AICS-M010-007 工作台商机按创建时间倒序。"""
        make_opportunity(client, 'AICS 最新商机')
        titles = [o['title'] for o in ok(client.get('/api/dashboard'))['opportunities']]
        assert titles[0] == 'AICS 最新商机'


# ═══════════════════════════════════════════════════════════════
# AICS-M011 数据采集（全打桩，不触网）
# ═══════════════════════════════════════════════════════════════


class TestAICSM011Crawl:
    def test_m011_001_trigger_crawl(self, client, monkeypatch):
        """AICS-M011-001 触发采集返回运行中状态。"""
        import app.services.crawler as crawler
        monkeypatch.setattr(crawler, 'start_crawl_background', lambda app: True)
        body = ok(client.post('/api/crawl', json={}))
        assert body['ok'] is True and body['running'] is True

    def test_m011_002_trigger_conflict(self, client, monkeypatch):
        """AICS-M011-002 采集进行中重复触发返回明确提示。"""
        import app.services.crawler as crawler
        monkeypatch.setattr(crawler, 'start_crawl_background', lambda app: False)
        body = ok(client.post('/api/crawl', json={}))
        assert body['ok'] is False and '已在运行中' in body['error']

    def test_m011_003_crawl_status_shape(self, client):
        """AICS-M011-003 采集状态接口字段契约（前端轮询依赖）。"""
        body = ok(client.get('/api/crawl/status'))
        for key in ('running', 'phase', 'progress', 'total', 'current',
                    'count', 'errors', 'message'):
            assert key in body, f"缺少字段 {key}"

    def test_m011_004_crawl_keywords_config(self, client):
        """AICS-M011-004 关键词配置存在且可被采集读取。"""
        from app.services.crawler import get_crawl_keywords
        cfg = ok(client.get('/api/config'))
        assert 'keywords' in cfg
        with client.application.app_context():
            assert get_crawl_keywords()

    def test_m011_005_news_collect_endpoints(self, client, monkeypatch, seed):
        """AICS-M011-005 客户/联系人新闻采集接口（打桩）。"""
        import app.services.news_collector as nc
        monkeypatch.setattr(nc, 'collect_customer_news',
                            lambda cid: {'count': 2, 'errors': [], 'message': 'ok'})
        monkeypatch.setattr(nc, 'collect_contact_news',
                            lambda cid: {'count': 1, 'errors': [], 'message': 'ok'})
        body = ok(client.post(f"/api/customers/{seed['customer']}/collect-news", json={}))
        assert body['ok'] is True and body['count'] == 2
        body = ok(client.post(f"/api/contacts/{seed['contact']}/collect-news", json={}))
        assert body['ok'] is True and body['count'] == 1

    def test_m011_006_news_collect_error_is_graceful(self, client, monkeypatch, seed):
        """AICS-M011-006 采集异常不抛 500，以 ok=false 返回提示。"""
        import app.services.news_collector as nc

        def boom(cid):
            raise RuntimeError('AICS 采集异常')

        monkeypatch.setattr(nc, 'collect_customer_news', boom)
        body = ok(client.post(f"/api/customers/{seed['customer']}/collect-news", json={}))
        assert body['ok'] is False and '采集失败' in body['error']

    def test_m011_007_collect_all(self, client, monkeypatch):
        """AICS-M011-007 批量采集接口。"""
        import app.services.news_collector as nc
        monkeypatch.setattr(nc, 'collect_all', lambda kind='all': {'count': 5, 'errors': []})
        body = ok(client.post('/api/news/collect-all', json={'type': 'all'}))
        assert body['ok'] is True and body['count'] == 5

    def test_m011_008_news_logs(self, client, dbsession):
        """AICS-M011-008 采集日志按时间倒序返回最近记录。"""
        from datetime import datetime
        from app.models import CrawlLog
        dbsession.add(CrawlLog(task_type='客户新闻', sources='AICS 来源', status='partial',
                               items_count=3, error_count=1, message='AICS 日志',
                               started_at=datetime.now(), finished_at=datetime.now()))
        dbsession.commit()
        logs = ok(client.get('/api/news/logs'))
        assert logs[0]['message'] == 'AICS 日志'
        assert {'task_type', 'sources', 'status', 'items_count',
                'error_count', 'started_at', 'finished_at'} <= set(logs[0])

    def test_m011_009_delete_news(self, client, dbsession, seed):
        """AICS-M011-009 删除客户新闻与联系人动态。"""
        from app.models import ContactNews, CustomerNews
        n1 = CustomerNews(customer_id=seed['customer'], title='AICS 待删客户新闻')
        n2 = ContactNews(contact_id=seed['contact'], title='AICS 待删联系人动态')
        dbsession.add_all([n1, n2])
        dbsession.commit()
        ok(client.delete(f'/api/news/customer/{n1.id}'))
        ok(client.delete(f'/api/news/contact/{n2.id}'))
        assert client.delete(f'/api/news/customer/{n1.id}').status_code == 404


# ═══════════════════════════════════════════════════════════════
# AICS-M012 全局规则与接口契约
# ═══════════════════════════════════════════════════════════════


class TestAICSM012Contract:
    def test_m012_001_unknown_api_is_json_404(self, client):
        """AICS-M012-001 未注册的 /api/* 返回 JSON 404，不被 SPA 兜底成 HTML。"""
        r = client.get('/api/does-not-exist')
        assert r.status_code == 404
        assert r.headers['Content-Type'].startswith('application/json')
        assert 'error' in json_of(r)

    def test_m012_002_all_errors_are_json(self, client):
        """AICS-M012-002 所有错误响应统一为 JSON 契约。"""
        cases = [
            ('get', '/api/customers/999999'),
            ('post', '/api/customers'),
            ('put', '/api/leads/999999'),
            ('delete', '/api/contacts/999999'),
        ]
        for method, url in cases:
            r = getattr(client, method)(url)
            assert r.status_code >= 400
            assert r.headers['Content-Type'].startswith('application/json'), \
                f'{method.upper()} {url} 返回了非 JSON'
            assert 'error' in json_of(r)

    def test_m012_003_cors_not_wildcard(self, client):
        """AICS-M012-003 默认不放开任意来源 CORS。"""
        assert client.get('/api/customers').headers.get('Access-Control-Allow-Origin') != '*'

    def test_m012_004_match_level_editable(self, client, seed):
        """AICS-M012-004 线索匹配等级可手工覆盖。"""
        lid = seed['lead_active']
        ok(client.put(f'/api/leads/{lid}', json={'match_level': '中匹配'}))
        assert ok(client.get(f'/api/leads/{lid}'))['match_level'] == '中匹配'

    def test_m012_005_method_not_allowed_is_json_405(self, client):
        """AICS-M012-005 路径已注册但方法不符 → 405 JSON（不得退化为 404/HTML）。"""
        r = client.get('/api/export/leads')  # 该接口仅支持 POST
        assert r.status_code == 405
        assert r.headers['Content-Type'].startswith('application/json')
        assert json_of(r)['error'] == '请求方法不被允许'

    def test_m012_006_error_text_localized(self, client):
        """AICS-M012-006 错误文案统一中文；业务提示（abort description）优先保留。"""
        assert json_of(client.get('/api/nope'))['error'] == '接口不存在'
        assert json_of(client.delete('/api/dashboard'))['error'] == '请求方法不被允许'
        # 业务校验产生的自定义提示不应被通用文案覆盖
        assert '缺少必填字段' in json_of(client.post('/api/customers', json={}))['error']


# ═══════════════════════════════════════════════════════════════
# AICS-M013 数据报表
# ═══════════════════════════════════════════════════════════════


class TestAICSM013Analytics:
    def test_m013_001_shape(self, client):
        """AICS-M013-001 报表四段结构：summary / monthly_leads / funnel / win_loss。"""
        body = ok(client.get('/api/analytics'))
        assert set(body) == {'summary', 'monthly_leads', 'funnel', 'win_loss'}
        assert len(body['monthly_leads']) == 6
        assert {'total_leads', 'total_opportunities', 'total_amount',
                'won_amount', 'conversion_rate', 'total_activities'} <= set(body['summary'])

    def test_m013_002_amount_parsing(self, client):
        """AICS-M013-002 金额支持「万」等后缀，取数值部分累加。"""
        make_opportunity(client, 'AICS 金额商机甲', amount='120万')
        make_opportunity(client, 'AICS 金额商机乙', amount='80.5')
        summary = ok(client.get('/api/analytics'))['summary']
        assert summary['total_amount'] >= 200.5

    def test_m013_003_win_loss_no_double_count(self, client):
        """AICS-M013-003 赢单/丢单/进行中互斥且不重复计数。"""
        make_opportunity(client, 'AICS 丢单商机', current_stage='已丢单', amount='50')
        make_opportunity(client, 'AICS 签约商机', current_stage='合同签约', amount='80')
        body = ok(client.get('/api/analytics'))
        wl = {w['name']: w['value'] for w in body['win_loss']}
        assert wl['赢单'] == 1 and wl['丢单'] == 1
        assert sum(wl.values()) == body['summary']['total_opportunities']

    def test_m013_004_conversion_rate(self, client):
        """AICS-M013-004 转化率 = 已转化线索 / 线索总数。"""
        make_lead(client, 'AICS 转化率线索', purchaser='AICS 转化率采购方')
        leads = ok(client.get('/api/leads'))
        lid = [l['id'] for l in leads if l['title'] == 'AICS 转化率线索'][0]
        client.post(f'/api/leads/{lid}/convert', json={})
        body = ok(client.get('/api/analytics'))
        total = len(ok(client.get('/api/leads')))
        converted = len(ok(client.get('/api/leads?status=converted')))
        assert body['summary']['total_leads'] == total
        assert body['summary']['conversion_rate'] == round(converted / max(total, 1) * 100, 1)

    def test_m013_005_monthly_trend(self, client):
        """AICS-M013-005 月度趋势最近 6 个月，当月线索计入。"""
        make_lead(client, 'AICS 当月线索')
        body = ok(client.get('/api/analytics'))
        assert body['monthly_leads'][-1]['leads'] >= 1
        assert all('month' in m and 'leads' in m and 'converted' in m
                   for m in body['monthly_leads'])

    def test_m013_006_funnel_stages_unique(self, client):
        """AICS-M013-006 漏斗阶段不重复。

        回归：阶段配置表为空时，去重条件 `s not in configured` 恒为真，
        同一阶段的商机条数会原样展开成同名阶段（14 条商机 → 14 个"初步接触"）。
        """
        # 阶段配置表为空 + 多条同阶段商机，复现原始触发条件
        with client.application.app_context():
            from app import db
            from app.models import OpportunityStage
            OpportunityStage.query.delete()
            db.session.commit()
        for i in range(4):
            make_opportunity(client, f'AICS 漏斗商机{i}', current_stage='初步接触', amount='10')

        funnel = ok(client.get('/api/analytics'))['funnel']
        names = [f['stage'] for f in funnel]
        assert len(names) == len(set(names)), f'漏斗阶段重复: {names}'
        # 每个阶段的计数应等于该阶段商机数，且不重复累计
        stages = {o['current_stage'] for o in ok(client.get('/api/opportunities'))}
        assert set(names) == stages
        by_name = {f['stage']: f['count'] for f in funnel}
        for stage in stages:
            expected = len([o for o in ok(client.get('/api/opportunities'))
                            if o['current_stage'] == stage])
            assert by_name[stage] == expected


# ═══════════════════════════════════════════════════════════════
# AICS-M014 数据导出
# ═══════════════════════════════════════════════════════════════


class TestAICSM014Export:
    @pytest.mark.parametrize('etype', ['leads', 'opportunities', 'contacts',
                                       'customers', 'activities', 'followups'])
    def test_m014_001_export_all_types(self, client, etype):
        """AICS-M014-001 六类数据均可导出 CSV（含 UTF-8 BOM 与中文文件名）。"""
        from crm_test_utils import parse_csv
        r = client.post(f'/api/export/{etype}', json={})
        assert r.status_code == 200
        assert r.headers['Content-Type'].startswith('text/csv')
        assert "filename*=UTF-8''" in r.headers['Content-Disposition']
        assert r.get_data().startswith(b'\xef\xbb\xbf')
        header, rows = parse_csv(r)
        assert header and len(header) >= 9
        assert rows, '演示数据应有可导出内容'

    def test_m014_002_export_by_ids(self, client):
        """AICS-M014-002 按 ids 导出仅包含指定记录。"""
        from crm_test_utils import parse_csv
        lid = make_lead(client, 'AICS 导出指定线索')
        _, rows = parse_csv(client.post('/api/export/leads', json={'ids': [lid]}))
        assert len(rows) == 1 and rows[0][1] == 'AICS 导出指定线索'

    def test_m014_003_export_empty(self, client):
        """AICS-M014-003 无数据可导出时返回 400 提示。"""
        assert '当前无数据可导出' in err(
            client.post('/api/export/leads', json={'ids': [999999]}))

    def test_m014_004_export_unknown_type(self, client):
        """AICS-M014-004 未知导出类型返回 400。"""
        assert '不支持的导出类型' in err(client.post('/api/export/bogus', json={}))

    def test_m014_005_export_maps_status(self, client):
        """AICS-M014-005 导出内容做了可读化映射（状态中文、空值 -）。"""
        from crm_test_utils import parse_csv
        lid = make_lead(client, 'AICS 导出映射线索', purchaser='AICS 映射采购方')
        _, rows = parse_csv(client.post('/api/export/leads', json={'ids': [lid]}))
        row = rows[0]
        assert row[12] == '待转化'
        assert '-' in row  # 空值统一为 '-'


# ═══════════════════════════════════════════════════════════════
# AICS-M015 公告全文
# ═══════════════════════════════════════════════════════════════


class TestAICSM015Fulltext:
    def test_m015_001_stored_fulltext(self, client, dbsession):
        """AICS-M015-001 已入库全文直接返回并转为 Markdown。"""
        from app.models import Lead
        lead = Lead(title='AICS 全文线索', status='active',
                    full_text='AICS 公告标题行\n一、项目概况\n本项目采购无人机巡检服务。')
        dbsession.add(lead)
        dbsession.commit()
        body = ok(client.get(f'/api/leads/{lead.id}/fulltext'))
        assert body['source'] == 'stored'
        assert body['text'].startswith('# AICS 公告标题行')
        assert '### 一、项目概况' in body['text']

    def test_m015_002_no_source_url(self, client):
        """AICS-M015-002 无原文链接时返回 400 提示。"""
        lid = make_lead(client, 'AICS 无链接线索')
        assert '无原文链接' in err(client.get(f'/api/leads/{lid}/fulltext'))

    def test_m015_003_ssrf_blocked(self, client):
        """AICS-M015-003 内网/环回地址被 SSRF 防护拦截。"""
        lid = make_lead(client, 'AICS SSRF 线索', source_url='http://127.0.0.1:5001/secret')
        assert '受限地址' in err(client.get(f'/api/leads/{lid}/fulltext'))

    def test_m015_004_invalid_scheme(self, client):
        """AICS-M015-004 非 http(s) 链接被拒绝。"""
        lid = make_lead(client, 'AICS 非法链接线索', source_url='file:///etc/passwd')
        assert '不合法' in err(client.get(f'/api/leads/{lid}/fulltext'))

    def test_m015_005_fetch_and_convert(self, client, monkeypatch):
        """AICS-M015-005 远程抓取并转为近似 Markdown（打桩，不触网）。"""
        import socket

        import requests

        html = ('<html><body><h1>AICS 远程公告</h1><p>正文段落一。</p>'
                '<table><tr><th>项目</th><th>内容</th></tr>'
                '<tr><td>预算</td><td>100</td></tr></table></body></html>')

        class FakeResp:
            status_code = 200
            text = html
            encoding = 'utf-8'
            apparent_encoding = 'utf-8'

        monkeypatch.setattr(socket, 'getaddrinfo',
                            lambda *a, **k: [(2, 1, 6, '', ('93.184.216.34', 0))])
        monkeypatch.setattr(requests, 'get', lambda *a, **k: FakeResp())
        lid = make_lead(client, 'AICS 远程抓取线索', source_url='https://example.com/notice/1')
        body = ok(client.get(f'/api/leads/{lid}/fulltext'))
        assert body['source'] == 'fetched'
        assert '# AICS 远程公告' in body['text']
        assert '| 项目 | 内容 |' in body['text']

    def test_m015_006_remote_error(self, client, monkeypatch):
        """AICS-M015-006 原文站点非 200 时返回 502 提示。"""
        import socket

        import requests

        class FakeResp:
            status_code = 404
            text = 'not found'
            encoding = 'utf-8'
            apparent_encoding = 'utf-8'

        monkeypatch.setattr(socket, 'getaddrinfo',
                            lambda *a, **k: [(2, 1, 6, '', ('93.184.216.34', 0))])
        monkeypatch.setattr(requests, 'get', lambda *a, **k: FakeResp())
        lid = make_lead(client, 'AICS 抓取失败线索', source_url='https://example.com/missing')
        assert 'HTTP 404' in err(client.get(f'/api/leads/{lid}/fulltext'), 502)


if __name__ == '__main__':
    raise SystemExit(pytest.main([os.path.abspath(__file__), '-v', '-p', 'no:cacheprovider']))
