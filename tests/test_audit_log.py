"""操作日志：全量记账、每日汇总、管理员可见。

四块契约：
1. 中间件按「方法 + 路径」给每个 /api 请求定动作与模块，失败请求同样留痕；
2. 凭据字段永不进日志（detail 里只出现字段名）；
3. 每日汇总按 (天, 用户, 动作, 模块) 预聚合，可重复生成而不产生第二行；
4. /api/audit/* 只有管理员能读，/api/track 人人可写。
"""
from datetime import datetime, timedelta

from crm_test_utils import (
    auth_login, auth_setup, created_id, err, make_lead, ok,
)
from app.models import OperationLog, OperationSummary
from app.services import audit


def _rows(**kw):
    q = OperationLog.query
    for key, value in kw.items():
        q = q.filter(getattr(OperationLog, key) == value)
    return q.order_by(OperationLog.id).all()


def _one(**kw):
    rows = _rows(**kw)
    assert len(rows) == 1, f"期望 1 条 {kw}，实际 {len(rows)} 条：{[(r.action, r.detail) for r in rows]}"
    return rows[0]


def _rows_of(auth_app, **kw):
    """鉴权用例要查自己那个库。

    dbsession 夹具绑的是另一个 app（AUTH_DISABLED 那个），在它的上下文里
    查 OperationLog 查的是空库，日志断言会假绿/假红。
    """
    with auth_app.app_context():
        return _rows(**kw)


class TestAuditMiddleware:
    """请求级记账：动作分类、内容文案、脱敏与噪音排除。"""

    def test_m022_001_query_list_logged(self, client, dbsession):
        ok(client.get('/api/leads?status=active&q=松材'))
        row = _one(action='查询', module='线索')
        assert '查看线索列表' in row.detail
        assert 'status=active' in row.detail and 'q=松材' in row.detail
        assert (row.method, row.status_code, row.user) == ('GET', 200, '未登录')

    def test_m022_002_query_detail_logged_with_id(self, client, seed, dbsession):
        ok(client.get(f'/api/leads/{seed["lead_active"]}'))
        row = _one(action='查询', module='线索')
        assert f'#{seed["lead_active"]}' in row.detail and '详情' in row.detail

    def test_m022_003_create_logged_with_name_and_new_id(self, client, dbsession):
        new_id = created_id(client.post('/api/customers', json={'name': '日志-新增客户'}))
        row = _one(action='新增', module='客户')
        assert '日志-新增客户' in row.detail and f'#{new_id}' in row.detail

    def test_m022_004_update_lists_changed_fields(self, client, seed, dbsession):
        ok(client.put(f'/api/customers/{seed["customer"]}', json={'level': 'A', 'remark': 'x'}))
        row = _one(action='修改', module='客户')
        assert 'level' in row.detail and 'remark' in row.detail

    def test_m022_005_delete_logged(self, client, seed, dbsession):
        ok(client.delete(f'/api/customers/{seed["customer"]}'))
        assert _one(action='删除', module='客户').detail.endswith(f'#{seed["customer"]}')

    def test_m022_006_special_paths_get_their_own_action(self, client, seed, dbsession):
        """领取/释放/转化/批量不能被统统计成「新增」，否则日志没有可读性。"""
        lead_id = seed['lead_active']
        other = make_lead(client, '日志-批量线索')
        ok(client.post(f'/api/leads/{lead_id}/release', json={'reason': '地区不符'}))
        ok(client.post(f'/api/leads/{lead_id}/claim', json={}))
        ok(client.post('/api/leads/batch', json={'action': 'release', 'ids': [other], 'reason': '人力不足'}))
        actions = [r.action for r in _rows(module='线索')]
        assert '释放' in actions and '领取' in actions and '批量操作' in actions

    def test_m022_007_never_logs_credentials(self, client, dbsession):
        """口令/API key 只留字段名：日志表被导出时不该带走凭据。"""
        ok(client.post('/api/users', json={'username': 'loguser', 'password': 'Sup3rSecret!'}), 201)
        row = _one(action='新增', module='账号管理')
        assert 'Sup3rSecret!' not in row.detail
        for r in _rows():
            assert 'Sup3rSecret!' not in (r.detail or '')

    def test_m022_008_failed_login_recorded_as_login(self, auth_app, auth_client):
        """未初始化时的登录失败也要留痕，且记下被尝试的账号。"""
        auth_client.post('/api/auth/login', json={'username': 'ghost', 'password': 'x'})
        rows = _rows_of(auth_app, action='登录')
        assert len(rows) == 1
        assert rows[0].status_code >= 400 and 'ghost' in rows[0].detail

    def test_m022_009_login_success_uses_real_username(self, auth_app, auth_client):
        ok(auth_setup(auth_client))
        ok(auth_login(auth_client))
        rows = _rows_of(auth_app, action='登录', status_code=200)
        assert len(rows) == 1
        assert rows[0].user == 'admin' and rows[0].detail == '登录成功'

    def test_m022_010_static_and_track_not_double_logged(self, client, dbsession):
        """页面请求、埋点接口与采集进度轮询都不该多记一行噪音。"""
        client.get('/')
        client.get('/assets/nope.js')
        ok(client.post('/api/track', json={'page': '线索管理', 'target': '批量释放'}))
        assert _rows(path='/') == []
        assert len(_rows(action='点击')) == 1
        click = _rows(action='点击')[0]
        assert click.module == '页面' and '批量释放' in click.detail and '线索管理' in click.detail

    def test_m022_011_crawler_writes_system_row(self, app, dbsession):
        """采集线程没有请求上下文，收尾时自己补一行「采集」，用户是「系统」。"""
        from app.services import crawl_log

        log = crawl_log.start_log('定时采集')
        crawl_log.finish_log(log, items_count=3, errors=[])
        row = _one(action='采集', user='系统')
        assert '新增 3 条' in row.detail and row.module == '采集'

    def test_m022_012_log_failure_does_not_break_request(self, app, monkeypatch):
        """日志写不进去（库锁、磁盘抖动）只能丢这一行，绝不能变成用户看到的 500。"""
        from app import db

        def _boom(*a, **kw):
            raise RuntimeError('disk I/O error')

        monkeypatch.setattr(db.session, 'add', _boom)
        assert app.test_client().get('/api/leads').status_code == 200

    def test_m022_013_record_reports_failure_instead_of_raising(self, app, monkeypatch):
        from app import db

        def _boom(*a, **kw):
            raise RuntimeError('database is locked')

        monkeypatch.setattr(db.session, 'commit', _boom)
        assert audit.record('查询', '线索', '手工调用') is False

    def test_m022_014_crawl_status_poll_not_logged(self, client, dbsession):
        """采集期间前端每 6 秒轮一次进度，不算用户操作，否则一次采集刷出几十行「查询」。"""
        for _ in range(3):
            ok(client.get('/api/crawl/status'))
        assert _rows(path='/api/crawl/status') == []


