"""操作日志：谁、什么时候、做了什么，以及每天的汇总统计。

记账口径：
- 后端用 before/after_request 中间件统一记账，不在 90 多个端点里逐个埋点。
  逐个埋的结果一定是「新接口忘了埋」，而漏埋的那类操作在审计里就等于没发生。
- 「点击」只能由前端上报（POST /api/track）：菜单跳转、弹窗打开不产生独立的
  后端请求，中间件看不到。
- 失败请求同样记录（401 登录失败、403 越权、400 参数错、500 崩溃）。
  审计最想看见的恰恰是这些。
- 口令/API key 之类的字段永不进日志，只记字段名。

写入永不反噬业务：每次记账自带 commit + try/except，日志表出问题
（网络卷抖动、库锁）最多丢一行日志，绝不能把用户的请求一起拖死。
"""
import json
import re
import time
from datetime import datetime, timedelta

from flask import g, request

from app import db

# 只记字段名、绝不记字段值的请求键
SENSITIVE_KEYS = frozenset({
    'password', 'new_password', 'old_password', 'current_password', 'confirm_password',
    'api_key', 'apikey', 'key', 'token', 'access_token', 'secret', 'auth_password_hash',
})
# 分页/缓存穿透用的参数，展示成「筛选条件」只会干扰阅读
_NOISE_ARGS = frozenset({'page', 'page_size', 'per_page', '_t', 'ts', 'limit', 'offset'})

# 路径首段 → 业务模块中文名（决定「操作内容」的主语，也是筛选下拉的枚举）
_SEGMENT_MODULE = {
    'auth': '登录', 'leads': '线索', 'customers': '客户', 'contacts': '联系人',
    'opportunities': '商机', 'stages': '商机', 'activities': '联络记录',
    'followups': '联络计划', 'kanban': '看板', 'config': '系统设置',
    'users': '账号管理', 'skills': '技能', 'crawl': '采集', 'news': '新闻采集',
    'audit': '操作日志', 'dashboard': '工作台', 'daily-tasks': '工作台',
    'analytics': '报表', 'search': '检索', 'export': '导出', 'options': '通用',
    'ai': 'AI 任务', 'error-types': '采集', 'suggestions': 'AI 建议', 'track': '页面',
}
_METHOD_ACTION = {'GET': '查询', 'POST': '新增', 'PUT': '修改', 'PATCH': '修改', 'DELETE': '删除'}
# 这些接口的语义不是「新增」：按路径正则改写成更贴切的动作名
_ACTION_RULES = [
    (re.compile(r'^/api/auth/login$'), '登录'),
    (re.compile(r'^/api/auth/logout$'), '登出'),
    (re.compile(r'^/api/auth/setup$'), '初始化'),
    (re.compile(r'^/api/auth/change$'), '改密'),
    (re.compile(r'^/api/users/\d+/password$'), '重置口令'),
    (re.compile(r'^/api/leads/\d+/claim$'), '领取'),
    (re.compile(r'^/api/leads/\d+/release$'), '释放'),
    (re.compile(r'^/api/leads/\d+/convert$'), '转化'),
    (re.compile(r'^/api/leads/batch$'), '批量操作'),
    (re.compile(r'^/api/crawl$'), '采集'),
    (re.compile(r'^/api/news/collect-all$'), '采集'),
    (re.compile(r'^/api/(?:customers|contacts)/\d+/collect-news$'), '采集'),
    (re.compile(r'^/api/followups/\d+/execute$'), '执行'),
    (re.compile(r'^/api/skills/[^/]+/execute$'), '执行'),
    (re.compile(r'^/api/ai/urgent-tasks/refresh$'), '执行'),
    (re.compile(r'^/api/config/backup-now$'), '备份'),
    (re.compile(r'^/api/config/(?:ai-providers|crawl-targets|scheduler)$'), '修改'),
    (re.compile(r'^/api/(?:leads|customers|contacts|opportunities|activities|followups)/\d+/restore$'), '恢复'),
    (re.compile(r'^/api/export/'), '导出'),
]
# 埋点接口自身不再记账：那一行已经作为「点击」写进去了，再记一次就成两条。
# /api/crawl/status 是前端采集期间的 6 秒轮询，一次采集能刷出二十行「查询」，
# 而采集收尾已经由 crawl_log 写了「系统」那条汇总，进度轮询不算用户操作。
_SKIP_PATHS = frozenset({'/api/track', '/api/crawl/status'})
# SPA 兜底/静态资源不是业务操作，记下来只有噪音
_SKIP_ENDPOINTS = frozenset({'serve_index', 'serve_spa'})
# 采集线程跑在后台，收尾时没有请求上下文，用它自己那条流水名
SYSTEM_ACTOR = '系统'


