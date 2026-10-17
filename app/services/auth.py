"""账号鉴权支撑：多用户口令校验、角色判定、登录限速。

- 口令只存散列（werkzeug scrypt），散列与原文都不经任何接口回传；
- 限速键取「用户名 + 来源 IP」的交集：只按 IP 会让同网段多人互相拖死，
  只按用户名则任何人拿管理员账号名连错几次就能把真管理员锁在门外；
- 角色只用来划分「谁能改系统设置和账号」，业务数据全员共享，不做 per-owner 隔离。
"""
import time
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

MAX_FAILURES = 5
LOCK_SECONDS = 3600

ADMIN = 'admin'
SALES = 'sales'
ROLES = (ADMIN, SALES)

_attempts = {}


def has_accounts():
    """库里是否已有账号：决定首次进入走「初始化管理员」还是「登录」。"""
    from app.models import User
    return User.query.first() is not None


def active_admin_count():
    from app.models import User
    return User.query.filter_by(role=ADMIN, is_active=True).count()


def create_user(username, password, role=SALES, display_name=''):
    from app import db
    from app.models import User
    username = (username or '').strip()
    if User.find(username) is not None:
        raise ValueError('该账号名已存在')
    user = User(
        username=username,
        display_name=(display_name or '').strip(),
        role=role if role in ROLES else SALES,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()
    return user


def verify(username, password):
    """校验通过返回 User，否则返回 None。

    账号不存在、口令错误、已停用一律同一个结果：不给探测者区分「账号名是否存在」
    的机会，限速才有意义。
    """
    from app.models import User
    user = User.find(username)
    if user is None or not user.is_active or not user.password_hash:
        return None
    if not password or not check_password_hash(user.password_hash, password):
        return None
    return user


def is_admin(user):
    return bool(user) and user.role == ADMIN


def touch_login(user):
    from app import db
    user.last_login_at = datetime.now()
    db.session.commit()


def set_password(user, plain):
    from app import db
    user.password_hash = generate_password_hash(plain)
    db.session.commit()


def attempt_key(username, source):
    return f'{(username or "").strip().lower()}|{source}'


def lock_remaining(key):
    """该键还需等待多少秒（0 表示可以尝试）。"""
    fails = _attempts.get(key)
    if not fails:
        return 0.0
    until = fails.get('locked_until', 0.0)
    now = time.monotonic()
    if until > now:
        return until - now
    if until:
        # 锁定期已过：重新计数
        _attempts.pop(key, None)
    return 0.0


def note_failure(key):
    entry = _attempts.setdefault(key, {'count': 0, 'locked_until': 0.0})
    entry['count'] += 1
    if entry['count'] >= MAX_FAILURES:
        entry['locked_until'] = time.monotonic() + LOCK_SECONDS
    return lock_remaining(key)


def reset_attempts(key):
    _attempts.pop(key, None)


def current_user():
    """本次请求的登录账号；不存在 / 已停用 / 已删除都按未登录处理。

    每次都回库确认（主键查询，1ms 级），账号被管理员停用或删除后，
    对方手里那张 30 天有效的 cookie 立刻失效。
    结果缓存在 g 上，同一个请求里多次取用不会重复查库。
    """
    from flask import g, session
    if hasattr(g, 'crm_user'):
        return g.crm_user
    from app.models import User
    user = None
    uid = session.get('uid')
    if uid:
        user = User.query.filter_by(id=uid).first()
        if user is not None and not user.is_active:
            user = None
    g.crm_user = user
    return user


# 业务表里的「操作人」列在没有登录身份时的取值：定时采集、脚本导入、
# 以及改造上线前的历史行，都归到这个名字，列表永远不会出现空操作人。
SYSTEM_ACTOR = '系统'

