"""操作日志查询接口（管理员）+ 前端点击埋点入口（全员）。

- /audit/*：读日志、读每日汇总、重新归档、导出。整个前缀已登记为管理员专属
  （见 app/__init__.py 的 _ADMIN_PREFIXES），所以这里不必再逐个加装饰器。
- /track：埋点上报。任何登录账号都会产生点击，把它放在 /audit 前缀之外，
  否则普通销售点一下菜单就吃 403。
"""
import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, request

from app import db
from app.errors import fail
from app.models import OperationLog
from app.services import audit

audit_bp = Blueprint('audit', __name__)

_EXPORT_LIMIT = 20000


def _log_item(log):
    return {
        'id': log.id,
        'time': log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
        'user': log.user or '',
        'action': log.action or '',
        'module': log.module or '',
        'detail': log.detail or '',
        'method': log.method or '',
        'path': log.path or '',
        'status_code': log.status_code or 0,
        'duration_ms': log.duration_ms or 0,
        'ip': log.ip or '',
    }


def _apply_window(query, args):
    """days=today|7|30|all，或显式 start/end（YYYY-MM-DD）。"""
    days = (args.get('days') or '').strip()
    start = (args.get('start') or '').strip()
    end = (args.get('end') or '').strip()
    if start:
        try:
            query = query.filter(OperationLog.created_at >= datetime.strptime(start, '%Y-%m-%d'))
        except ValueError:
            pass
    else:
        if days == 'today':
            query = query.filter(
                OperationLog.created_at >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
        elif days and days != 'all':
            try:
                query = query.filter(OperationLog.created_at >= datetime.now() - timedelta(days=int(days)))
            except (TypeError, ValueError):
                pass
    if end:
        try:
            query = query.filter(OperationLog.created_at
                                 < datetime.strptime(end, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            pass
    return query


def _log_query():
    """列表、统计、导出共用同一套过滤条件，口径才不会各说各话。"""
    args = request.args
    query = _apply_window(OperationLog.query, args)
    for field, column in (('user', OperationLog.user),
                          ('action', OperationLog.action),
                          ('module', OperationLog.module)):
        value = (args.get(field) or '').strip()
        if value and value != 'all':
            names = [v.strip() for v in value.split(',') if v.strip()]
            query = query.filter(column.in_(names))
    if (args.get('result') or '').strip() == 'fail':
        query = query.filter(OperationLog.status_code >= 400)
    kw = (args.get('q') or '').strip()
    if kw:
        like = f'%{kw}%'
        query = query.filter(db.or_(
            OperationLog.detail.like(like), OperationLog.path.like(like),
            OperationLog.user.like(like), OperationLog.module.like(like),
        ))
    return query


@audit_bp.route('/audit/logs', methods=['GET'])
def list_logs():
    """操作日志明细：时间倒序 + 分页，并附同口径的统计与筛选枚举。"""
    base = _log_query()
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(200, max(1, int(request.args.get('page_size', 50))))
    except (TypeError, ValueError):
        page_size = 50

    total = base.count()
    logs = (base.order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())

    # 统计只算当前筛选命中的行，与分页无关；上限 5000 行避免把全表拉进内存
    scope = _apply_window(OperationLog.query, request.args)
    rows = scope.with_entities(OperationLog.user, OperationLog.action,
                               OperationLog.module, OperationLog.status_code) \
                 .limit(5000).all()
    by_action, by_user, by_module = {}, {}, {}
    failures = 0
    for user, action, module, status_code in rows:
        by_action[action] = by_action.get(action, 0) + 1
        by_user[user] = by_user.get(user, 0) + 1
        if module:
            by_module[module] = by_module.get(module, 0) + 1
        if (status_code or 0) >= 400:
            failures += 1

    return jsonify({
        'items': [_log_item(log) for log in logs],
        'total': total,
        'page': page,
        'page_size': page_size,
        'stats': {
            'scoped': len(rows),
            'failures': failures,
            'active_users': len(by_user),
            'by_action': dict(sorted(by_action.items(), key=lambda kv: -kv[1])),
            'by_user': dict(sorted(by_user.items(), key=lambda kv: -kv[1])),
            'by_module': dict(sorted(by_module.items(), key=lambda kv: -kv[1])),
        },
        'users': sorted({u for (u,) in db.session.query(OperationLog.user).distinct().all() if u}),
        'actions': sorted({a for (a,) in db.session.query(OperationLog.action).distinct().all() if a}),
        'modules': sorted({m for (m,) in db.session.query(OperationLog.module).distinct().all() if m}),
    })


@audit_bp.route('/audit/summary', methods=['GET'])
def get_summary():
    """最近 N 天的每日汇总（默认 30 天）。"""
    try:
        days = int(request.args.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    return jsonify({'days': audit.summary_range(days), 'days_requested': max(1, min(365, days))})


@audit_bp.route('/audit/summary', methods=['POST'])
def rebuild_summary():
    """立即生成/重算某一天的日志总结（默认今天）。按 day 覆盖，不产生重复行。"""
    body = request.get_json(silent=True) or {}
    day = str(body.get('day') or datetime.now().strftime('%Y-%m-%d'))
    try:
        datetime.strptime(day, '%Y-%m-%d')
    except ValueError:
        return fail('日期格式应为 YYYY-MM-DD', 400, 'bad_date')
    data = audit.archive_day(day)
    return jsonify({'ok': True, 'day': day, 'summary': data,
                    'message': f'{day} 的日志总结已生成（{data["total"]} 次操作）'})


@audit_bp.route('/audit/export', methods=['GET'])
def export_logs():
    """导出当前筛选条件下的操作日志 CSV（最多 2 万行）。"""
    rows = (_log_query().order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
            .limit(_EXPORT_LIMIT).all())
    if not rows:
        return fail('当前筛选条件下没有日志可导出', 400, 'empty_export')

    from urllib.parse import quote
    buf = io.StringIO()
    buf.write('\ufeff')  # BOM：Excel 直接双击打开不乱码
    writer = csv.writer(buf)
    writer.writerow(['时间', '用户', '操作', '模块', '操作内容', '接口', '状态码', '耗时(ms)', '来源IP'])
    for log in rows:
        item = _log_item(log)
        writer.writerow([item['time'], item['user'], item['action'], item['module'],
                         item['detail'], f"{item['method']} {item['path']}".strip(),
                         item['status_code'], item['duration_ms'], item['ip']])
    filename = f'操作日志_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
    resp = Response(buf.getvalue().encode('utf-8'), mimetype='text/csv; charset=utf-8')
    # HTTP 头只支持 latin-1：中文文件名按 RFC 5987 百分号编码
    resp.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return resp


@audit_bp.route('/track', methods=['POST'])
def track_click():
    """前端点击埋点：菜单/页面访问、关键按钮。

    这里只接受 page/target 两个短字符串，且立即截断：埋点接口要是能被写入
    任意长文本，日志表就会变成垃圾场。
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        body = {}
    page = audit.clip(body.get('page') or '', 30)
    target = audit.clip(body.get('target') or '', 30)
    detail = audit.build_detail('点击', '页面', {'page': page, 'target': target}, 200)
    # 模块固定「页面」，页名留在操作内容里：否则模块下拉会被十几个页面名撑满，
    # 想按页筛用关键词搜 detail 就够了。
    audit.record('点击', '页面', detail, path='/api/track', method='POST')
    return jsonify({'ok': True})
