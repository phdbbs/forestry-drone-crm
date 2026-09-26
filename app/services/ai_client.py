"""AI 客户端：调用 OpenAI 兼容接口（本地 qwen3-14b-mlx），用于招标信息抽取与每日跟进分析。"""
import json
import re
import threading
import time
import requests
from app import db
from app.models import SystemConfig
from app.services.textutil import clean_text

_ai_lock = threading.Lock()

# 这些状态码重试没有意义：请求体/密钥/额度的问题，重试 2 轮只会白等 30 秒，
# 还会把「模型额度不足」这类本可立刻识别的故障拖到超时。直接抛出交给分类器。
_NON_RETRYABLE_STATUS = {400, 401, 402, 403, 404, 422}

# response_format={"type":"json_object"} 探测结果：None 未试 / True 支持 / False 不支持。
# 支持的服务端会强制模型输出合法 JSON，从源头消灭「输出不是预期的 JSON 结构」；
# 不支持的服务商通常回 400，此时降级为纯提示词约束并记住结论，不再重复踩。
_json_mode_ok = None


def get_ai_config():
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    return {
        "endpoint": (configs.get("ai_api_endpoint") or "http://127.0.0.1:1234/v1").rstrip("/"),
        "api_key": configs.get("ai_api_key") or "",
        "model": configs.get("ai_model") or "qwen3-14b-mlx",
    }


