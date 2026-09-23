"""采集报错分类器：把原始异常文本翻译成「可直接识别的错误类型」。

采集链路的报错来源很杂——requests 的 ConnectionError、HTTP 状态码、AI 接口
返回的 JSON 错误体、SQLite 的 OperationalError、页面改版后的解析异常……
把这些原文直接丢给使用者，既看不懂该不该重试，也不知道下一步该做什么。

这里统一做一次归类，例如：

    raw  = 'AI 接口返回 HTTP 402: {"error":{"code":"insufficient_quota"}}'
    ->   {code: 'ai_quota', label: '模型额度不足',
          hint: '模型账户额度/余额已耗尽，请充值或更换 API Key'}

    raw  = 'HTTP 403'
    ->   {code: 'antibot', label: '网站反爬拒绝访问',
          hint: '目标站点拒绝了本次请求，建议降低频率或稍后重试'}

分类结果写入 CrawlLog.error_types / error_detail，前端直接按类型渲染标签。
"""
import re

# ---------------------------------------------------------------------------
# 错误类型字典（唯一事实来源）
# ---------------------------------------------------------------------------
# severity: error 严重（需要处理）/ warning 警告（可重试）/ info 提示（非故障）
# retryable: 是否建议直接重试
ERROR_TYPES = {
    # ------------------------------ 模型（AI）侧 ------------------------------
    'ai_quota': {
        'label': '模型额度不足', 'category': '模型服务', 'severity': 'error', 'retryable': False,
        'hint': '模型账户额度/余额已耗尽，请为 API Key 充值，或更换可用模型/Key。',
    },
    'ai_auth': {
        'label': '模型鉴权失败', 'category': '模型服务', 'severity': 'error', 'retryable': False,
        'hint': 'API Key 无效或已过期，请在「AI 配置」中更新 Key 与 Endpoint。',
    },
    'ai_rate_limit': {
        'label': '模型请求限流', 'category': '模型服务', 'severity': 'warning', 'retryable': True,
        'hint': '触发模型调用频率/并发上限，稍后重试或降低单次采集条数。',
    },
    'ai_unavailable': {
        'label': '模型服务不可用', 'category': '模型服务', 'severity': 'error', 'retryable': True,
        'hint': '无法连通模型服务（连接被拒/超时/服务未启动/模型不存在），请确认模型服务已运行。',
    },
    'ai_bad_response': {
        'label': '模型返回异常', 'category': '模型服务', 'severity': 'warning', 'retryable': True,
        'hint': '模型输出不是预期的 JSON 结构，可重试；持续出现请检查模型与提示词。',
    },
    'ai_timeout': {
        'label': '模型响应超时', 'category': '模型服务', 'severity': 'warning', 'retryable': True,
        'hint': '模型推理时间超过等待上限，可重试或换用更快的模型。',
    },

    # ------------------------------ 目标网站侧 ------------------------------
    'antibot': {
        'label': '网站反爬拒绝访问', 'category': '目标网站', 'severity': 'error', 'retryable': False,
        'hint': '目标站点识别为自动化访问并拒绝（403/拦截页/验证码），请降低频率、更换出口 IP 或稍后重试。',
    },
    'web_rate_limited': {
        'label': '网站访问限流', 'category': '目标网站', 'severity': 'warning', 'retryable': True,
        'hint': '短时间内请求过多被站点限流（429/访问过于频繁），请稍后重试并减少关键词数量。',
    },
    'web_captcha': {
        'label': '触发网站验证码', 'category': '目标网站', 'severity': 'error', 'retryable': False,
        'hint': '站点要求人机校验，需人工介入或更换采集通道。',
    },
    'http_error': {
        'label': '网站返回错误', 'category': '目标网站', 'severity': 'error', 'retryable': True,
        'hint': '目标站点返回 4xx/5xx 状态码，请检查采集地址是否有效，或稍后重试。',
    },
    'site_changed': {
        'label': '站点结构变化', 'category': '目标网站', 'severity': 'warning', 'retryable': False,
        'hint': '页面结构已变或未匹配到列表节点，请检查目标站点是否改版。',
    },
    'not_found': {
        'label': '页面不存在', 'category': '目标网站', 'severity': 'warning', 'retryable': False,
        'hint': '目标页面返回 404，链接可能已失效。',
    },

    # ------------------------------ 网络链路 ------------------------------
    'network_error': {
        'label': '网络连接异常', 'category': '网络链路', 'severity': 'error', 'retryable': True,
        'hint': '域名解析/连接超时/SSL/代理异常，请检查本机网络与代理设置后重试。',
    },

    # ------------------------------ 解析与数据 ------------------------------
    'parse_error': {
        'label': '页面解析失败', 'category': '解析与数据', 'severity': 'warning', 'retryable': False,
        'hint': '正文或字段解析失败，可能是页面改版或内容缺失。',
    },
    'db_error': {
        'label': '数据库写入失败', 'category': '解析与数据', 'severity': 'error', 'retryable': True,
        'hint': '数据库锁/只读/磁盘异常导致入库失败，服务会自动重建连接，请重试。',
    },
    'empty_result': {
        'label': '无采集结果', 'category': '解析与数据', 'severity': 'info', 'retryable': False,
        'hint': '该关键词/来源本次没有搜到公告，可放宽关键词或扩大时间范围。',
    },

    # ------------------------------ 兜底 ------------------------------
    'unknown': {
        'label': '未知异常', 'category': '其他', 'severity': 'error', 'retryable': False,
        'hint': '未能自动识别类型，请查看原始报错信息进一步排查。',
    },
}

