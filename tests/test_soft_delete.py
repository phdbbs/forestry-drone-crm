"""逻辑删除：所有删除只打 is_deleted 标记，行永不从库里消失。

覆盖三件事：
1. 删除后在列表/详情/搜索/统计/导出里都看不见；
2. 行仍在库里且带上标记（审计与将来恢复的依据）；
3. 取号与采集去重必须仍能「看见」已删行，否则会复用流水号、把删掉的公告再采回来。
"""
from datetime import datetime

from crm_test_utils import (
    created_id, err, make_activity, make_contact, make_lead,
    make_opportunity, ok, parse_csv,
)
from app import db
from app.models import (
    Activity, Contact, ContactNews, CrawlLog, FollowUp, KanbanBoard, KanbanCard,
    KanbanColumn, Lead, Opportunity, Skill, StageRecord, User,
)


def _kept(model, obj_id):
    """绕过软删过滤器读原始行，用于断言「没有物理删除」。"""
    return db.session.query(model).filter(model.id == obj_id) \
        .execution_options(include_deleted=True).first()


def _titles(client, path='/api/leads'):
    return [r['title'] for r in ok(client.get(path))]


class TestInvisibleButPresent:
    def test_deleted_lead_is_gone_from_every_read(self, client, dbsession, fresh_session):
        title = '逻辑删除-线索'
        lead_id = make_lead(client, title)
        ok(client.delete(f'/api/leads/{lead_id}'))
        fresh_session()

        assert title not in _titles(client)
        assert client.get(f'/api/leads/{lead_id}').status_code == 404
        assert lead_id not in ok(client.get(f'/api/leads/search?q={title}'))['ids']
        results = ok(client.get('/api/search?q=' + title))['results']
        assert [r for r in results if r['type'] == 'lead'] == []

        with client.application.app_context():
            kept = _kept(Lead, lead_id)
            assert kept is not None and kept.is_deleted

    def test_deleted_lead_left_export_csv(self, client, dbsession, fresh_session):
        gone = '逻辑删除-已消失'
        keep = '逻辑删除-仍在'
        lead_id = make_lead(client, gone)
        make_lead(client, keep)
        assert client.post('/api/export/leads', json={'ids': [lead_id]}).status_code == 200

        ok(client.delete(f'/api/leads/{lead_id}'))
        fresh_session()
        assert err(client.post('/api/export/leads', json={'ids': [lead_id]}))
        _, rows = parse_csv(client.post('/api/export/leads', json={}))
        text = '\n'.join(','.join(r) for r in rows)
        assert keep in text and gone not in text

    def test_deleted_lead_drops_list_total_and_stats(self, client, dbsession):
        total = ok(client.get('/api/leads?page_size=1'))['total']
        stats = ok(client.get('/api/dashboard'))['stats']

        lead_id = make_lead(client, '逻辑删除-分页', status='active')
        assert ok(client.get('/api/leads?page_size=1'))['total'] == total + 1
        assert ok(client.get('/api/dashboard'))['stats']['active_leads'] == stats['active_leads'] + 1

        ok(client.delete(f'/api/leads/{lead_id}'))
        assert ok(client.get('/api/leads?page_size=1'))['total'] == total
        assert ok(client.get('/api/dashboard'))['stats']['active_leads'] == stats['active_leads']

    def test_deleted_contact_keeps_row_and_hides_its_news(self, client, dbsession, seed, fresh_session):
        name = '逻辑删除-联系人'
        cid = make_contact(client, name, customer_id=seed['customer'])
        with client.application.app_context():
            news = ContactNews(contact_id=cid, customer_id=seed['customer'],
                               title='逻辑删除-联系人新闻', url='http://example.test/cn/1')
            db.session.add(news)
            db.session.commit()
            news_id = news.id

        ok(client.delete(f'/api/contacts/{cid}'))
        fresh_session()
        assert name not in [c['name'] for c in ok(client.get('/api/contacts'))]
        assert ContactNews.query.filter_by(id=news_id).first() is None
        with client.application.app_context():
            assert _kept(Contact, cid).is_deleted
            assert _kept(ContactNews, news_id).is_deleted

    def test_deleted_customer_news_row_stays_auditable(self, client, dbsession, seed, fresh_session):
        with client.application.app_context():
            from app.models import CustomerNews
            news = CustomerNews(customer_id=seed['customer'], title='逻辑删除-新闻',
                                url='http://example.test/news/gone')
            db.session.add(news)
            db.session.commit()
            news_id = news.id

        ok(client.delete(f'/api/news/customer/{news_id}'))
        fresh_session()
        assert news_id not in [n['id'] for n in ok(client.get(f'/api/customers/{seed["customer"]}/news'))]
        with client.application.app_context():
            assert _kept(CustomerNews, news_id).is_deleted

    def test_deleted_children_disappear_from_parent_views(self, client, dbsession, fresh_session):
        """客户列表计数、客户详情、商机详情的子记录都走关系加载，同样得屏蔽墓碑行。"""
        cid = created_id(client.post('/api/customers', json={'name': '逻辑删除-父客户'}))
        ctid = make_contact(client, '逻辑删除-子联系人', customer_id=cid)
        oid = make_opportunity(client, '逻辑删除-子商机', customer_id=cid)
        aid = make_activity(client, '逻辑删除-子活动', opportunity_id=oid)
        with client.application.app_context():
            from app.models import CustomerNews
            news = CustomerNews(customer_id=cid, title='逻辑删除-子新闻', url='http://example.test/child')
            news.is_deleted = True
            db.session.add(news)
            db.session.get(Contact, ctid).is_deleted = True
            db.session.get(Activity, aid).is_deleted = True
            db.session.commit()

        fresh_session()
        row = next(r for r in ok(client.get('/api/customers')) if r['id'] == cid)
        assert (row['contact_count'], row['news_count']) == (0, 0)
        detail = ok(client.get(f'/api/customers/{cid}'))
        assert ctid not in [x['id'] for x in detail['contacts']]
        assert detail['news'] == []
        assert aid not in [x['id'] for x in ok(client.get(f'/api/opportunities/{oid}'))['activities']]

    def test_stage_delete_hides_list_but_keeps_opportunity_text(self, client, dbsession, fresh_session):
        name = '逻辑删除-阶段'
        stage_id = created_id(client.post('/api/stages', json={'name': name}))
        oid = make_opportunity(client, '逻辑删除-阶段商机', current_stage=name)
        ok(client.delete(f'/api/stages/{stage_id}'))
        fresh_session()
        assert name not in [s['name'] for s in ok(client.get('/api/stages'))]
        assert ok(client.get(f'/api/opportunities/{oid}'))['current_stage'] == name
        with client.application.app_context():
            assert _kept(Opportunity, oid).current_stage == name


