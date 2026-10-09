"""测试公共工具：断言辅助与数据构造。"""
import csv
import io


def json_of(resp):
    """安全取 JSON；非 JSON 响应返回 None。"""
    try:
        return resp.get_json(silent=True)
    except Exception:
        return None


def ok(resp, expected=200):
    """断言状态码并返回 JSON body。"""
    raw = resp.get_data(as_text=True)
    assert resp.status_code == expected, \
        f"期望 HTTP {expected}，实际 {resp.status_code}：{raw[:300]}"
    return json_of(resp)


def err(resp, expected=400):
    """断言错误状态码与统一形状（{error, code[, detail]}），返回错误文案。

    code 是形状契约的一部分：文案可以改写，调用方分支只应依赖 code。
    这里统一断言，等于让全部错误用例顺手守住该契约。
    """
    body = ok(resp, expected)
    assert isinstance(body, dict) and 'error' in body, f"错误响应缺少 error 字段: {body}"
    assert isinstance(body.get('code'), str) and body['code'], f"错误响应缺少 code 字段: {body}"
    return body['error']


def created_id(resp):
    """从创建类接口的响应中取出 id。"""
    body = ok(resp)
    assert isinstance(body, dict) and 'id' in body, f"响应缺少 id: {body}"
    return body['id']


ADMIN_USER = 'admin'
ADMIN_PASS = 'hunter2'


def auth_setup(client, username=ADMIN_USER, password=ADMIN_PASS):
    """首次初始化管理员（未初始化时才允许）。"""
    return client.post('/api/auth/setup', json={'username': username, 'password': password})


def auth_login(client, username=ADMIN_USER, password=ADMIN_PASS):
    return client.post('/api/auth/login', json={'username': username, 'password': password})


def auth_logout(client):
    return client.post('/api/auth/logout', json={})


def make_customer(client, name='测试客户-构造', **kw):
    payload = {'name': name}
    payload.update(kw)
    return created_id(client.post('/api/customers', json=payload))


def make_contact(client, name='测试联系人-构造', customer_id=None, **kw):
    payload = {'name': name}
    if customer_id is not None:
        payload['customer_id'] = customer_id
    payload.update(kw)
    return created_id(client.post('/api/contacts', json=payload))


def make_lead(client, title='测试线索-构造', **kw):
    payload = {'title': title}
    payload.update(kw)
    return created_id(client.post('/api/leads', json=payload))


def make_opportunity(client, title='测试商机-构造', **kw):
    payload = {'title': title}
    payload.update(kw)
    return created_id(client.post('/api/opportunities', json=payload))


def make_activity(client, content='测试联络-构造', **kw):
    payload = {'content': content}
    payload.update(kw)
    return created_id(client.post('/api/activities', json=payload))


def make_followup(client, content='测试计划-构造', **kw):
    payload = {'content': content}
    payload.update(kw)
    return created_id(client.post('/api/followups', json=payload))


def make_card(client, column_id, title='测试卡片-构造', **kw):
    payload = {'column_id': column_id, 'title': title}
    payload.update(kw)
    return created_id(client.post('/api/kanban/cards', json=payload))


def set_config(app, **kwargs):
    """写入或覆盖系统配置（seed 里已有的键必须走 upsert，不能直接 insert）。"""
    from app import db
    from app.models import SystemConfig
    with app.app_context():
        for key, value in kwargs.items():
            cfg = SystemConfig.query.filter_by(key=key).first()
            if cfg is None:
                cfg = SystemConfig(key=key)
                db.session.add(cfg)
            cfg.value = str(value)
        db.session.commit()


def parse_csv(resp):
    """解析导出的 CSV，返回 (表头, 数据行列表)。"""
    text = resp.get_data().decode('utf-8-sig')
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:]


def fake_remote(monkeypatch, status=200, body='', headers=None, ip='93.184.216.34'):
    """不触网的远端响应：正文预先缓存，域名解析固定到给定 IP。

    走真实的 requests.Response，netutil 的流式读取、连接关闭、重定向判定
    才不会被测试替身绕过（用鸭子类型的手搓对象会让 bug 在测试里隐形）。
    """
    import socket

    from requests import Response
    import requests

    resp = Response()
    resp.status_code = status
    resp.headers.update(headers or {})
    resp._content = body.encode('utf-8') if isinstance(body, str) else bytes(body)
    resp._content_consumed = True
    resp.encoding = 'utf-8'
    monkeypatch.setattr(socket, 'getaddrinfo',
                        lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 0))])
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: resp)
    return resp


def fake_stream(status=200, chunks=(b'',), headers=None, url=''):
    """构造一个「仍在流式读取」的响应，用于验证字节上限真的生效。"""
    from requests import Response

    class _FakeRaw:
        def __init__(self, chunks):
            self._chunks = list(chunks)
            self.closed = 0

        def stream(self, chunk_size=None, decode_content=None):
            for chunk in self._chunks:
                yield chunk

        def close(self):
            self.closed += 1

        def release_conn(self):
            pass

    resp = Response()
    resp.status_code = status
    resp.headers.update(headers or {})
    resp.url = url
    resp.raw = _FakeRaw(chunks)
    resp._content_consumed = False
    return resp


def wipe_all(session):
    """按外键依赖顺序清空全部业务数据（用于构造空库场景）。

    SQLite 外键约束已启用，批量删除必须从子表删到父表，
    否则会触发 FOREIGN KEY constraint failed。
    """
    from app.models import (
        Activity, Contact, ContactNews, CrawlLog, Customer, CustomerNews,
        FollowUp, KanbanBoard, KanbanCard, KanbanColumn, Lead, Opportunity,
        StageRecord,
    )
    for model in (FollowUp, Activity, StageRecord, ContactNews, CustomerNews,
                  CrawlLog, KanbanCard, KanbanColumn, KanbanBoard,
                  Opportunity, Lead, Contact, Customer):
        model.query.delete()
    session.commit()
