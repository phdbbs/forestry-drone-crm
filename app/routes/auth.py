from flask import Blueprint, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models.user import User

auth = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth.route('/login', methods=['POST'])
def login():
    d = request.get_json(silent=True) or {}
    username = (d.get('username') or '').strip()
    password = d.get('password') or ''
    remember = bool(d.get('remember'))
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return jsonify({'error': '用户名或密码错误'}), 401
    login_user(user, remember=remember)
    return jsonify({'user': user.to_dict()})


@auth.route('/logout', methods=['POST'])
def logout():
    logout_user()
    return jsonify({'ok': True})


@auth.route('/me', methods=['GET'])
def me():
    if current_user.is_authenticated:
        return jsonify({'user': current_user.to_dict()})
    # 401 是前端判断"未登录"的正常信号
    return jsonify({'user': None}), 401


@auth.route('/change-password', methods=['POST'])
@login_required
def change_password():
    d = request.get_json(silent=True) or {}
    old_password = d.get('old_password') or ''
    new_password = d.get('new_password') or ''
    if not current_user.check_password(old_password):
        return jsonify({'error': '原密码错误'}), 400
    if len(new_password) < 6:
        return jsonify({'error': '新密码至少 6 位'}), 400
    current_user.set_password(new_password)
    db.session.commit()
    return jsonify({'ok': True})
