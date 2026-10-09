"""账号管理与权限边界：管理员建号/改角色/重置口令/逻辑删除，销售只用业务接口。

数据全员共享，权限只区分「谁能改系统设置和账号」。
"""
import pytest
from crm_test_utils import auth_login, ok

SALES_PASS = 'Sales123'


@pytest.fixture()
def sales_client(auth_app, admin_client):
    """由管理员创建并登录的销售账号。"""
    ok(admin_client.post('/api/users', json={
        'username': 'sales1', 'password': SALES_PASS, 'role': 'sales', 'display_name': '小张'}), 201)
    client = auth_app.test_client()
    assert auth_login(client, username='sales1', password=SALES_PASS).status_code == 200
    return client


class TestAdminCreatesAccounts:
    def test_list_shows_admin_self(self, admin_client):
        rows = ok(admin_client.get('/api/users'))
        assert [r['username'] for r in rows] == ['admin']
        assert rows[0]['role'] == 'admin'
        assert 'password_hash' not in rows[0]

    def test_create_sales_account(self, admin_client):
        body = ok(admin_client.post('/api/users', json={
            'username': 'wanglin', 'password': SALES_PASS, 'role': 'sales', 'display_name': '王林'}), 201)
        assert body['role'] == 'sales' and body['display_name'] == '王林'
        assert 'password' not in body and 'password_hash' not in body

    def test_new_account_can_log_in(self, auth_app, admin_client, auth_client):
        ok(admin_client.post('/api/users', json={
            'username': 'wanglin', 'password': SALES_PASS, 'role': 'sales'}), 201)
        fresh = auth_app.test_client()
        assert auth_login(fresh, username='wanglin', password=SALES_PASS).status_code == 200
        assert fresh.get('/api/auth/me').get_json()['role'] == 'sales'

    def test_rejects_duplicate_username(self, admin_client):
        ok(admin_client.post('/api/users', json={'username': 'wanglin', 'password': SALES_PASS}), 201)
        r = admin_client.post('/api/users', json={'username': 'wanglin', 'password': SALES_PASS})
        assert r.status_code == 400
        assert '已存在' in r.get_json()['error']

    def test_rejects_short_password_and_bad_role(self, admin_client):
        assert admin_client.post('/api/users', json={'username': 'a', 'password': '123'}).status_code == 400
        r = admin_client.post('/api/users', json={'username': 'b', 'password': SALES_PASS, 'role': 'root'})
        assert r.status_code == 400


class TestSalesPermissions:
    def test_business_api_is_open(self, sales_client):
        for path in ('/api/leads', '/api/customers', '/api/contacts', '/api/opportunities',
                     '/api/activities', '/api/followups', '/api/kanban/boards', '/api/dashboard',
                     '/api/stages', '/api/options', '/api/search?q=林'):
            assert sales_client.get(path).status_code == 200, path

    def test_can_write_business_data(self, sales_client):
        ok(sales_client.post('/api/customers', json={'name': '销售新建客户'}))

    def test_admin_only_endpoints_are_blocked(self, sales_client):
        blocked = [
            sales_client.get('/api/users'),
            sales_client.get('/api/config'),
            sales_client.put('/api/config', json={'keywords': 'x'}),
            sales_client.get('/api/skills'),
            sales_client.get('/api/crawl/logs'),
            sales_client.delete('/api/crawl/logs?task_type=lead&days=1'),
            sales_client.post('/api/config/backup-now'),
            sales_client.post('/api/stages', json={'name': '新阶段'}),
        ]
        for r in blocked:
            assert r.status_code == 403, r.request.path
            assert r.get_json()['code'] == 'forbidden'

    def test_stage_list_still_readable(self, sales_client):
        """阶段配置的销售可读不可改：商机页要用它渲染阶段下拉。"""
        assert sales_client.get('/api/stages').status_code == 200

    def test_crawl_trigger_stays_open(self, sales_client):
        """采集是线索的日常来源，不属于系统设置。"""
        assert sales_client.get('/api/crawl/status').status_code == 200