class TestAuditSummary:
    """每日汇总：聚合口径、幂等归档、启动补齐。"""

    def test_m023_001_aggregate_counts_by_action_and_user(self, app, client, dbsession):
        ok(client.get('/api/leads'))
        ok(client.get('/api/customers'))
        ok(client.post('/api/customers', json={'name': '日志-汇总客户'}))
        today = datetime.now().strftime('%Y-%m-%d')
        data = audit.summarize_day(today)
        assert data['total'] == 3
        assert data['by_action']['查询'] == 2 and data['by_action']['新增'] == 1
        assert data['by_user'] == {'未登录': 3}
        assert data['active_users'] == 1

    def test_m023_002_headline_reads_like_a_summary(self, app, client, dbsession):
        ok(client.get('/api/leads'))
        text = audit.summarize_day(datetime.now().strftime('%Y-%m-%d'))['headline']
        assert text.startswith(datetime.now().strftime('%Y-%m-%d'))
        assert '查询' in text and text.endswith('。')

    def test_m023_003_archive_is_idempotent(self, app, client, dbsession):
        ok(client.get('/api/leads'))
        day = datetime.now().strftime('%Y-%m-%d')
        audit.archive_day(day)
        audit.archive_day(day)
        rows = OperationSummary.query.filter_by(day=day).all()
        assert len(rows) == 1
        assert rows[0].total == 1 and rows[0].active_users == 1

    def test_m023_004_empty_day_archives_zero(self, app, dbsession):
        data = audit.archive_day('2000-01-01')
        assert data['total'] == 0 and data['headline'] == '2000-01-01 无操作记录。'

    def test_m023_005_ensure_recent_summaries_skips_empty_days(self, app, client, dbsession):
        ok(client.get('/api/leads'))
        done = audit.ensure_recent_summaries(days=7)
        # 今天还没到归档口径（只补 1..7 天前），有日志的日子才建，空日不建
        assert done == []
        assert OperationSummary.query.count() == 0

    def test_m023_006_summary_range_marks_archived(self, app, client, dbsession):
        ok(client.get('/api/leads'))
        today = datetime.now().strftime('%Y-%m-%d')
        days = audit.summary_range(days=3)
        assert [d['day'] for d in days] == [(datetime.now() - timedelta(days=n)).strftime('%Y-%m-%d')
                                            for n in (2, 1, 0)]
        assert days[-1]['archived'] is False and days[-1]['total'] >= 1
        audit.archive_day(today)
        days = audit.summary_range(days=3)
        assert days[-1]['archived'] is True


