"""操作留痕：线索流水、联系人来源线索与关联商机、联络记录/计划的操作用户。

三块都是「列表里要能看到是谁、什么时候、动了哪条」：
1. 线索的每次人工操作写一条 lead_operations 流水，列表回最近一次；
2. 由线索转化出来的联系人保留来源线索（编号 + 招标公告链接），并能列出多条关联商机；
3. 活动/联络计划带操作人，历史行统一是「系统」。
"""
from crm_test_utils import (
    created_id, make_activity, make_contact, make_followup,
    make_lead, make_opportunity, ok, set_config,
)
from app.models import Contact, Lead, LeadOperation


class TestLeadOperations:
    """线索操作流水表（lead_operations）"""

    def _ops(self, lead_id):
        return LeadOperation.query.filter_by(lead_id=lead_id).order_by(LeadOperation.id).all()

    def test_m017_001_release_and_claim_record_flow(self, client, seed, dbsession):
        """领取/释放各留一条，动作与原因都能追溯。"""
        lead_id = seed['lead_active']
        ok(client.post(f'/api/leads/{lead_id}/release', json={'reason': '地区不符'}))
        ok(client.post(f'/api/leads/{lead_id}/claim', json={}))
        ops = self._ops(lead_id)
        assert [o.action for o in ops] == ['释放', '领取']
        assert ops[0].detail == '地区不符'
        # 测试关掉了鉴权，写入人记「未登录」（与「系统」的无人值守写入区分开）
        assert {o.operator for o in ops} == {'未登录'}

    def test_m017_002_batch_writes_one_row_per_lead(self, client, seed, dbsession):
        """批量释放要逐条留痕，不能只记一次。"""
        other = make_lead(client, '批量留痕-线索')
        body = ok(client.post('/api/leads/batch', json={
            'action': 'release', 'ids': [seed['lead_active'], other], 'reason': '人力不足'}))
        assert body['done'] == 2
        for lead_id in (seed['lead_active'], other):
            assert [o.action for o in self._ops(lead_id)][-1] == '释放'
        assert [o.action for o in self._ops(other)] == ['新建', '释放']

    def test_m017_003_convert_recorded(self, client, dbsession):
        lead_id = make_lead(client, '留痕-转化', purchaser='留痕转化单位')
        ok(client.post(f'/api/leads/{lead_id}/convert', json={'title': '留痕转化商机'}))
        assert [o.action for o in self._ops(lead_id)] == ['新建', '转化']

    def test_m017_004_list_returns_last_operator(self, client, seed):
        lead_id = seed['lead_active']
        ok(client.put(f'/api/leads/{lead_id}', json={'budget': '120'}))
        row = next(r for r in ok(client.get('/api/leads')) if r['id'] == lead_id)
        assert row['operator'] == '未登录'
        assert row['operation'] == '编辑'
        assert row['operated_at']

    def test_m017_005_legacy_lead_falls_back_to_updated_at(self, client, seed, dbsession):
        """流水上线前的老线索没有记录：操作人算「系统」，时间退回行的最后修改时间。"""
        lead_id = seed['lead_active']
        lead = Lead.query.get(lead_id)
        assert self._ops(lead_id) == []
        row = next(r for r in ok(client.get('/api/leads')) if r['id'] == lead_id)
        assert row['operator'] == '系统' and row['operation'] == ''
        assert row['operated_at'] == lead.updated_at.strftime('%Y-%m-%d %H:%M')

    def test_m017_006_hard_delete_keeps_the_trail(self, client, dbsession):
        lead_id = make_lead(client, '留痕-彻底删除')
        ok(client.delete(f'/api/leads/{lead_id}'))
        assert [o.action for o in self._ops(lead_id)] == ['新建', '彻底删除']

    def test_m017_007_operator_is_logged_in_user(self, auth_app, admin_client):
        """开启鉴权时，流水记登录人；领取不传 assignee 也归到登录人名下。"""
        lead_id = created_id(admin_client.post('/api/leads', json={'title': '登录人留痕'}))
        ok(admin_client.post(f'/api/leads/{lead_id}/release', json={'reason': '换人跟进'}))
        ok(admin_client.post(f'/api/leads/{lead_id}/claim', json={}))
        with auth_app.app_context():
            ops = LeadOperation.query.filter_by(lead_id=lead_id).order_by(LeadOperation.id).all()
            assignee = Lead.query.get(lead_id).assignee
        assert [o.action for o in ops] == ['新建', '释放', '领取']
        assert {o.operator for o in ops} == {'admin'}
        assert assignee == 'admin'


