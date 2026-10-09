"""账号管理（仅管理员）：列表 / 新增 / 改名改角色 / 重置口令 / 逻辑删除。

这里的删除同样只置 is_deleted=True：账号行永不物理消失，
否则该账号历史上的操作痕迹就查无对证了。
"""
from flask import Blueprint, jsonify, request

from app.errors import fail

from app import db
from app.models import User
from app.services import auth as auth_svc

users_bp = Blueprint('users', __name__)

MIN_LENGTH = 6


def _body():
    return request.get_json(silent=True) or {}


def _target(id):
    """按 id 取未删除账号，取不到返回 None（调用方给 404）。"""
    return User.query.filter_by(id=id).first()


def _last_admin_guard(user, action):
    """保住最后一个可用管理员，否则没人能再管账号。"""
    if user.role == auth_svc.ADMIN and auth_svc.active_admin_count() <= 1:
        return fail(f"这是最后一个可用管理员，不能{action}", 400, "last_admin")
    return None


@users_bp.route('/users', methods=['GET'])
def list_users():
    rows = User.query.order_by(User.role.desc(), User.username).all()
    return jsonify([u.to_dict() for u in rows])


@users_bp.route('/users', methods=['POST'])
def create_user():
    body = _body()
    username = str(body.get('username') or '').strip()
    password = str(body.get('password') or '')
    role = str(body.get('role') or auth_svc.SALES)
    if not username:
        return fail("请填写账号名", 400)
    if len(password) < MIN_LENGTH:
        return fail(f"口令至少 {MIN_LENGTH} 位", 400)
    if role not in auth_svc.ROLES:
        return fail("角色只能是 admin 或 sales", 400)
    user = auth_svc.create_user(username, password, role=role,
                                display_name=str(body.get('display_name') or ''))
    return jsonify(user.to_dict()), 201


@users_bp.route('/users/<int:id>', methods=['PUT'])
def update_user(id):
    user = _target(id)
    if user is None:
        return fail("账号不存在", 404)
    body = _body()
    role = str(body.get('role') or user.role)
    if role not in auth_svc.ROLES:
        return fail("角色只能是 admin 或 sales", 400)
    is_active = body.get('is_active')
    is_active = user.is_active if is_active is None else bool(is_active)
    from flask import session
    if user.id == session.get('uid') and not is_active:
        return fail("不能停用自己当前登录的账号", 400, "self_action")
    if (not is_active or role != auth_svc.ADMIN) and user.is_active and user.role == auth_svc.ADMIN:
        blocked = _last_admin_guard(user, '停用或降级')
        if blocked is not None:
            return blocked
    user.display_name = str(body.get('display_name') if body.get('display_name') is not None
                            else user.display_name or '').strip()
    user.role = role
    user.is_active = is_active
    db.session.commit()
    return jsonify(user.to_dict())


@users_bp.route('/users/<int:id>/password', methods=['POST'])
def reset_password(id):
    user = _target(id)
    if user is None:
        return fail("账号不存在", 404)
    password = str(_body().get('password') or '')
    if len(password) < MIN_LENGTH:
        return fail(f"口令至少 {MIN_LENGTH} 位", 400)
    auth_svc.set_password(user, password)
    return jsonify({"ok": True})


@users_bp.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    user = _target(id)
    if user is None:
        return fail("账号不存在", 404)
    from flask import session
    if user.id == session.get('uid'):
        return fail("不能删除自己当前登录的账号", 400, "self_action")
    if user.is_active and user.role == auth_svc.ADMIN:
        blocked = _last_admin_guard(user, '删除')
        if blocked is not None:
            return blocked
    user.is_deleted = True
    user.is_active = False
    db.session.commit()
    return jsonify({"ok": True, "count": 1})