# 前端图例顺序
_TYPE_ORDER = list(ERROR_TYPES.keys())

# ---------------------------------------------------------------------------
# HTTP 状态码 → 错误类型（按阶段区分，因为同一个码在模型侧/网站侧含义不同）
# ---------------------------------------------------------------------------
_AI_STATUS = {
    400: 'ai_bad_response', 401: 'ai_auth', 402: 'ai_quota', 403: 'ai_auth',
    404: 'ai_unavailable', 422: 'ai_bad_response', 429: 'ai_rate_limit',
}
_WEB_STATUS = {
    400: 'http_error', 401: 'antibot', 403: 'antibot',
    404: 'not_found', 429: 'web_rate_limited',
}

# ---------------------------------------------------------------------------
# 文本特征规则（按顺序匹配，越具体的越靠前）
# ---------------------------------------------------------------------------
# 额度/鉴权这两个关键词列表同时用于「覆盖状态码」：服务商常把额度不足塞在
# HTTP 400 的 body 里，若只看状态码会误判成「模型返回异常」，因此它们优先级最高。
_AI_QUOTA_PATTERNS = [
    r'insufficient[_\s-]?quota', r'exceeded your current quota', r'quota[_\s-]?exceeded',
    r'out of credit', r'no credit', r'credit balance', r'billing', r'payment required',
    r'free tier', r'余额不足', r'额度不足', r'配额不足', r'配额已用尽', r'账户余额', r'欠费',
]
_AI_AUTH_PATTERNS = [
    r'invalid[_\s-]?api[_\s-]?key', r'incorrect api key', r'unauthorized',
    r'authentication fail', r'api key not valid', r'鉴权失败', r'密钥无效', r'认证失败',
]
_OVERRIDE_RULES = [('ai_quota', _AI_QUOTA_PATTERNS), ('ai_auth', _AI_AUTH_PATTERNS)]