def module_of(path):
    """由路径推断业务模块中文名。"""
    parts = [p for p in (path or '').split('/') if p]
    if len(parts) >= 2 and parts[0] == 'api':
        return _SEGMENT_MODULE.get(parts[1], '其他')
    return '其他'


def action_of(method, path):
    for pattern, action in _ACTION_RULES:
        if pattern.match(path or ''):
            return action
    return _METHOD_ACTION.get(method, '其他')


def _target_id(path):
    """路径里第一个数字段就是被操作记录的主键（/api/leads/12/convert → 12）。"""
    m = re.search(r'/(\d+)(?:/|$)', path or '')
    return m.group(1) if m else ''


def clip(value, limit=40):
    """压成一行、限长：日志的 detail 列只有 300 字符，用户提交的正文必须截断。"""
    text = str(value).replace('\n', ' ').strip()
    return text[:limit] + '…' if len(text) > limit else text


def _req_json():
    """请求体 JSON；非 JSON、超大体（公告全文）一律当空，解析失败也不报错。"""
    try:
        if not request.is_json:
            return {}
        data = request.get_json(silent=True)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_body(body):
    """脱敏后的键名列表 + 可读标识值：值只取名称类字段，凭据类字段永不外泄。"""
    keys = [str(k) for k in body]
    shown = [k for k in keys if k.lower() not in SENSITIVE_KEYS]
    hidden = [k for k in keys if k.lower() in SENSITIVE_KEYS]
    return shown, hidden


def _filters_text(limit=3):
    """把查询参数压成「状态=active, 关键词=松材」这样的短标签。"""
    items = []
    for key in request.args:
        if key.lower() in SENSITIVE_KEYS or key in _NOISE_ARGS:
            continue
        if len(items) >= limit:
            items.append('…')
            break
        items.append(f'{key}={clip(request.args.get(key) or "", 24)}')
    return ', '.join(items)