def chat(messages, max_tokens=1200, temperature=0.2, timeout=240, retries=2, json_mode=False):
    """调用 AI 对话接口，返回 assistant content 文本。
    本地模型偶发崩溃：串行执行 + 失败自动重试（间隔 15 秒）。
    json_mode=True 时尝试 response_format 强制 JSON，服务商不认就自动降级。
    """
    global _json_mode_ok
    cfg = get_ai_config()
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    with _ai_lock:  # 串行调用，避免本地模型并发崩溃
        attempt = 0
        while attempt <= retries:
            payload = {
                "model": cfg["model"],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if json_mode and _json_mode_ok is not False:
                payload["response_format"] = {"type": "json_object"}
            try:
                resp = requests.post(
                    cfg["endpoint"] + "/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
            except Exception as e:
                attempt += 1
                if attempt <= retries:
                    time.sleep(15)
                    continue
                raise RuntimeError(f"AI 请求异常: {e}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    raise RuntimeError(f"AI 响应非 JSON 格式: {resp.text[:200]}")
                try:
                    content = data["choices"][0]["message"]["content"] or ""
                except (KeyError, IndexError, TypeError):
                    raise RuntimeError(f"AI 响应格式异常: {str(data)[:200]}")
                if json_mode:
                    _json_mode_ok = True
                return content
            body = (resp.text or '')[:500]
            # response_format 不被支持（常见报法各异）：记 False 降级重发本次请求（不计入重试额度）
            if (json_mode and resp.status_code in (400, 422) and _json_mode_ok is not False
                    and re.search(r'response_format|json[_\s-]?mode|unsupported', body, re.I)):
                _json_mode_ok = False
                continue
            # 保留完整错误体（最多 500 字符）：额度/鉴权类错误的关键词
            # （insufficient_quota、余额不足…）只在 body 里，截太短会分类不出来；
            # 且这类问题重试无意义，直接抛出交给分类器
            if resp.status_code in _NON_RETRYABLE_STATUS:
                raise RuntimeError(f"AI 接口返回 HTTP {resp.status_code}: {body}")
            attempt += 1
            if attempt <= retries:
                time.sleep(15)
                continue
            raise RuntimeError(f"AI 接口返回 HTTP {resp.status_code}: {body}")


def _balanced_spans(text, open_ch, close_ch):
    """扫描出文本中所有成对闭合的 {...} / [...] 片段（正确跳过字符串内的括号与转义）；
    末尾若遇未闭合块，把残片也带出，交给 _repair_truncated 抢救。"""
    out = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] != open_ch:
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        j = i
        while j < n:
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        if j < n:
            out.append(text[i:j + 1])
            i = j + 1
        else:
            out.append(text[i:])
            break
    return out


def _top_level_spans(text):
    """按文档顺序返回所有最外层 {...} / [...] 片段（含未闭合尾片）。
    识别一对括号后把游标跳到其闭合位之后，天然跳过所有嵌套——因此返回的
    一定是彼此不平级的顶层结构，避免"tasks 数组"抢过"包含它的外层对象"。"""
    out = []
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch not in '{[':
            i += 1
            continue
        open_ch, close_ch = ch, ('}' if ch == '{' else ']')
        depth = 0
        in_str = False
        esc = False
        j = i
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '{' or c == '[':
                    depth += 1
                elif c == '}' or c == ']':
                    depth -= 1
                    if depth == 0:
                        break
            j += 1
        if j < n:
            out.append((i, text[i:j + 1]))
            i = j + 1
        else:
            out.append((i, text[i:]))  # 未闭合残片，交给修复逻辑
            break
    return out


def _balanced_objects(text):
    return _balanced_spans(text, '{', '}')


def _repair_truncated(s):
    """抢救被 max_tokens 截断的 JSON：补引号、补括号、必要时丢半个键值对。

    先做「温和版」——只补上悬空的引号与闭合括号，尽量原样保留已有内容
    （这样 {"score":9 这类「尾部是完整数字」的截断不会被误删）；
    若温和版仍解析不了（结尾是半截的键/值），再退回「激进版」丢掉最后那个没写完的片段。
    """
    stack = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '{':
                stack.append('}')
            elif ch == '[':
                stack.append(']')
            elif ch in '}]':
                if stack and stack[-1] == ch:
                    stack.pop()
    closes = ''.join(reversed(stack))
    closed = s + ('"' if in_str else '')

    def _tidy(text):
        """反复清掉结尾紧贴闭符的空容器与悬空逗号：[{"a":1},{}] → [{"a":1}]。"""
        prev = None
        while prev != text:
            prev = text
            text = re.sub(r',\s*\{\s*\}\s*(?=[}\]])', '', text)
            text = re.sub(r'\[\s*\]\s*(?=[}\]])', '', text)
            text = re.sub(r',\s*([}\]])', r'\1', text)
        return text

    def _parses(text):
        try:
            json.loads(text)
            return True
        except ValueError:
            return False

    # 温和版：补悬空引号 + 去掉结尾多余逗号 + 补齐括号（尽量原样保留尾部完整值）
    gentle = re.sub(r',\s*$', '', closed.rstrip()) + closes
    if _parses(gentle):
        return gentle

    # 激进版：断口的半截键值对整个丢弃："k": 无值 / ,"k" 只写了键 / 值是没写完的关键字
    # （引号包住的值在上面已补闭合，属合法内容，不会被这条误删）
    t = re.sub(r'[,{]\s*"[^"]*"\s*(?::\s*(?:true|false|null|[A-Za-z_$][\w$]*)?)?\s*$',
               lambda m: m.group(0)[0], closed).rstrip()
    t = re.sub(r',\s*$', '', t)
    cleaned = _tidy(t + closes)
    if _parses(cleaned):
        return cleaned
    raw = t + closes
    return raw if _parses(raw) else cleaned


def _extract_json(text):
    """从 AI 输出中稳健提取 JSON：全文 → 代码块 → 平衡截取 → 截断修复，逐级尝试。"""
    if not text or not text.strip():
        raise ValueError("AI 输出为空")
    raw = text.strip()
    # tier1：整串（含去围栏）与代码块——代表"完整输出"，命中即采用
    whole = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
    tried = {whole}
    try:
        data = json.loads(whole)
        if isinstance(data, (dict, list)):
            return data
    except ValueError:
        pass
    for m in re.finditer(r"```(?:json)?\s*(.+?)```", raw, re.S):
        block = m.group(1).strip()
        if block in tried:
            continue
        tried.add(block)
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, (dict, list)):
            return data
    # tier2：正文中的最外层片段（原始 + 截断修复版）；同级多块时取
    # "字段/条目最多，同分取更靠后"的那个（模型通常先举例、后给最终答案）
    parsed = []
    for cand in _top_level_spans(raw):
        span = cand[1]
        for variant in (span, _repair_truncated(span)):
            if variant in tried:
                continue
            tried.add(variant)
            try:
                data = json.loads(variant)
            except ValueError:
                continue
            if isinstance(data, (dict, list)):
                parsed.append((len(data), len(parsed), data))
                break
    if parsed:
        return max(parsed, key=lambda x: (x[0], x[1]))[2]
    raise ValueError(f"AI 输出无法解析为 JSON: {raw[:200]}")


def _chat_json(messages, max_tokens=1200, temperature=0.2, json_mode=False, repair_tries=1):
    """chat + 宽容解析。解析失败时把坏输出回喂给模型自纠一次（多数畸形是围栏/前言/截断，
    一句话纠正就能恢复）。返回 (data|None, 最后一次原始文本)，由调用方决定兜底策略。"""
    convo = list(messages)
    last_text = ''
    for attempt in range(repair_tries + 1):
        text = chat(convo, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)
        last_text = text or last_text
        try:
            return _extract_json(text), last_text
        except ValueError:
            if attempt < repair_tries:
                convo = (list(messages)
                         + [{"role": "assistant", "content": (text or '')[:2000]},
                            {"role": "user", "content": "你上一次的输出不是有效的 JSON 对象。"
                             "请重新只输出一个完整、合法的 JSON 对象本身，"
                             "不要任何解释、前后缀或 markdown 代码块。"}])
    return None, last_text


EXTRACT_SYSTEM_PROMPT = (
    "你是政府采购公告结构化提取助手。从公告文本中提取以下字段，只输出一个 JSON 对象，"
    "不要输出任何其他文字或解释。字段："
    '{"title":"项目名称","purchaser":"采购单位/客户方","contact_name":"项目联系人/联系人姓名",'
    '"contact_phone":"联系电话/项目联系电话(纯数字或含区号)","address":"采购单位地址",'
    '"budget":"预算金额(纯数字，单位万元，无法确定填null)",'
    '"deadline":"报名/投标截止时间(YYYY-MM-DD，无则null)","summary":"60字以内业务摘要",'
    '"winner":"中标/成交供应商（单位）名称，仅中标公告、成交公告等结果类公告有此字段，其他公告填null",'
    '"region":"项目所在行政区划，根据采购单位地址/公告正文推断，格式为完整的省+市+县区'
    '(如"黑龙江省哈尔滨市依兰县"、"浙江省丽水市松阳县")，只能确定省市时填省市，无法确定填null"}。'
    "注意：公告末尾的'联系人及联系方式'区域中，'项目联系人'后面的姓名和'项目联系电话'后面的号码"
    "是重要字段，必须提取；中标/成交类公告中的'中标（成交）供应商名称'或'中标供应商'同样必须提取到 winner；"
    "无法确定的字段填 null。"
)


def _regex_fields(text, keys):
    """最后兜底：JSON 整体解析不了时，按 "key":"value" 逐字段正则抠出来。"""
    out = {}
    for k in keys:
        m = re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)"' % re.escape(k), text or '')
        if m:
            out[k] = m.group(1).replace('\\"', '"').replace('\\n', ' ')
            continue
        m = re.search(r'"%s"\s*:\s*(-?[\d.]+|true|false|null)' % re.escape(k), text or '')
        if m:
            v = m.group(1)
            if v in ('true', 'false'):
                out[k] = v == 'true'
            elif v != 'null':
                out[k] = v
    return out