_TEXT_RULES = [
    # 模型额度：关键词比状态码更可靠（很多服务把额度错误包在 200/400 里）
    ('ai_quota', _AI_QUOTA_PATTERNS),
    ('ai_auth', _AI_AUTH_PATTERNS),
    ('ai_rate_limit', [
        r'rate[_\s-]?limit', r'too many requests', r'\btpm\b', r'\brpm\b',
        r'请求过于频繁.*模型', r'模型.*限流',
    ]),
    ('ai_timeout', [r'ai 请求超时', r'模型响应超时']),
    ('ai_unavailable', [
        r'ai 请求异常', r'connection refused', r'failed to establish', r'max retries exceeded',
        r'no such model', r'model[_\s-]?not[_\s-]?found', r'model does not exist',
        r'模型未加载', r'模型不存在', r'服务未启动', r'bad gateway', r'service unavailable',
    ]),
    ('ai_bad_response', [
        r'ai 响应非 json', r'ai 响应格式异常', r'ai 输出无法解析', r'ai 输出为空',
        r'非 json 格式', r'unable to parse', r'json 解析',
    ]),
    # 网站限流要排在反爬之前：'访问过于频繁' 是限流而非硬封锁，
    # 两者的处置方式不同（一个稍后重试即可，一个需要换 IP/人工介入）
    ('web_rate_limited', [
        r'访问过于频繁', r'频繁访问', r'限流', r'too many requests', r'请求过于频繁',
    ]),
    # 网站反爬
    ('web_captcha', [r'验证码', r'captcha', r'人机校验', r'安全验证']),
    ('antibot', [
        r'访问被拒', r'拒绝访问', r'access denied', r'forbidden',
        r'anti[_\s-]?bot', r'robot', r'\bwaf\b', r'拦截', r'封禁', r'blocked',
    ]),
    ('site_changed', [r'结构变化', r'未匹配到', r'列表节点']),
    ('empty_result', [r'搜索结果为\s*0\s*条', r'结果为\s*0', r'无结果', r'无命中', r'未找到匹配']),
    ('db_error', [
        r'sqlite', r'operationalerror', r'integrityerror', r'database is locked',
        r'readonly', r'disk i/o', r'入库失败', r'数据库',
    ]),
    ('network_error', [
        r'timeout', r'timed out', r'超时', r'name resolution', r'域名解析',
        r'connection reset', r'connection aborted', r'connection error', r'newconnectionerror',
        r'ssl', r'proxy', r'network is unreachable', r'远程主机强迫关闭', r'连接被关闭', r'无法连接',
    ]),
    ('parse_error', [r'解析失败', r'解析异常', r'parse error', r'解析出错']),
]

_STATUS_RE = re.compile(r'^([45]\d{2})$')


def _extract_status(raw):
    """从文本里提取 HTTP 状态码。

    只在「HTTP 403」「状态码: 502」这类有明确前缀、或整串就是一个状态码时才算数：
    直接全文搜 4xx/5xx 会把端口号（443）、超时秒数（read timeout=240）当成状态码，
    导致把「模型响应超时」误判成「模型服务不可用」。
    """
    m = re.search(r'http[\s/]*([45]\d{2})\b', raw, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'(?:status|status[_ ]?code|状态码|状态)[\s:：=]*([45]\d{2})\b', raw, re.I)
    if m:
        return int(m.group(1))
    m = _STATUS_RE.match(raw.strip())
    return int(m.group(1)) if m else None


def _verdict(code, raw, matched=''):
    meta = ERROR_TYPES.get(code) or ERROR_TYPES['unknown']
    out = {
        'code': code,
        'label': meta['label'],
        'category': meta['category'],
        'severity': meta['severity'],
        'retryable': meta['retryable'],
        'hint': meta['hint'],
    }
    if matched:
        out['matched'] = matched
    return out


def _normalize_stage(stage):
    """把调用方传入的中文阶段名（如 'AI抽取'/'详情抓取'）归一为 ai/web/db/parse。"""
    s = str(stage or '').strip().lower()
    if not s:
        return ''
    if s.startswith('ai') or '模型' in s:
        return 'ai'
    if s in ('db', '入库', '数据库'):
        return 'db'
    if s == 'parse' or '解析' in s:
        return 'parse'
    if any(k in s for k in ('web', 'http', '列表页', '详情', '关键词', '搜索', '站点', '网站')):
        return 'web'
    return ''