class TestAdminEditsAccounts:
    def _create_sales(self, admin_client, username='wanglin'):
        return ok(admin_client.post('/api/users', json={
            'username': username, 'password': SALES_PASS, 'role': 'sales'}), 201)['id']

    def test_update_display_name_and_role(self, admin_client, auth_app):
        uid = self._create_sales(admin_client)
        body = ok(admin_client.put(f'/api/users/{uid}', json={'display_name': '王林', 'role': 'admin'}))
        assert body['display_name'] == '王林' and body['role'] == 'admin'

    def test_admin_can_reset_password(self, admin_client, auth_app):
        uid = self._create_sales(admin_client)
        ok(admin_client.post(f'/api/users/{uid}/password', json={'password': 'NewPass123'}))
        fresh = auth_app.test_client()
        assert auth_login(fresh, username='wanglin', password='NewPass123').status_code == 200

    def test_disabled_account_cannot_log_in(self, admin_client, auth_app):
        from app.services import auth as auth_svc
        uid = self._create_sales(admin_client)
        ok(admin_client.put(f'/api/users/{uid}', json={'is_active': False}))
        auth_svc._attempts.clear()
        fresh = auth_app.test_client()
        assert auth_login(fresh, username='wanglin', password=SALES_PASS).status_code == 401

    def test_disabling_kicks_the_live_session(self, auth_app, admin_client, sales_client):
        """会话 cookie 有效期 30 天，停用必须立刻生效，所以闸门每请求回库确认。"""
        with auth_app.app_context():
            from app.models import User
            target = User.find('sales1').id
        ok(admin_client.put(f'/api/users/{target}', json={'is_active': False}))
        assert sales_client.get('/api/leads').status_code == 401

    def test_cannot_disable_self(self, admin_client, auth_app):
        with auth_app.app_context():
            from app.models import User
            admin_id = User.query.filter_by(username='admin').first().id
        r = admin_client.put(f'/api/users/{admin_id}', json={'is_active': False})
        assert r.status_code == 400
        assert '自己' in r.get_json()['error']

    def test_last_admin_cannot_be_demoted_or_disabled(self, admin_client, auth_app):
        with auth_app.app_context():
            from app.models import User
            admin_id = User.query.filter_by(username='admin').first().id
        assert admin_client.put(f'/api/users/{admin_id}', json={'role': 'sales'}).status_code == 400
        assert admin_client.delete(f'/api/users/{admin_id}').status_code == 400


class TestLogicalAccountDelete:
    def test_row_stays_in_db_and_username_is_free(self, auth_app, admin_client):
        from app.models import User
        uid = ok(admin_client.post('/api/users', json={
            'username': 'wanglin', 'password': SALES_PASS, 'role': 'sales'}), 201)['id']
        ok(admin_client.delete(f'/api/users/{uid}'))
        with auth_app.app_context():
            kept = User.query.filter_by(username='wanglin').execution_options(
                include_deleted=True).first()
            assert kept is not None and kept.is_deleted and not kept.is_active
        # 用户名不再占用，可以重新建号（部分唯一索引只约束未删除账号）
        ok(admin_client.post('/api/users', json={
            'username': 'wanglin', 'password': 'Other123', 'role': 'sales'}), 201)

    def test_deleted_account_is_hidden_and_cannot_log_in(self, auth_app, admin_client):
        from app.services import auth as auth_svc
        uid = ok(admin_client.post('/api/users', json={
            'username': 'wanglin', 'password': SALES_PASS, 'role': 'sales'}), 201)['id']
        ok(admin_client.delete(f'/api/users/{uid}'))
        assert all(u['username'] != 'wanglin' for u in ok(admin_client.get('/api/users')))
        auth_svc._attempts.clear()
        fresh = auth_app.test_client()
        assert auth_login(fresh, username='wanglin', password=SALES_PASS).status_code == 401

    def test_deleted_account_session_is_revoked(self, auth_app, admin_client, sales_client):
        with auth_app.app_context():
            from app.models import User
            target = User.find('sales1').id
        ok(admin_client.delete(f'/api/users/{target}'))
        assert sales_client.get('/api/leads').status_code == 401

    def test_cannot_delete_self(self, admin_client, auth_app):
        with auth_app.app_context():
            from app.models import User
            admin_id = User.query.filter_by(username='admin').first().id
        assert admin_client.delete(f'/api/users/{admin_id}').status_code == 400