class TestContactLeadAndOpportunities:
    """联系人的来源线索与关联商机"""

    def _converted_contact(self, client, bid_type='中标公告'):
        lead_id = created_id(client.post('/api/leads', json={
            'title': f'来源线索-联系人{bid_type}',
            'purchaser': f'来源线索采购单位{bid_type}',
            'contact_name': f'张处长{bid_type}',
            'contact_phone': '13800000000',
            'source_url': 'https://example.com/tender/1',
        }))
        # 类别只由采集写入，手工建档要补类别得走 PUT
        ok(client.put(f'/api/leads/{lead_id}', json={'bid_type': bid_type}))
        ok(client.post(f'/api/leads/{lead_id}/convert', json={'title': '来源线索商机'}))
        name = f'张处长{bid_type}'
        contact_id = next(c['id'] for c in ok(client.get(f'/api/contacts?search={name}'))
                          if c['name'] == name)
        return lead_id, contact_id

    def test_m018_001_contact_keeps_source_lead(self, client, dbsession):
        lead_id, contact_id = self._converted_contact(client)
        lead = Lead.query.get(lead_id)
        detail = ok(client.get(f'/api/contacts/{contact_id}'))
        assert detail['lead']['id'] == lead_id
        assert detail['lead']['serial_no'] == lead.serial_no
        assert detail['lead']['bid_type'] == '中标公告'
        assert detail['lead']['source_url'] == 'https://example.com/tender/1'
        assert '由线索' in detail['notes']
        assert Contact.query.get(contact_id).lead_id == lead_id

    def test_m018_002_list_carries_lead_brief(self, client, dbsession):
        lead_id, contact_id = self._converted_contact(client, bid_type='招标公告')
        row = next(c for c in ok(client.get('/api/contacts')) if c['id'] == contact_id)
        assert row['lead']['id'] == lead_id
        assert row['lead']['bid_type'] == '招标公告'

    def test_m018_003_manual_contact_has_no_lead(self, client, dbsession):
        cid = make_contact(client, '手工联系人')
        assert ok(client.get(f'/api/contacts/{cid}'))['lead'] is None

    def test_m018_004_detail_lists_multiple_opportunities(self, client, dbsession):
        cid = make_contact(client, '多商机联系人')
        o1 = make_opportunity(client, '商机甲', contact_id=cid)
        o2 = make_opportunity(client, '商机乙', contact_id=cid)
        detail = ok(client.get(f'/api/contacts/{cid}'))
        assert {o['id'] for o in detail['opportunities']} == {o1, o2}
        assert all(o['title'] for o in detail['opportunities'])

    def test_m018_005_opportunities_filter_by_contact(self, client, dbsession):
        cid = make_contact(client, '过滤联系人')
        other = make_contact(client, '无关联系人')
        oid = make_opportunity(client, '归属商机', contact_id=cid)
        make_opportunity(client, '他人商机', contact_id=other)
        rows = ok(client.get(f'/api/opportunities?contact_id={cid}'))
        assert [r['id'] for r in rows] == [oid]


class TestOperatorOnContactsActivity:
    """联络记录、联络计划的操作人"""

    def test_m019_001_activity_has_operator_and_contact_filter(self, client, dbsession):
        cid = make_contact(client, '联络人甲')
        aid = make_activity(client, '电话沟通预算', contact_id=cid)
        rows = ok(client.get(f'/api/activities?contact_id={cid}'))
        assert [r['id'] for r in rows] == [aid]
        assert rows[0]['operator'] == '未登录'

    def test_m019_002_activity_opportunity_in_payload(self, client, dbsession):
        cid = make_contact(client, '联络人乙')
        oid = make_opportunity(client, '联络挂商机', contact_id=cid)
        make_activity(client, '约见客户', contact_id=cid, opportunity_id=oid)
        row = ok(client.get(f'/api/activities?contact_id={cid}'))[0]
        assert row['opportunity_id'] == oid and row['opportunity_title'] == '联络挂商机'

    def test_m019_003_followup_operator_and_executor(self, client, dbsession):
        cid = make_contact(client, '计划联系人')
        oid = make_opportunity(client, '计划商机', contact_id=cid)
        fid = make_followup(client, '下周确认评标结果', contact_id=cid, opportunity_id=oid)
        row = ok(client.get(f'/api/followups?contact_id={cid}'))[0]
        assert row['operator'] == '未登录' and row['executed_by'] == ''
        ok(client.post(f'/api/followups/{fid}/execute', json={'actual_content': '已电话确认'}))
        done = next(r for r in ok(client.get(f'/api/followups?contact_id={cid}')) if r['id'] == fid)
        assert done['executed_by'] == '未登录'
        # 执行时补写的联络记录同样带操作人
        act = ok(client.get(f'/api/activities?contact_id={cid}'))[0]
        assert act['operator'] == '未登录'

    def test_m019_004_operator_is_logged_in_user(self, admin_client):
        cid = created_id(admin_client.post('/api/contacts', json={'name': '登录人联系人'}))
        ok(admin_client.post('/api/activities', json={'content': '登录人写的联络', 'contact_id': cid}))
        row = ok(admin_client.get(f'/api/activities?contact_id={cid}'))[0]
        assert row['operator'] == 'admin'