def build_detail(action, module, body, status_code, resp_json=None):
    """拼出给人看的「操作内容」。宁可写得普通，也绝不写进敏感值。"""
    ident = _target_id(request.path)
    if action == '登录':
        if status_code < 400:
            return '登录成功'
        who = clip(body.get('username') or '（空账号）', 30)
        return f'登录失败：账号 {who}'
    if action == '登出':
        return '退出登录'
    if action == '初始化':
        return '初始化系统管理员账号'
    if action == '改密':
        return '修改自己的口令'
    if action == '点击':
        page = clip(body.get('page') or '', 30)
        target = clip(body.get('target') or '', 30)
        if target:
            return f'点击「{target}」（{page}）' if page else f'点击「{target}」'
        return f'访问页面「{page}」' if page else '页面内点击'
    if action == '导出':
        return f'导出{module}数据'
    if action == '采集':
        return f'触发{module}'
    if action == '备份':
        return '手动执行数据库备份'
    if action == '批量操作':
        ids = body.get('ids')
        n = len(ids) if isinstance(ids, list) else 0
        op = clip(body.get('op') or '操作', 20)
        return f'批量{op} {n} 条线索'
    if action == '查询':
        if ident and not request.query_string:
            return f'查看{module} #{ident} 详情'
        if ident:
            return f'查看{module} #{ident} 明细'
        cond = _filters_text()
        return f'查看{module}列表' + (f'（{cond}）' if cond else '')
    if action == '删除':
        return f'删除{module} #{ident}' if ident else f'删除{module}'
    if action == '修改':
        shown, hidden = _safe_body(body)
        parts = [f'字段 {",".join(shown[:8])}' if shown else '无字段变更']
        if hidden:
            parts.append('含凭据字段')
        return f'修改{module} #{ident}：' + '; '.join(parts)
    if action in ('新增', '执行', '领取', '释放', '转化', '恢复', '编辑', '重置口令'):
        name = ''
        for key in ('name', 'title', 'content', 'display_name', 'username', 'remark'):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                name = clip(value)
                break
        new_id = ''
        if isinstance(resp_json, dict) and resp_json.get('id') is not None:
            new_id = f'（#{resp_json["id"]}）'
        label = f'：{name}' if name else ''
        if ident and action in ('执行', '领取', '释放', '转化', '恢复', '重置口令'):
            return f'{action}{module} #{ident}{label}{new_id}'
        return f'{action}{module}{label}{new_id}'
    return f'{action}{module}'


def http_actor():
    """本次请求的记账用户名。

    AUTH_DISABLED（测试基线）下拿不到身份，记「未登录」而不是「系统」：
    「系统」专指采集线程、定时任务这类无人值守写入，两者混在一起，
    汇总统计就分不出「无人做的」和「有人做但没登记身份」的。
    """
    from flask import current_app
    from app.services.auth import current_user
    if current_app.config.get('AUTH_DISABLED'):
        return '未登录'
    user = current_user()
    if user is None:
        return '未登录'
    return user.name or user.username


def record(action, module, detail, user=None, path=None, method=None,
           status_code=200, duration_ms=0, ip=None):
    """写一行日志并独立提交。返回是否写入成功，失败只吞掉异常。"""
    from app.models import OperationLog
    if user is None:
        user = http_actor() if _has_request() else SYSTEM_ACTOR
    try:
        db.session.add(OperationLog(
            user=(user or SYSTEM_ACTOR)[:50],
            action=(action or '其他')[:20],
            module=(module or '')[:30],
            detail=(detail or '')[:300],
            method=(method or (request.method if _has_request() else ''))[:8],
            path=(path or (request.path if _has_request() else ''))[:200],
            status_code=status_code,
            duration_ms=int(duration_ms or 0),
            ip=(ip if ip is not None else _client_ip())[:40],
        ))
        db.session.commit()
        return True
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False


def _has_request():
    from flask import has_request_context
    return has_request_context()


def _client_ip():
    if not _has_request():
        return ''
    return (request.headers.get('X-Forwarded-For', '').split(',')[0].strip()
            or request.remote_addr or 'unknown')


def log_action(action, module, detail, user=SYSTEM_ACTOR):
    """给非 HTTP 场景（定时采集、启动自愈）补一行流水。"""
    return record(action, module, detail, user=user, method='', path='', status_code=200)


def install_audit(app):
    """挂上请求级记账钩子。

    身份必须在 before_request 抓：登出会清空 session，等到 after_request
    再看就已经查不到是谁了。
    """
    @app.before_request
    def _audit_start():
        g.audit_t0 = time.monotonic()
        g.audit_user = http_actor() if request.path.startswith('/api/') else ''

    @app.after_request
    def _audit_after(response):
        try:
            _log_response(response)
        except Exception:
            # 记账失败绝不能演变成用户看到的 500
            try:
                db.session.rollback()
            except Exception:
                pass
        return response


