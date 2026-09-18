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
    """断言错误状态码，并返回错误文案。"""
    body = ok(resp, expected)
    assert isinstance(body, dict) and 'error' in body, f"错误响应缺少 error 字段: {body}"
    return body['error']


def created_id(resp):
    """从创建类接口的响应中取出 id。"""
    body = ok(resp)
    assert isinstance(body, dict) and 'id' in body, f"响应缺少 id: {body}"
    return body['id']


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


def parse_csv(resp):
    """解析导出的 CSV，返回 (表头, 数据行列表)。"""
    text = resp.get_data().decode('utf-8-sig')
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:]


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
