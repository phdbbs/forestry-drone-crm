"""多用户鉴权行为：登录闸门、初始化管理员、账号口令、暴力尝试限速、凭据不外泄。

鉴权用例走 conftest 的 auth_app / auth_client（AUTH_DISABLED=False），
业务用例仍走默认关鉴权的夹具。
"""
from crm_test_utils import auth_login, auth_setup

ADMIN = {'username': 'admin', 'password': 'hunter2'}


class TestGate:
    def test_api_requires_login(self, auth_client):
        r = auth_client.get('/api/leads')
        assert r.status_code == 401
        assert r.get_json()['code'] == 'unauthorized'

    def test_write_endpoints_also_blocked(self, auth_client):
        assert auth_client.delete('/api/customers/1').status_code == 401
        assert auth_client.put('/api/config', json={'keywords': 'x'}).status_code == 401

    def test_account_api_requires_login(self, auth_client):
        assert auth_client.get('/api/users').status_code == 401

    def test_auth_status_is_open(self, auth_client):
        r = auth_client.get('/api/auth/status')
        assert r.status_code == 200
        assert r.get_json() == {
            'auth_enabled': True, 'configured': False, 'authenticated': False, 'user': None,
        }

    def test_spa_shell_still_served(self, auth_client):
        """登录页本身是 SPA 的一部分，不能被闸拦成 401，否则永远进不去。"""
        assert auth_client.get('/').status_code != 401

    def test_logout_is_idempotent_without_login(self, auth_client):
        assert auth_client.post('/api/auth/logout', json={}).status_code == 200


class TestFirstRunSetup:
    def test_requires_username(self, auth_client):
        r = auth_client.post('/api/auth/setup', json={'password': 'hunter2'})
        assert '账号名' in r.get_json()['error']
        assert r.status_code == 400

    def test_rejects_short_password(self, auth_client):
        assert auth_setup(auth_client, password='123').status_code == 400

    def test_creates_admin_and_logs_in(self, auth_client):
        r = auth_setup(auth_client)
        assert r.status_code == 200
        assert r.get_json()['user']['role'] == 'admin'
        assert auth_client.get('/api/leads').status_code == 200
        assert auth_client.get('/api/auth/status').get_json()['user']['username'] == 'admin'

    def test_created_row_stores_hash_not_plaintext(self, auth_app, auth_client):
        from app.models import User
        auth_setup(auth_client)
        with auth_app.app_context():
            user = User.query.filter_by(username='admin').first()
            assert user.password_hash != ADMIN['password']
            assert user.password_hash.startswith(('scrypt:', 'pbkdf2:'))

    def test_can_only_run_once(self, auth_client):
        """初始化窗口只在零账号时打开，否则任何人都能建一个管理员把自己抬进去。"""
        auth_setup(auth_client)
        r = auth_setup(auth_client, username='hacker')
        assert r.status_code == 409
        assert '管理员' in r.get_json()['error']

    def test_login_before_setup_is_rejected(self, auth_client):
        r = auth_login(auth_client)
        assert r.status_code == 400
        assert '初始化' in r.get_json()['error']


class TestLogin:
    def test_wrong_password(self, auth_client):
        auth_setup(auth_client)
        auth_client.post('/api/auth/logout', json={})
        r = auth_login(auth_client, password='wrong-one')
        assert r.status_code == 401
        assert r.get_json()['error'] == '账号或口令不正确'

    def test_unknown_username_gives_same_error(self, auth_app, auth_client):
        """不区分「账号不存在」与「口令错误」，否则接口可用于枚举账号名。"""
        from app.services import auth as auth_svc
        auth_setup(auth_client)
        auth_client.post('/api/auth/logout', json={})
        auth_svc._attempts.clear()
        assert auth_login(auth_client, username='nosuch').get_json()['error'] == '账号或口令不正确'

    def test_username_is_case_insensitive(self, auth_app, auth_client):
        from app.services import auth as auth_svc
        auth_setup(auth_client, username='WangLin')
        auth_client.post('/api/auth/logout', json={})
        auth_svc._attempts.clear()
        assert auth_login(auth_client, username='wanglin').status_code == 200

    def test_empty_password_rejected(self, auth_client):
        auth_setup(auth_client)
        auth_client.post('/api/auth/logout', json={})
        assert auth_login(auth_client, password='').status_code == 401

    def test_logout_then_api_401(self, auth_client):
        auth_setup(auth_client)
        auth_client.post('/api/auth/logout', json={})
        assert auth_client.get('/api/leads').status_code == 401

    def test_me_requires_session(self, auth_client):
        assert auth_client.get('/api/auth/me').status_code == 401
        auth_setup(auth_client)
        assert auth_client.get('/api/auth/me').get_json()['username'] == 'admin'

    def test_last_login_is_recorded(self, auth_app, auth_client):
        from app.models import User
        auth_setup(auth_client)
        with auth_app.app_context():
            assert User.query.filter_by(username='admin').first().last_login_at is not None