def extract_lead(title, page_text, source_url, bid_type=""):
    """AI 抽取公告字段（招标类与中标/成交类均支持），返回 dict。
    容错链：response_format 强制 JSON → 宽容解析（围栏/前后缀/截断修复）→
    坏输出回喂模型自纠一次 → 逐字段正则兜底。全链路失败也不会抛断整轮采集。"""
    content = f"公告标题：{title}\n公告类型：{bid_type or '未标注'}\n公告来源：{source_url}\n公告正文：\n{page_text[:7000]}"
    data, raw = _chat_json(
        [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        max_tokens=1500,
        json_mode=True,
    )
    if not isinstance(data, dict):
        data = _regex_fields(
            raw, ('title', 'purchaser', 'contact_name', 'contact_phone', 'address',
                  'region', 'budget', 'deadline', 'summary', 'winner')
        )
    # 统一走 clean_text：公告正文常带 0x1E / NBSP / 零宽字符，
    # 只 strip() 会让它们跟着"采购单位""中标单位"一起入库。
    return {
        "title": clean_text(data.get("title") or title, collapse_space=True),
        "purchaser": clean_text(data.get("purchaser"), collapse_space=True),
        "contact_name": clean_text(data.get("contact_name"), collapse_space=True),
        "contact_phone": clean_text(data.get("contact_phone"), collapse_space=True),
        "address": clean_text(data.get("address"), collapse_space=True),
        "region": clean_text(data.get("region"), collapse_space=True),
        "budget": data.get("budget"),
        "deadline": data.get("deadline"),
        "summary": clean_text(data.get("summary")),
        "winner": clean_text(data.get("winner"), collapse_space=True),
    }


PLAN_SYSTEM_PROMPT = (
    "你是林业无人机业务 CRM 的销售助理。基于系统数据生成当日跟进方案，只输出一个 JSON 对象："
    '{"date":"YYYY-MM-DD","tasks":[{"type":"contact|followup|lead|opportunity",'
    '"title":"任务标题","content":"具体跟进建议(1-2句)","priority":"high|medium|low",'
    '"related":"关联的客户/线索/商机名称"}]}。'
    "要求：任务必须基于给出的真实数据，3-8 条，按优先级排序，不要编造不存在的对象。"
)


def generate_daily_plan():
    """AI 分析联系记录与项目数据，生成当日跟进方案（任务列表）。失败抛异常。"""
    from datetime import date, timedelta
    from app.models import Activity, FollowUp, Lead, Opportunity, Contact

    today = date.today()
    week_ago = today - timedelta(days=7)

    activities = Activity.query.order_by(Activity.activity_time.desc()).limit(20).all()
    act_lines = [
        f"- [{a.activity_time.date() if a.activity_time else '?'}] 客户:{a.customer.name if a.customer else '-'} "
        f"联系人:{a.contact.name if a.contact else '-'} 方式:{a.method} 内容:{a.content[:80]}"
        for a in activities
    ]

    followups = FollowUp.query.filter(FollowUp.actual_date.is_(None)).order_by(FollowUp.plan_date).all()
    fu_lines = [
        f"- 计划日:{f.plan_date.date() if f.plan_date else '?'} 客户:{f.customer.name if f.customer else '-'} "
        f"联系人:{f.contact.name if f.contact else '-'} 内容:{f.content[:60]}"
        for f in followups
    ]

    leads = Lead.query.filter(Lead.status.in_(['active', 'pool'])).order_by(Lead.deadline).all()
    lead_lines = [
        f"- {l.title[:50]} 截止:{l.deadline.date() if l.deadline else '无'} 匹配度:{l.match_level} "
        f"预算:{l.budget} 客户:{l.customer.name if l.customer else '未关联'}"
        for l in leads
    ]

    opps = Opportunity.query.all()
    opp_lines = [
        f"- {o.title[:50]} 阶段:{o.current_stage} 金额:{o.amount} 客户:{o.customer.name if o.customer else '-'} "
        f"赢率:{o.probability}%"
        for o in opps
    ]

    contacts = Contact.query.all()
    stale = [c for c in contacts if c.updated_at and (today - c.updated_at.date()).days >= 14]
    stale_lines = [f"- {c.name} ({c.customer.name if c.customer else '无客户'}) 最近更新:{c.updated_at.date()}" for c in stale]

    context = (
        f"今天日期：{today}\n"
        f"最近活动记录({len(act_lines)}条):\n" + "\n".join(act_lines) +
        f"\n待完成跟进计划({len(fu_lines)}条):\n" + "\n".join(fu_lines) +
        f"\n活跃线索({len(lead_lines)}条):\n" + "\n".join(lead_lines) +
        f"\n商机({len(opp_lines)}条):\n" + "\n".join(opp_lines) +
        f"\n超过14天未更新的联系人({len(stale_lines)}条):\n" + "\n".join(stale_lines)
    )
    data, raw = _chat_json(
        [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        max_tokens=2500,
        json_mode=True,
    )
    if data is None:
        raise ValueError(f"AI 输出无法解析为 JSON: {(raw or '')[:200]}")
    if isinstance(data, list):  # 模型直接吐了任务数组
        data = {"tasks": data}
    tasks = data.get("tasks") or []
    normalized = []
    for t in tasks:
        if isinstance(t, dict):
            normalized.append({
                "type": str(t.get("type") or "followup"),
                "title": str(t.get("title") or "跟进任务"),
                "content": str(t.get("content") or ""),
                "priority": str(t.get("priority") or "medium"),
                "related": str(t.get("related") or ""),
            })
    return {"date": str(data.get("date") or today), "tasks": normalized}