class TestCascadeMarking:
    def test_board_delete_marks_columns_and_cards(self, client, dbsession, seed, fresh_session):
        board_id = created_id(client.post('/api/kanban/boards', json={'name': '逻辑删除-看板'}))
        col_id = created_id(client.post(f'/api/kanban/boards/{board_id}/columns', json={'name': '列一'}))
        card_id = created_id(client.post('/api/kanban/cards', json={
            'column_id': col_id, 'title': '逻辑删除-卡片'}))

        ok(client.delete(f'/api/kanban/boards/{board_id}'))
        fresh_session()
        assert board_id not in [b['id'] for b in ok(client.get('/api/kanban/boards'))]
        with client.application.app_context():
            for model, pk in ((KanbanBoard, board_id), (KanbanColumn, col_id), (KanbanCard, card_id)):
                assert _kept(model, pk).is_deleted, model

    def test_column_delete_marks_its_cards(self, client, dbsession, seed, fresh_session):
        board_id = created_id(client.post('/api/kanban/boards', json={'name': '逻辑删除-看板2'}))
        col_id = created_id(client.post(f'/api/kanban/boards/{board_id}/columns', json={'name': '列二'}))
        card_id = created_id(client.post('/api/kanban/cards', json={'column_id': col_id, 'title': '卡三'}))

        ok(client.delete(f'/api/kanban/columns/{col_id}'))
        fresh_session()
        board = next(b for b in ok(client.get('/api/kanban/boards')) if b['id'] == board_id)
        # 关系加载同样被过滤器拦住：列不见了，挂在它下面的卡片也不会再被带出来
        assert col_id not in [c['id'] for c in board['columns']]
        assert card_id not in [k['id'] for c in board['columns'] for k in c['cards']]
        with client.application.app_context():
            assert _kept(KanbanCard, card_id).is_deleted

    def test_opportunity_delete_marks_stage_records(self, client, dbsession):
        oid = make_opportunity(client, '逻辑删除-商机', current_stage='初步接触')
        ok(client.put(f'/api/opportunities/{oid}', json={'current_stage': '方案报价'}))
        with client.application.app_context():
            rec_id = StageRecord.query.filter_by(opportunity_id=oid).first().id

        ok(client.delete(f'/api/opportunities/{oid}'))
        with client.application.app_context():
            assert _kept(StageRecord, rec_id).is_deleted

    def test_followup_delete_removes_its_kanban_card(self, client, dbsession, seed, fresh_session):
        fu_id = created_id(client.post('/api/followups', json={
            'customer_id': seed['customer'], 'content': '逻辑删除-计划', 'add_to_kanban': True}))
        with client.application.app_context():
            card_id = db.session.get(FollowUp, fu_id).kanban_card_id
        assert card_id, '建卡时未记录 kanban_card_id，删除计划就带不走卡片'

        ok(client.delete(f'/api/followups/{fu_id}'))
        fresh_session()
        assert fu_id not in [f['id'] for f in ok(client.get('/api/followups'))]
        with client.application.app_context():
            assert _kept(KanbanCard, card_id).is_deleted

    def test_activity_delete_marks_unexecuted_plan_only(self, client, dbsession, seed):
        act_id = make_activity(client, '逻辑删除-活动', customer_id=seed['customer'],
                               next_time='2026-12-01', next_content='下月回访')
        with client.application.app_context():
            planned = FollowUp.query.filter_by(source_activity_id=act_id).one()
            done = FollowUp(customer_id=seed['customer'], content='已执行计划',
                            actual_date=datetime.now())
            db.session.add(done)
            db.session.commit()
            planned_id, done_id = planned.id, done.id

        ok(client.delete(f'/api/activities/{act_id}'))
        with client.application.app_context():
            assert _kept(FollowUp, planned_id).is_deleted
            assert not _kept(FollowUp, done_id).is_deleted

    def test_contact_delete_unlinks_activities_without_touching_tombstones(self, client, dbsession, seed, fresh_session):
        """删联系人会清空其活动的 contact_id，但已删的活动不该被顺带改掉。"""
        keep_cid = make_contact(client, '逻辑删除-保留联系人', customer_id=seed['customer'])
        del_cid = make_contact(client, '逻辑删除-被删联系人', customer_id=seed['customer'])
        live_act = make_activity(client, '逻辑删除-在架活动', customer_id=seed['customer'], contact_id=del_cid)
        gone_act = make_activity(client, '逻辑删除-已删活动', customer_id=seed['customer'], contact_id=del_cid)
        with client.application.app_context():
            db.session.get(Activity, gone_act).is_deleted = True
            db.session.commit()

        ok(client.delete(f'/api/contacts/{del_cid}'))
        with client.application.app_context():
            assert _kept(Activity, live_act).contact_id is None
            assert _kept(Activity, gone_act).contact_id == del_cid
        fresh_session()
        assert ok(client.get(f'/api/activities/{live_act}'))['contact_id'] is None
        assert keep_cid