class TestAuditEndpoints:
    """读接口：筛选、分页、统计、导出与权限边界。"""

    def test_m024_001_logs_list_shape(self, client, dbsession):
        ok(client.get('/api/leads'))
        ok(client.delete('/api/customers/1'))
        body = ok(client.get('/api/audit/logs?page=1&page_size=10'))
        assert body['total'] == 2
        assert {'time', 'user', 'action', 'module', 'detail', 'status_code', 'ip'} <= set(body['items'][0])
        assert body['actions'] == ['删除', '查询']
        assert body['stats']['by_action']['查询'] == 1

    def test_m024_002_filters_by_action_user_and_keyword(self, client, seed, dbsession):
        ok(client.get('/api/leads'))
        ok(client.post('/api/customers', json={'name': '日志-筛选客户'}))
        assert {r['action'] for r in ok(client.get('/api/audit/logs?action=新增'))['items']} == {'新增'}
        assert ok(client.get('/api/audit/logs?user=不存在的人'))['total'] == 0
        assert ok(client.get('/api/audit/logs?q=筛选客户'))['total'] == 1

    def test_m024_003_only_failures_filter(self, client, dbsession):
        client.delete('/api/customers/999999')
        ok(client.get('/api/leads'))
        body = ok(client.get('/api/audit/logs?result=fail'))
        assert body['total'] == 1 and body['stats']['failures'] == 1
        assert body['items'][0]['status_code'] == 404

    def test_m024_004_summary_and_rebuild(self, client, dbsession):
        ok(client.get('/api/leads'))
        body = ok(client.get('/api/audit/summary?days=2'))
        assert len(body['days']) == 2 and body['days'][-1]['total'] >= 1
        day = datetime.now().strftime('%Y-%m-%d')
        r = ok(client.post('/api/audit/summary', json={'day': day}))
        assert r['ok'] and r['summary']['total'] >= 1
        assert OperationSummary.query.filter_by(day=day).count() == 1

    def test_m024_005_bad_date_rejected(self, client):
        assert '格式' in err(client.post('/api/audit/summary', json={'day': 'today'}), 400)

    def test_m024_006_export_csv(self, client, dbsession):
        ok(client.get('/api/leads'))
        resp = client.get('/api/audit/export?days=all')
        assert resp.status_code == 200
        text = resp.get_data().decode('utf-8-sig')
        assert text.splitlines()[0].startswith('时间,用户,操作,模块,操作内容')
        assert '查看线索列表' in text

    def test_m024_007_export_without_rows_rejected(self, client):
        assert err(client.get('/api/audit/export?user=没人'), 400)

    def test_m024_008_admin_only_read(self, admin_client, auth_app):
        """管理员能读，普通销售连读日志都不该被允许；但埋点照写不误。"""
        from app.models import User

        ok(admin_client.get('/api/audit/logs'))
        ok(admin_client.post('/api/users', json={'username': 'sales1', 'password': 'Passw0rd!'}), 201)
        with auth_app.app_context():
            assert User.query.filter_by(username='sales1', role='sales').count() == 1

        second = auth_app.test_client()
        # admin_client 与 second 共享 auth_app 的会话库，这里独立登录一个销售
        ok(second.post('/api/auth/login', json={'username': 'sales1', 'password': 'Passw0rd!'}))
        assert second.get('/api/audit/logs').status_code == 403
        assert second.get('/api/audit/summary').status_code == 403
        ok(second.post('/api/track', json={'page': '联系人管理'}))
        assert _rows_of(auth_app, action='点击', user='sales1')

    def test_m024_009_unauthenticated_cannot_read_logs(self, auth_client):
        assert auth_client.get('/api/audit/logs').status_code == 401


class TestAuditOnLegacyDatabase:
    """旧库升级：只建表，不需要 ALTER。"""

    def test_m025_001_tables_created_on_existing_db(self, tmp_path, monkeypatch):
        """老库（有业务表、没有日志表）启动后能直接用：新表由 create_all 补建。"""
        import sqlite3

        from app import create_app, db

        db_file = tmp_path / 'crm_legacy.db'
        con = sqlite3.connect(db_file)
        con.execute("CREATE TABLE system_config (id INTEGER PRIMARY KEY, key VARCHAR(100), "
                    "value TEXT, updated_at DATETIME)")
        con.execute("INSERT INTO system_config (key, value) VALUES ('app_version', '5.1')")
        con.commit()
        con.close()
        monkeypatch.setenv('CRM_SKIP_SEED', '1')
        app = create_app(config={
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(db_file),
            'TESTING': True, 'AUTH_DISABLED': True,
        })
        with app.app_context():
            assert OperationLog.query.count() == 0
            assert OperationSummary.query.count() == 0
            ok(app.test_client().get('/api/leads'))
            assert _rows(action='查询')
            db.session.remove()
            db.engine.dispose()
