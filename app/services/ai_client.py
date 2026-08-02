"""AI 客户端：调用 OpenAI 兼容接口（本地 qwen3-14b-mlx），用于招标信息抽取与每日跟进分析。"""
import json
import re
import threading
import time
import requests
from app import db
from app.models import SystemConfig

_ai_lock = threading.Lock()


def get_ai_config():
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    return {
        "endpoint": (configs.get("ai_api_endpoint") or "http://127.0.0.1:1234/v1").rstrip("/"),
        "api_key": configs.get("ai_api_key") or "",
        "model": configs.get("ai_model") or "qwen3-14b-mlx",
    }


def chat(messages, max_tokens=1200, temperature=0.2, timeout=240, retries=2):
    """调用 AI 对话接口，返回 assistant content 文本。
    本地模型偶发崩溃：串行执行 + 失败自动重试（间隔 15 秒）。
    """
    cfg = get_ai_config()
    headers = {"Content-Type": "application/json"}
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    with _ai_lock:  # 串行调用，避免本地模型并发崩溃
        for attempt in range(retries + 1):
            try:
                resp = requests.post(
                    cfg["endpoint"] + "/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
            except Exception as e:
                if attempt < retries:
                    time.sleep(15)
                    continue
                raise RuntimeError(f"AI 请求异常: {e}")
            if resp.status_code == 200:
                data = resp.json()
                try:
                    return data["choices"][0]["message"]["content"] or ""
                except (KeyError, IndexError):
                    raise RuntimeError(f"AI 响应格式异常: {str(data)[:200]}")
            if attempt < retries:
                time.sleep(15)
                continue
            raise RuntimeError(f"AI 接口返回 HTTP {resp.status_code}: {resp.text[:200]}")


def _extract_json(text):
    """从 AI 输出中稳健提取 JSON 对象。"""
    if not text:
        raise ValueError("AI 输出为空")
    text = text.strip()
    # 去掉 markdown 代码围栏
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip()).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group())
        raise ValueError(f"AI 输出无法解析为 JSON: {text[:200]}")


EXTRACT_SYSTEM_PROMPT = (
    "你是招标信息结构化提取助手。从政府采购公告文本中提取以下字段，只输出一个 JSON 对象，"
    "不要输出任何其他文字或解释。字段："
    '{"title":"项目名称","purchaser":"采购单位/客户方","contact_name":"项目联系人/联系人姓名",'
    '"contact_phone":"联系电话/项目联系电话(纯数字或含区号)","address":"采购单位地址",'
    '"budget":"预算金额(纯数字，单位万元，无法确定填null)",'
    '"deadline":"报名/投标截止时间(YYYY-MM-DD，无则null)","summary":"60字以内业务摘要"}。'
    "注意：公告末尾的'联系人及联系方式'区域中，'项目联系人'后面的姓名和'项目联系电话'后面的号码"
    "是重要字段，必须提取；无法确定的字段填 null。"
)


def extract_lead(title, page_text, source_url):
    """AI 抽取招标公告字段，返回 dict。"""
    content = f"公告标题：{title}\n公告来源：{source_url}\n公告正文：\n{page_text[:7000]}"
    text = chat(
        [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        max_tokens=1200,
    )
    data = _extract_json(text)
    return {
        "title": str(data.get("title") or title).strip(),
        "purchaser": (data.get("purchaser") or "").strip(),
        "contact_name": (data.get("contact_name") or "").strip(),
        "contact_phone": (data.get("contact_phone") or "").strip(),
        "address": (data.get("address") or "").strip(),
        "budget": data.get("budget"),
        "deadline": data.get("deadline"),
        "summary": (data.get("summary") or "").strip(),
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
    text = chat(
        [
            {"role": "system", "content": PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        max_tokens=2000,
    )
    data = _extract_json(text)
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