class TestTombstonesStillCountForIdentity:
    """墓碑行仍参与唯一性判断：流水号不复用、公告不重采、用户名可复用。"""

    def test_serial_skips_the_deleted_lead_number(self, client, dbsession):
        from app.services.serial import gen_serial
        today = datetime.now()
        taken = gen_serial(today)
        with client.application.app_context():
            lead = Lead(title='逻辑删除-占号', serial_no=taken, status='active')
            db.session.add(lead)
            db.session.commit()
            lead.is_deleted = True
            db.session.commit()

        assert gen_serial(today) != taken

    def test_crawl_dedup_sees_the_deleted_lead_url(self, client, dbsession):
        url = 'http://example.test/crm/deleted-once'
        lead_id = make_lead(client, '逻辑删除-公告', source_url=url)
        ok(client.delete(f'/api/leads/{lead_id}'))
        with client.application.app_context():
            # crawler.py 用同样的取法：已入库 URL 含墓碑行，否则删掉的公告每轮都被采回
            urls = {u for (u,) in db.session.query(Lead.source_url)
                    .execution_options(include_deleted=True).all() if u}
            assert url in urls
            assert Lead.query.filter_by(source_url=url).first() is None

    def test_deleted_crawl_log_is_marked_not_deleted(self, client, dbsession, fresh_session):
        with client.application.app_context():
            log = CrawlLog(task_type='lead', status='success', items_count=1,
                           started_at=datetime.now())
            db.session.add(log)
            db.session.commit()
            log_id = log.id

        assert ok(client.delete('/api/crawl/logs?task_type=lead'))['deleted'] == 1
        fresh_session()
        assert log_id not in [r['id'] for r in ok(client.get('/api/crawl/logs'))['items']]
        with client.application.app_context():
            assert _kept(CrawlLog, log_id).is_deleted

    def test_deleted_skill_name_can_be_reused(self, client, dbsession, fresh_session):
        """skills.name 是硬 UNIQUE：墓碑行占着名字，重建时复用那一行而不是插入冲突。"""
        name = '逻辑删除-技能'
        sid = created_id(client.post('/api/skills', json={'name': name, 'description': '旧'}))
        ok(client.delete(f'/api/skills/{sid}'))
        fresh_session()
        assert name not in [s['name'] for s in ok(client.get('/api/skills'))['custom']]

        assert ok(client.post('/api/skills', json={'name': name, 'description': '新'}))['id'] == sid
        with client.application.app_context():
            assert not _kept(Skill, sid).is_deleted