def classify_error(raw, stage=''):
    """把一条原始报错文本归类为可直接识别的错误类型。

    stage 取值：'ai'（模型调用）/ 'web'（抓取网页）/ 'db'（入库）/ 'parse'（解析）/ ''（自动）。
    也接受中文阶段名（'AI抽取'、'详情抓取'…），内部会自动归一。
    返回 dict：code / label / category / severity / retryable / hint。
    """
    text = str(raw or '').strip()
    low = text.lower()
    stage = _normalize_stage(stage)

    # 1) 状态码优先：同一个码在模型侧与网站侧含义完全不同
    status = _extract_status(text)
    if status is not None:
        # 但额度/鉴权这类高辨识度关键词要先看：服务商常把「额度不足」包在
        # HTTP 400/403 的响应体里，只看状态码会误判成「模型返回异常」
        for code, patterns in _OVERRIDE_RULES:
            for p in patterns:
                m = re.search(p, low, re.I)
                if m:
                    return _verdict(code, text, m.group(0))
        if status >= 500:
            # 5xx 两边都属于「对方服务端故障」；模型侧更常见的是网关/未启动
            if stage == 'ai' or 'ai 接口' in low or 'ai 请求' in low:
                return _verdict('ai_unavailable', text, f'HTTP {status}')
            return _verdict('http_error', text, f'HTTP {status}')
        table = _AI_STATUS if (stage == 'ai' or 'ai 接口' in low) else _WEB_STATUS
        code = table.get(status)
        if code:
            return _verdict(code, text, f'HTTP {status}')
        # 4xx 未收录：模型侧按返回异常，网站侧按http错误
        return _verdict('ai_bad_response' if stage == 'ai' else 'http_error', text, f'HTTP {status}')

    # 2) 模型阶段的超时要单独识别：不能与普通网络超时混为一谈
    if stage == 'ai' and re.search(r'timeout|timed out|超时', low, re.I):
        return _verdict('ai_timeout', text, 'timeout')

    # 3) 文本特征
    for code, patterns in _TEXT_RULES:
        for p in patterns:
            m = re.search(p, low, re.I)
            if m:
                return _verdict(code, text, m.group(0))

    # 4) 阶段兜底
    if stage == 'ai':
        return _verdict('ai_unavailable', text)
    if stage == 'db':
        return _verdict('db_error', text)
    if stage == 'parse':
        return _verdict('parse_error', text)
    if stage == 'web':
        return _verdict('http_error', text)
    return _verdict('unknown', text)


def classify_record(record, default_stage=''):
    """把 {stage,target,raw} 记录补齐分类字段，返回可直接落库的 dict。"""
    if isinstance(record, dict):
        raw = str(record.get('raw') or '')
        stage = record.get('stage') or default_stage
        target = str(record.get('target') or '')
    else:
        raw, stage, target = str(record), default_stage, ''
    v = classify_error(raw, stage)
    return {
        'stage': stage,
        'target': target[:200],
        'raw': raw[:600],
        'code': v['code'],
        'label': v['label'],
        'category': v['category'],
        'severity': v['severity'],
        'retryable': v['retryable'],
        'hint': v['hint'],
    }


def summarize(classified):
    """按类型汇总：[{code,label,category,severity,count}]，按数量倒序。"""
    bucket = {}
    for item in classified or []:
        code = item.get('code') or 'unknown'
        entry = bucket.setdefault(code, {
            'code': code,
            'label': item.get('label') or ERROR_TYPES.get(code, ERROR_TYPES['unknown'])['label'],
            'category': item.get('category') or ERROR_TYPES.get(code, ERROR_TYPES['unknown'])['category'],
            'severity': item.get('severity') or ERROR_TYPES.get(code, ERROR_TYPES['unknown'])['severity'],
            'count': 0,
        })
        entry['count'] += 1
    return sorted(bucket.values(), key=lambda x: (-x['count'], _TYPE_ORDER.index(x['code'])
                                                  if x['code'] in _TYPE_ORDER else 999))


def format_error(record, with_raw=False):
    """给运行态状态栏用的短文本：'[模型额度不足] 关键词:无人机'。

    with_raw=True 时补上原始报错片段，便于在进度条上直接看到具体原因。
    """
    if isinstance(record, dict):
        label = record.get('label') or classify_error(record.get('raw'), record.get('stage', ''))['label']
        target = record.get('target') or ''
        raw = str(record.get('raw') or '')
    else:
        label = classify_error(record)['label']
        target, raw = '', str(record)
    parts = [f'[{label}]']
    if target:
        parts.append(target)
    if with_raw and raw:
        parts.append(f'({raw[:80]})')
    return ' '.join(parts)


def taxonomy():
    """错误类型字典（前端图例/筛选下拉用），按预定义顺序返回。"""
    return [
        {'code': code, 'label': meta['label'], 'category': meta['category'],
         'severity': meta['severity'], 'retryable': meta['retryable'], 'hint': meta['hint']}
        for code, meta in ERROR_TYPES.items()
    ]