class TestChangeOwnPassword:
    def test_requires_old_password(self, auth_client):
        auth_setup(auth_client)
        r = auth_client.post('/api/auth/change', json={'password': 'nope', 'new_password': 'newpass1'})
        assert r.status_code == 401
        assert auth_login(auth_client, password='newpass1').status_code == 401

    def test_rejects_short_new_password(self, auth_client):
        auth_setup(auth_client)
        r = auth_client.post('/api/auth/change', json={'password': 'hunter2', 'new_password': '123'})
        assert r.status_code == 400

    def test_changes_only_own_password(self, auth_app, auth_client):
        from app.services import auth as auth_svc
        auth_setup(auth_client)
        with auth_app.app_context():
            auth_svc.create_user('sales1', 'Sales123')
        auth_client.post('/api/auth/logout', json={})
        auth_svc._attempts.clear()
        assert auth_login(auth_client, username='sales1', password='Sales123').status_code == 200
        assert auth_client.post('/api/auth/change', json={
            'password': 'Sales123', 'new_password': 'Sales456'}).status_code == 200
        auth_svc._attempts.clear()
        other = auth_app.test_client()
        assert auth_login(other, password='hunter2').status_code == 200
        assert auth_login(other, username='sales1', password='Sales456').status_code == 200


class TestBruteForceGuard:
    def test_five_failures_lock_the_account(self, auth_client):
        auth_setup(auth_client)
        auth_client.post('/api/auth/logout', json={})
        for _ in range(5):
            assert auth_login(auth_client, password='bad-pass').status_code == 401
        # 锁定期内连正确口令也进不来
        assert auth_login(auth_client).status_code == 429

    def test_lock_is_per_username_not_per_ip(self, auth_client):
        """同一来源锁定 A 账号不能把 B 账号一起锁死，否则多人共用网络会互相误伤。"""
        auth_setup(auth_client)
        auth_client.post('/api/auth/logout', json={})
        for _ in range(5):
            auth_login(auth_client, username='other', password='bad-pass')
        assert auth_login(auth_client).status_code == 200

    def test_successful_login_clears_counter(self, auth_client):
        auth_setup(auth_client)
        auth_client.post('/api/auth/logout', json={})
        for _ in range(4):
            auth_login(auth_client, password='bad-pass')
        assert auth_login(auth_client).status_code == 200
        auth_client.post('/api/auth/logout', json={})
        for _ in range(4):
            auth_login(auth_client, password='bad-pass')
        assert auth_login(auth_client, password='bad-pass').status_code == 401


class TestCredentialsNotExposed:
    def test_no_response_carries_the_hash(self, admin_client):
        for path in ('/api/auth/status', '/api/auth/me', '/api/users'):
            body = str(admin_client.get(path).get_json())
            assert 'hunter2' not in body
            assert 'scrypt:' not in body and 'pbkdf2:' not in body

    def test_config_get_masks_secrets(self, client, dbsession):
        """/api/config 是老配置读取口，敏感键必须打码。"""
        from app import db
        from app.models import SystemConfig
        for key, value in (('ai_api_key', 'sk-secret'), ('auth_password_hash', 'legacy-hash')):
            rec = SystemConfig.query.filter_by(key=key).first()
            if rec is None:
                db.session.add(SystemConfig(key=key, value=value))
            else:
                rec.value = value
            db.session.commit()
        body = client.get('/api/config').get_json()
        assert body['ai_api_key']['value'] == '[已隐藏]'
        assert 'sk-secret' not in str(body)

    def test_config_put_cannot_write_secrets(self, client):
        r = client.put('/api/config', json={'auth_password_hash': 'x', 'ai_api_key': 'y'})
        assert r.status_code == 400
        assert 'auth_password_hash' in r.get_json()['error']


class TestAuthDisabled:
    def test_default_fixture_skips_gate(self, client):
        """conftest 的公共夹具关掉鉴权，业务用例不必关心登录。"""
        assert client.get('/api/leads').status_code == 200
        assert client.get('/api/auth/status').get_json()['auth_enabled'] is False