class TestNoPhysicalDeleteRemains:
    """守住规矩：业务代码里不允许再出现物理删除。"""

    def test_app_code_has_no_delete_statements(self):
        import pathlib
        import re
        root = pathlib.Path(__file__).resolve().parents[1] / 'app'
        patterns = [re.compile(r'session\.delete\('), re.compile(r'\bquery\b.*\.delete\(')]
        offenders = []
        for py in root.rglob('*.py'):
            if 'static' in py.parts:
                continue
            for lineno, line in enumerate(py.read_text(encoding='utf-8').splitlines(), 1):
                if any(p.search(line) for p in patterns):
                    offenders.append(f'{py.relative_to(root)}:{lineno}')
        assert offenders == []

    def test_every_business_model_has_the_flag(self):
        from app import db
        missing = [m.class_.__name__ for m in db.Model.registry.mappers
                   if m.class_.__tablename__ != 'system_config'
                   and not hasattr(m.class_, 'is_deleted')]
        assert missing == []

    def test_account_delete_keeps_row(self, auth_app, admin_client):
        uid = ok(admin_client.post('/api/users', json={
            'username': 'wanglin', 'password': 'Sales123'}), 201)['id']
        ok(admin_client.delete(f'/api/users/{uid}'))
        with auth_app.app_context():
            assert _kept(User, uid).is_deleted
            assert User.query.filter_by(id=uid).first() is None

    def test_username_index_only_covers_live_accounts(self, auth_app, admin_client):
        """部分唯一索引：活跃账号之间用户名唯一，已删账号不占名。"""
        uid = ok(admin_client.post('/api/users', json={
            'username': 'dup', 'password': 'Sales123'}), 201)['id']
        assert admin_client.post('/api/users', json={
            'username': 'dup', 'password': 'Sales123'}).status_code == 400
        ok(admin_client.delete(f'/api/users/{uid}'))
        assert admin_client.post('/api/users', json={
            'username': 'dup', 'password': 'Sales123'}).status_code == 201
