"""登录鉴权端点：状态 / 登录 / 初始化管理员 / 我的信息 / 改密 / 登出。

口令散列只存 users 表，任何接口都不回传散列或原文；
未登录时 /api/* 一律 401，前端据此跳登录页（见 app/__init__ 的闸门）。
"""
from flask import Blueprint, jsonify, request, session

from app.services import auth as auth_svc

auth_bp = Blueprint('auth', __name__)

MIN_LENGTH = 6


def _source():
    return request.remote_addr or 'unknown'


def _body():
    return request.get_json(silent=True) or {}


def _username_from(body):
    return str(body.get('username') or '').strip()


def _begin_session(user):
    """会话只放标识，角色每次请求回库取，改角色/停用即时生效。"""
    session.clear()
    session.permanent = True
    session['uid'] = user.id
    auth_svc.reset_attempts(auth_svc.attempt_key(user.username, _source()))


@auth_bp.route('/status', methods=['GET'])
def status():
    """前端启动时调用：决定展示登录页还是应用，以及登录页要不要走「初始化」。"""
    from flask import current_app
    user = auth_svc.current_user()
    return jsonify({
        "auth_enabled": not current_app.config.get('AUTH_DISABLED', False),
        "configured": auth_svc.has_accounts(),
        "authenticated": bool(user),
        "user": user.to_dict() if user else None,
    })


@auth_bp.route('/login', methods=['POST'])
def login():
    body = _body()
    username = _username_from(body)
    key = auth_svc.attempt_key(username, _source())
    remaining = auth_svc.lock_remaining(key)
    if remaining:
        return jsonify({"error": "失败次数过多，请稍后再试"}), 429
    if not auth_svc.has_accounts():
        return jsonify({"error": "尚未创建账号，请先初始化管理员"}), 400
    user = auth_svc.verify(username, str(body.get('password') or ''))
    if user is None:
        auth_svc.note_failure(key)
        # 不区分「账号不存在」与「口令错误」，避免被用来枚举账号名
        return jsonify({"error": "账号或口令不正确"}), 401
    auth_svc.touch_login(user)
    _begin_session(user)
    return jsonify({"ok": True, "user": user.to_dict()})


@auth_bp.route('/setup', methods=['POST'])
def setup():
    """首次使用：创建第一个管理员账号并直接登录。已有账号则拒绝，避免越权建号。"""
    if auth_svc.has_accounts():
        return jsonify({"error": "系统已初始化，请让管理员在账号管理中添加账号"}), 409
    body = _body()
    username = _username_from(body)
    password = str(body.get('password') or '')
    if not username:
        return jsonify({"error": "请填写账号名"}), 400
    if len(password) < MIN_LENGTH:
        return jsonify({"error": f"口令至少 {MIN_LENGTH} 位"}), 400
    user = auth_svc.create_user(username, password, role=auth_svc.ADMIN,
                                display_name=str(body.get('display_name') or username))
    auth_svc.touch_login(user)
    _begin_session(user)
    return jsonify({"ok": True, "user": user.to_dict()})


@auth_bp.route('/me', methods=['GET'])
def me():
    user = auth_svc.current_user()
    if user is None:
        return jsonify({"error": "请先登录", "code": "unauthorized"}), 401
    return jsonify(user.to_dict())


@auth_bp.route('/change', methods=['POST'])
def change():
    """修改自己的口令，必须验证原口令。"""
    from app.services.auth import current_user
    user = current_user()
    if user is None:
        return jsonify({"error": "请先登录", "code": "unauthorized"}), 401
    body = _body()
    if auth_svc.verify(user.username, str(body.get('password') or '')) is None:
        return jsonify({"error": "原口令不正确"}), 401
    new_password = str(body.get('new_password') or '')
    if len(new_password) < MIN_LENGTH:
        return jsonify({"error": f"新口令至少 {MIN_LENGTH} 位"}), 400
    auth_svc.set_password(user, new_password)
    return jsonify({"ok": True})


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"ok": True})