def _log_response(response):
    path = request.path
    if not path.startswith('/api/') or request.method == 'OPTIONS':
        return
    if path in _SKIP_PATHS or (request.endpoint or '') in _SKIP_ENDPOINTS:
        return
    action = action_of(request.method, path)
    module = module_of(path)
    status = getattr(response, 'status_code', 0) or 0
    body = _req_json() if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') else {}
    resp_json = None
    if action in ('新增', '登录'):
        # 只有需要回读新建 id / 登录者姓名时才解析响应，列表响应可达数百 KB
        try:
            resp_json = response.get_json(silent=True)
        except Exception:
            resp_json = None
    detail = build_detail(action, module, body, status, resp_json if isinstance(resp_json, dict) else None)
    user = g.get('audit_user') or '未登录'
    if action == '登录' and isinstance(resp_json, dict):
        info = resp_json.get('user') or {}
        user = (info.get('display_name') or info.get('username') or user)
    duration = int((time.monotonic() - g.get('audit_t0', time.monotonic())) * 1000)
    record(action, module, detail, user=user, path=path, method=request.method,
           status_code=status, duration_ms=max(0, duration), ip=_client_ip())


# ---------------------------------------------------------------- 每日汇总

def _day_bounds(day):
    """'YYYY-MM-DD' → 当天 [00:00, +1d) 。"""
    start = datetime.strptime(day, '%Y-%m-%d')
    return start, start + timedelta(days=1)


def aggregate(start, end):
    """按 (天, 用户, 动作, 模块) 聚合，一次扫表出全部口径。

    分三次 group by 也能算，但那是三倍的全表扫描；列表页和归档任务都要用，
    合成一次之后在 Python 里拆三份，代价只在内存。
    """
    from sqlalchemy import case, func
    from app.models import OperationLog
    day_expr = func.date(OperationLog.created_at).label('day')
    bad_expr = func.sum(case((OperationLog.status_code >= 400, 1), else_=0)).label('bad')
    n_expr = func.count(OperationLog.id).label('n')
    rows = (db.session.query(day_expr, OperationLog.user, OperationLog.action,
                             OperationLog.module, n_expr, bad_expr)
            .filter(OperationLog.created_at >= start, OperationLog.created_at < end)
            .group_by(day_expr, OperationLog.user, OperationLog.action, OperationLog.module)
            .all())
    days = {}
    for day, user, action, module, n, bad in rows:
        bucket = days.setdefault(str(day), {
            'day': str(day), 'total': 0, 'failures': 0,
            'by_action': {}, 'by_module': {}, 'by_user': {}, 'user_actions': {},
        })
        bucket['total'] += n
        bucket['failures'] += bad or 0
        bucket['by_action'][action] = bucket['by_action'].get(action, 0) + n
        if module:
            bucket['by_module'][module] = bucket['by_module'].get(module, 0) + n
        bucket['by_user'][user] = bucket['by_user'].get(user, 0) + n
        bucket['user_actions'].setdefault(user, {})[action] = n
    for bucket in days.values():
        bucket['active_users'] = len(bucket['by_user'])
        bucket['headline'] = headline(bucket)
    return days


_ACTION_ORDER = ('登录', '查询', '点击', '新增', '修改', '删除', '采集', '执行', '转化',
                 '领取', '释放', '恢复', '批量操作', '导出', '备份', '登出', '改密', '初始化')


def headline(bucket):
    """把一天的计数写成一句人话总结，设置页直接展示。"""
    parts = []
    counts = bucket['by_action']
    for action in _ACTION_ORDER:
        if counts.get(action):
            parts.append(f'{action} {counts[action]}')
    for action in sorted(counts):
        if action not in _ACTION_ORDER and counts[action]:
            parts.append(f'{action} {counts[action]}')
    text = (f"{bucket['day']} 共 {bucket['total']} 次操作：" + '、'.join(parts))
    if bucket['active_users']:
        text += f"；活跃账号 {bucket['active_users']} 个（{'、'.join(sorted(bucket['by_user'])[:5])}）"
    if bucket['failures']:
        text += f"；失败 {bucket['failures']} 次"
    return text + '。'


