#!/usr/bin/env python3
"""SHAPE — 错误响应形状契约：任何失败都同时给出 error（给用户）和 code（给程序）。

统一出口在 app/errors.py（fail / http_error），全局 errorhandler 兜住 abort()、
ORM 异常与未捕获异常。这里覆盖每条入口路径，防止「只有 message、没有 code」
的旧写法回潮；code 是调用方唯一可以依赖的稳定标识，文案随时可以改写。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crm_test_utils import auth_login, auth_setup, err, ok  # noqa: E402


def shape(resp, expected):
    """断言状态码 + {error, code[, detail]} 形状，返回 body 便于再断言 code。"""
    body = ok(resp, expected)
    assert isinstance(body, dict), f'错误响应应为对象: {body}'
    assert isinstance(body.get('error'), str) and body['error'], f'error 缺失或为空: {body}'
    assert isinstance(body.get('code'), str) and body['code'], f'code 缺失或为空: {body}'
    assert 'detail' not in body or isinstance(body['detail'], str), f'detail 类型不对: {body}'
    return body


class TestHttpErrorPaths:
    """由全局 errorhandler 生成的错误：code 取状态码默认映射。"""

    def test_shape_001_not_found(self, client):
        body = shape(client.get('/api/leads/999999'), 404)
        assert body['code'] == 'not_found'

    def test_shape_002_method_not_allowed(self, client, seed):
        # convert 只接受 POST
        body = shape(client.delete(f"/api/leads/{seed['lead_active']}/convert"), 405)
        assert body['code'] == 'method_not_allowed'

    def test_shape_003_abort_keeps_business_message(self, client):
        # _require_fields 走 abort(400, description=...)：业务提示必须原样透出
        body = shape(client.post('/api/customers', json={}), 400)
        assert '缺少必填字段' in body['error'], body['error']
        assert body['code'] == 'bad_request'

    def test_shape_004_unknown_api_path_is_json_404(self, client):
        shape(client.get('/api/no-such-endpoint'), 404)


class TestServiceExceptions:
    """服务层异常经 errorhandler 归一，不外泄堆栈与 SQL。"""

    def test_shape_010_value_error_becomes_bad_param(self, app, client):
        @app.route('/api/_shape/value')
        def _raise_value():
            raise ValueError('口令至少 6 位')

        body = shape(client.get('/api/_shape/value'), 400)
        assert body['error'] == '口令至少 6 位'
        assert body['code'] == 'bad_param'

    def test_shape_011_key_error_becomes_missing_param(self, app, client):
        @app.route('/api/_shape/key')
        def _raise_key():
            raise KeyError('title')

        body = shape(client.get('/api/_shape/key'), 400)
        assert 'title' in body['error']
        assert body['code'] == 'missing_param'

    def test_shape_012_unhandled_exception_is_generic_500(self, app, client):
        @app.route('/api/_shape/boom')
        def _boom():
            raise RuntimeError('内部实现细节，不能透出')

        # TESTING=True 时 Flask 会把异常抛给调用方；这里要的是生产语义
        app.testing = False
        body = shape(client.get('/api/_shape/boom'), 500)
        assert body['error'] == '服务器内部错误'
        assert body['code'] == 'server_error'
        app.testing = True

    def test_shape_013_foreign_key_becomes_bad_reference(self, client):
        body = shape(client.post('/api/opportunities',
                                 json={'title': '形状用例', 'customer_id': 999999}), 400)
        assert body['code'] == 'bad_reference', body
        assert 'SELECT' not in body['error'] and 'sql' not in body['error'].lower()


class TestRouteLevelFail:
    """路由里显式 fail() 的站点：既有中文文案，也有稳定 code。"""

    def test_shape_020_skill_not_found(self, client):
        body = shape(client.post('/api/skills/no_such_skill/execute', json={}), 404)
        assert body['code'] == 'skill_not_found'

    def test_shape_021_skill_param_name_rejected(self, client):
        body = shape(client.post('/api/skills/read_database/execute', json={'a b': 1}), 400)
        assert '参数名不合法' in body['error']
        assert body['code'] == 'bad_request'

    def test_shape_022_fulltext_without_source_url(self, client, seed):
        lead = seed['lead_active']
        with client.application.app_context():
            from app import db
            from app.models import Lead
            db.session.get(Lead, lead).source_url = ''
            db.session.commit()
        body = shape(client.post(f'/api/leads/{lead}/fulltext/fetch'), 400)
        assert body['code'] == 'no_source_url'

    def test_shape_023_secret_config_write_blocked(self, client):
        body = shape(client.put('/api/config', json={'ai_api_key': 'sk-abc'}), 400)
        assert '不能通过通用接口修改' in body['error']
        assert body['code'] == 'bad_request'

    def test_shape_024_export_unknown_type(self, client):
        body = shape(client.post('/api/export/not_a_type', json={'ids': [1]}), 400)
        assert body['code'] == 'bad_request'

    def test_shape_025_batch_action_unsupported(self, client):
        body = shape(client.post('/api/leads/batch', json={'action': 'nope', 'ids': [1]}), 400)
        assert body['code'] == 'bad_request'


class TestInBandFailureKeepsCode:
    """HTTP 200 + ok:false 的带内结果不算错误响应，但带 error 就必须带 code。"""

    def test_shape_030_collect_news_failure(self, client):
        body = ok(client.post('/api/customers/999999/collect-news'), 200)
        assert body['ok'] is False
        assert body['code'] == 'collect_failed', body

    def test_shape_031_crawl_already_running(self, client):
        from app.services import crawler
        crawler._crawl_status['running'] = True
        try:
            body = ok(client.post('/api/crawl'), 200)
            assert body['ok'] is False and body['running'] is True
            assert body['code'] == 'crawl_running', body
        finally:
            crawler._crawl_status['running'] = False

    def test_shape_032_ai_analysis_failure(self, client):
        body = ok(client.get('/api/ai/urgent-tasks'), 200)
        assert body['ok'] is False
        assert body['code'] == 'ai_failed', body


class TestAuthGateShape:
    """鉴权闸门走同一形状（独立于关闭鉴权的业务 client）。"""

    def test_shape_040_unauthorized(self, auth_client):
        body = shape(auth_client.get('/api/leads'), 401)
        assert body['error'] == '请先登录'
        assert body['code'] == 'unauthorized'

    def test_shape_041_forbidden_for_sales(self, auth_app, admin_client):
        ok(admin_client.post('/api/users', json={
            'username': 'seller', 'password': 'pw123456', 'role': 'sales'}), 201)
        seller = auth_app.test_client()
        auth_login(seller, 'seller', 'pw123456')
        body = shape(seller.get('/api/users'), 403)
        assert body['code'] == 'forbidden'

    def test_shape_042_login_bad_credentials(self, auth_client):
        assert auth_setup(auth_client).status_code == 200
        body = shape(auth_client.post('/api/auth/login',
                                      json={'username': 'admin', 'password': 'wrong'}), 401)
        assert body['code'] == 'bad_credentials'

    def test_shape_043_last_admin_guard(self, admin_client):
        with admin_client.application.app_context():
            from app.models import User
            admin_id = User.query.filter_by(username='admin').first().id
        body = shape(admin_client.put(f'/api/users/{admin_id}', json={'role': 'sales'}), 400)
        assert body['code'] == 'last_admin', body

    def test_shape_044_not_initialized(self, auth_client):
        body = shape(auth_client.post('/api/auth/login',
                                      json={'username': 'admin', 'password': 'whatever'}), 400)
        assert body['code'] == 'not_initialized'


class _ErrorOnlyBody:
    """伪造一个「只有文案、没有 code」的旧式错误响应，用来验证 err() 会拦住它。"""

    status_code = 400

    def get_data(self, as_text=False):
        raw = '{"error": "只有文案"}'
        return raw if as_text else raw.encode()

    def get_json(self, silent=False):
        return {'error': '只有文案'}


def test_shape_050_err_helper_enforces_code(client, seed):
    """crm_test_utils.err() 已内置 code 断言：这里验证它确实会拦住缺 code 的响应。"""
    assert '状态无效' in err(
        client.put(f"/api/leads/{seed['lead_active']}", json={'status': 'bogus'}))

    try:
        err(_ErrorOnlyBody())
    except AssertionError as e:
        assert 'code' in str(e), e
    else:
        raise AssertionError('err() 应当拒绝缺少 code 的错误响应')


def test_shape_060_error_sites_go_through_fail():
    """守卫：app/ 下不得再手写 jsonify({"error": ...}) 的错误响应。

    统一走 fail() 才保证 code 不会漏；唯一的例外是 HTTP 200 的带内结果
    （ok:false），它不是错误响应，但同一行也必须带 code。
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / 'app'
    bad = []
    for file in sorted(root.rglob('*.py')):
        for lineno, line in enumerate(file.read_text(encoding='utf-8').split('\n'), 1):
            if 'jsonify' in line and '"error"' in line and 'code' not in line:
                bad.append(f'{file.name}:{lineno}: {line.strip()[:90]}')
    assert not bad, '错误响应未走 app/errors.fail()：\n' + '\n'.join(bad)

    from app.errors import STATUS_CODE, fail
    assert callable(fail) and STATUS_CODE[404] == 'not_found'