class TestCustomerTypesOption:
    """客户类型枚举（v5.2 起的六类）"""

    def test_m020_001_default_types(self, client, dbsession):
        assert ok(client.get('/api/options'))['customer_types'] == [
            '政府/林场', '集成伙伴', '林业行业', '其他占位1', '其他占位2', '其他占位3']

    def test_m020_002_config_override_still_wins(self, app, client, dbsession):
        set_config(app, opt_customer_types='["自定义A","自定义B"]')
        assert ok(client.get('/api/options'))['customer_types'] == ['自定义A', '自定义B']


# 建库脚本 = 实机升级到 v5.2 之前那一版：没有 operator / lead_id / lead_operations。
_LEGACY_SCHEMA = """
CREATE TABLE leads (
    id INTEGER PRIMARY KEY, bid_number VARCHAR(100), title VARCHAR(500) NOT NULL,
    budget VARCHAR(50), deadline DATETIME, region VARCHAR(100), purchaser VARCHAR(200),
    service_content TEXT, match_keywords TEXT, match_level VARCHAR(20), match_score INTEGER,
    match_reason TEXT, contact_name VARCHAR(100), contact_phone VARCHAR(100),
    address VARCHAR(300), assignee VARCHAR(50), source_url VARCHAR(1000),
    source_platform VARCHAR(100), status VARCHAR(20), customer_id INTEGER,
    created_at DATETIME, updated_at DATETIME, bid_type VARCHAR(50), winner VARCHAR(200),
    related_customer_ids VARCHAR(500), serial_no VARCHAR(20), full_text TEXT,
    reason VARCHAR(300), is_deleted BOOLEAN NOT NULL DEFAULT 0
);
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, nickname VARCHAR(50),
    title VARCHAR(100), phone VARCHAR(50), email VARCHAR(100), wechat VARCHAR(50),
    role VARCHAR(50), tags TEXT, avatar VARCHAR(10), business_scope TEXT,
    importance VARCHAR(20), customer_id INTEGER, notes TEXT, created_at DATETIME,
    updated_at DATETIME, is_deleted BOOLEAN NOT NULL DEFAULT 0
);
CREATE TABLE activities (
    id INTEGER PRIMARY KEY, title VARCHAR(300), customer_id INTEGER, contact_id INTEGER,
    opportunity_id INTEGER, lead_id INTEGER, method VARCHAR(50), content TEXT,
    activity_time DATETIME, next_followup_time DATETIME, next_followup_content TEXT,
    add_to_kanban BOOLEAN, created_at DATETIME, updated_at DATETIME,
    is_deleted BOOLEAN NOT NULL DEFAULT 0
);
CREATE TABLE followups (
    id INTEGER PRIMARY KEY, contact_id INTEGER, customer_id INTEGER, opportunity_id INTEGER,
    lead_id INTEGER, plan_date DATETIME, content TEXT, ai_suggested_content TEXT,
    actual_date DATETIME, actual_content TEXT, add_to_kanban BOOLEAN, kanban_card_id INTEGER,
    source_activity_id INTEGER, created_at DATETIME, updated_at DATETIME,
    is_deleted BOOLEAN NOT NULL DEFAULT 0
);
INSERT INTO activities (id, content, activity_time, is_deleted) VALUES (1, '历史记录', '2026-09-01 10:00:00', 0);
INSERT INTO followups (id, content, plan_date, is_deleted) VALUES (1, '历史计划', '2026-09-05', 0);
"""


class TestLegacyDatabaseUpgrade:
    """老库升级：新列由 _migrate_db 补上，历史行的操作人回填成「系统」"""

    def test_m021_001_new_columns_added_and_backfilled(self, tmp_path, monkeypatch):
        import sqlite3
        from sqlalchemy import inspect, text
        from app import create_app, db

        db_path = str(tmp_path / 'legacy.db')
        conn = sqlite3.connect(db_path)
        conn.executescript(_LEGACY_SCHEMA)
        conn.commit()
        conn.close()

        monkeypatch.setenv('CRM_SKIP_SEED', '1')  # 老库里只有 v5.2 之前的表，seed 会写不进去
        application = create_app(config={
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + db_path,
            'TESTING': True,
            'AUTH_DISABLED': True,
        })
        with application.app_context():
            inspector = inspect(db.engine)
            for table, column in [('activities', 'operator'), ('followups', 'operator'),
                                  ('followups', 'executed_by'), ('contacts', 'lead_id')]:
                assert column in [c['name'] for c in inspector.get_columns(table)], f'{table}.{column} 未补齐'
            assert inspector.has_table('lead_operations')

            # 存量行必须拿到「系统」，不能是 NULL（否则列表要到处判空）
            raw = sqlite3.connect(db_path)
            assert raw.execute("SELECT operator FROM activities WHERE id=1").fetchone()[0] == '系统'
            assert raw.execute("SELECT operator FROM followups WHERE id=1").fetchone()[0] == '系统'
            raw.close()

            # 二次启动不能再报错（幂等）
            from app import _migrate_db
            _migrate_db()
            assert 'operator' in [c['name'] for c in inspect(db.engine).get_columns('activities')]