def summarize_day(day):
    """某一天（'YYYY-MM-DD'）的汇总；没有日志时返回全零结构。"""
    start, end = _day_bounds(day)
    days = aggregate(start, end)
    if day in days:
        return days[day]
    return {'day': day, 'total': 0, 'failures': 0, 'active_users': 0,
            'by_action': {}, 'by_module': {}, 'by_user': {}, 'user_actions': {},
            'headline': f'{day} 无操作记录。'}


def archive_day(day):
    """生成并落库某天的汇总（按 day 覆盖写，重复执行不产生第二行）。"""
    from app.models import OperationSummary
    data = summarize_day(day)
    row = OperationSummary.query.filter_by(day=day).first()
    if row is None:
        row = OperationSummary(day=day)
        db.session.add(row)
    row.total = data['total']
    row.failures = data['failures']
    row.active_users = data['active_users']
    row.by_action = json.dumps(data['by_action'], ensure_ascii=False, separators=(',', ':'))
    row.by_module = json.dumps(data['by_module'], ensure_ascii=False, separators=(',', ':'))
    row.by_user = json.dumps(data['by_user'], ensure_ascii=False, separators=(',', ':'))
    row.user_actions = json.dumps(data['user_actions'], ensure_ascii=False, separators=(',', ':'))
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
    return data


def ensure_recent_summaries(days=7):
    """启动补齐：把「有日志但没归档」的最近若干天补上汇总。

    首次上线、或服务器在凌晨停过机时，定时任务不会自动回放；
    少了这一步，设置页的汇总表就会缺几天，看着像功能没生效。
    空日不建行（否则第一次启动会写出一排 0），今天的汇总交给列表现算。
    """
    from app.models import OperationLog, OperationSummary
    today = datetime.now().date()
    window = [(today - timedelta(days=offset)).strftime('%Y-%m-%d')
              for offset in range(days, 0, -1)]
    have = {r.day for r in OperationSummary.query.filter(OperationSummary.day.in_(window)).all()}
    done = []
    for day in window:
        if day in have:
            continue
        start, end = _day_bounds(day)
        if not OperationLog.query.filter(
                OperationLog.created_at >= start,
                OperationLog.created_at < end).first():
            continue
        archive_day(day)
        done.append(day)
    return done


def scheduled_archive_job():
    """定时任务入口：归档昨天，同时刷新今天（今天可能已有大量操作）。"""
    today = datetime.now().date()
    archive_day((today - timedelta(days=1)).strftime('%Y-%m-%d'))
    return archive_day(today.strftime('%Y-%m-%d'))


def summary_range(days=30):
    """最近 N 天的每日汇总列表，按日期倒序；今天始终现算，保证刷新即见。

    只列出有操作记录的日子：日志功能上线之前的日期没有数据，
    列出来只会是一屏「无操作记录」，干扰阅读。"""
    from app.models import OperationSummary
    days = max(1, min(365, int(days or 30)))
    today = datetime.now().date()
    start = (today - timedelta(days=days - 1)).strftime('%Y-%m-%d')
    stored = {r.day: r for r in OperationSummary.query.filter(
        OperationSummary.day >= start).all()}
    out = []
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).strftime('%Y-%m-%d')
        row = stored.get(day)
        if row is not None:
            if not (row.total or 0):
                continue
            out.append({
                'day': day, 'total': row.total or 0, 'failures': row.failures or 0,
                'active_users': row.active_users or 0,
                'by_action': _loads(row.by_action), 'by_module': _loads(row.by_module),
                'by_user': _loads(row.by_user), 'user_actions': _loads(row.user_actions),
                'archived': True,
            })
        else:
            data = summarize_day(day)
            if not data['total']:
                continue
            data['archived'] = False
            out.append(data)
    for item in out:
        item['headline'] = headline(item)
    return out


def _loads(text):
    from app.services.crawl_log import loads
    return loads(text, {})
