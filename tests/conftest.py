"""pytest 公共夹具。

每个用例使用独立的临时 SQLite 库（自动建表 + 演示数据），
因此用例之间互不干扰，也不会碰到真实库 instance/crm.db。
"""
import os
import pathlib
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('CRM_SECRET_KEY', 'crm-test-secret')
os.environ.setdefault('CRM_DISABLE_SCHEDULER', '1')  # 测试不起定时任务线程
# 测试必须走 seed 分支，保证基线数据可预期
os.environ.pop('CRM_SKIP_SEED', None)


@pytest.fixture()
def tmp_path():
    """覆盖 pytest 默认实现。

    默认实现在会话开始时要清理历史目录、并以用户名拼装基础路径，
    在受限文件系统（网络卷 / 沙箱）上可能被拒绝，导致全部用例 setup 失败。
    这里直接使用系统临时目录，并忽略清理异常。
    """
    path = pathlib.Path(tempfile.mkdtemp(prefix='crm-test-'))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def app(tmp_path):
    """全新应用实例：临时库 + 演示数据。"""
    from app import create_app, db

    application = create_app(config={
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path / 'crm_test.db'),
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        # 绝大多数用例测的是业务接口本身；鉴权单独用 auth_client 覆盖
        'AUTH_DISABLED': True,
    })
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def dbsession(app):
    """在应用上下文中直接读写 ORM 的会话。"""
    from app import db
    with app.app_context():
        yield db.session
        db.session.remove()


@pytest.fixture()
def fresh_session(dbsession):
    """清掉身份映射，让下一次请求重新发 SQL。

    生产环境每个请求一个 session，逻辑删除的行在下一个请求里必然查不到。
    测试里 dbsession 与应用上下文是常驻的，同一会话已经持有该对象时
    get_or_404 不发 SQL、会直接把墓碑行交出去。断言「删后不可见」前调一次。
    """
    def _clear():
        dbsession.expunge_all()
        return dbsession
    return _clear


@pytest.fixture()
def auth_app(tmp_path):
    """开启鉴权的独立应用实例。

    conftest 的公共夹具为了「绝大多数用例只测业务接口」而关掉了鉴权，
    覆盖不到闸门本身，所以鉴权用例用它自己的库和会话计数。
    """
    from app import create_app, db
    from app.services import auth as auth_svc

    auth_svc._attempts.clear()
    application = create_app(config={
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path / 'crm_auth.db'),
        'TESTING': True,
        'AUTH_DISABLED': False,
    })
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()
    auth_svc._attempts.clear()


@pytest.fixture()
def auth_client(auth_app):
    return auth_app.test_client()


@pytest.fixture()
def admin_client(auth_client):
    """已完成首次初始化、并以管理员身份登录的客户端。"""
    from crm_test_utils import auth_setup
    assert auth_setup(auth_client).status_code == 200
    yield auth_client


@pytest.fixture()
def seed(app):
    """演示数据的关键主键，避免用例硬编码 ID。"""
    from app.models import (
        Contact, Customer, KanbanBoard, KanbanColumn, Lead, Opportunity,
    )
    with app.app_context():
        lead = Lead.query.filter_by(status='active').order_by(Lead.id).first()
        return {
            'customer': Customer.query.order_by(Customer.id).first().id,
            'customer2': Customer.query.order_by(Customer.id).offset(1).first().id,
            'contact': Contact.query.order_by(Contact.id).first().id,
            'lead_active': lead.id if lead else None,
            'opportunity': Opportunity.query.order_by(Opportunity.id).first().id,
            'board': KanbanBoard.query.order_by(KanbanBoard.id).first().id,
            'column': KanbanColumn.query.order_by(KanbanColumn.id).first().id,
        }
