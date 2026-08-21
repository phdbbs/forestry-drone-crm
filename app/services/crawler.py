import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from app import db
from app.models import Lead, SystemConfig
from app.services.matcher import match_lead
from app.services.ai_client import extract_lead
import re, time, json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://www.ccgp.gov.cn/",
}

# Delay between keyword requests (seconds) to avoid triggering rate limits
REQUEST_DELAY = 3


def get_crawl_keywords():
    """Get keywords from system config"""
    from app.models import SystemConfig
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    keywords = []
    # First try crawl_targets JSON config
    targets = configs.get('crawl_targets', '')
    if targets:
        try:
            for t in json.loads(targets):
                if t.get('enabled'):
                    for kw in (t.get('keywords') or '').split(','):
                        kw = kw.strip()
                        if kw and kw not in keywords:
                            keywords.append(kw)
        except (json.JSONDecodeError, TypeError):
            pass
    # Also read from keywords config (comma-separated)
    kw_config = configs.get('keywords', '')
    if kw_config:
        for kw in kw_config.split(','):
            kw = kw.strip()
            if kw and kw not in keywords:
                keywords.append(kw)
    return keywords or ["无人机", "林业", "病虫害", "巡检"]


def extract_budget(text):
    for p in [r"预算[金额价格]*[:：]\s*([\d,.]+)\s*[万]?元", r"项目预算[:：]\s*([\d,.]+)", r"总预算[:：]\s*([\d,.]+)"]:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return ""


def extract_region(text):
    provinces = ["北京", "上海", "重庆", "天津", "河北", "山西", "辽宁", "吉林",
                 "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
                 "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
                 "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆"]
    for p in provinces:
        if p in text:
            return p
    return ""


def extract_deadline(text):
    m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", text)
    if m:
        try:
            s = m.group(1).replace("年", "-").replace("月", "-").replace("/", "-")
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            pass
    return None


def detect_antibot(html_text):
    """Detect anti-bot/rate-limit pages. Returns reason string or None."""
    if "频繁访问" in html_text or "访问过于频繁" in html_text:
        return "访问过于频繁，被网站限流（请稍后重试或减少关键词数量）"
    if "验证码" in html_text or "captcha" in html_text.lower():
        return "触发验证码，需人工介入"
    if "请开启JavaScript" in html_text:
        return "网站要求启用JavaScript"
    if len(html_text) < 500 and ("error" in html_text.lower() or "错误" in html_text):
        return "网站返回错误页面"
    return None


def get_crawl_config():
    """读取采集配置：多来源 URL、首次回溯天数、抽取上限、关键词过滤开关、上次采集时间点。"""
    from app.models import SystemConfig
    configs = {c.key: c.value for c in SystemConfig.query.all()}

    sources = []
    raw_sources = configs.get('crawl_sources', '')
    if raw_sources:
        try:
            parsed = json.loads(raw_sources)
            if isinstance(parsed, list):
                for s in parsed:
                    if isinstance(s, dict) and s.get('url'):
                        sources.append({
                            "name": str(s.get('name') or s['url']),
                            "url": str(s['url']).strip(),
                            "enabled": bool(s.get('enabled', True)),
                        })
        except (json.JSONDecodeError, TypeError):
            for u in str(raw_sources).replace('，', ',').split(','):
                u = u.strip()
                if u:
                    sources.append({"name": u, "url": u, "enabled": True})
    if not sources:
        sources = [
            {"name": "中国政府采购网-中央公告", "url": "https://www.ccgp.gov.cn/cggg/zygg/", "enabled": True},
            {"name": "中国政府采购网-地方公告", "url": "https://www.ccgp.gov.cn/cggg/dfgg/", "enabled": True},
        ]

    try:
        days = max(1, min(30, int(configs.get('crawl_days', '7') or 7)))
    except (TypeError, ValueError):
        days = 7
    try:
        limit = max(1, min(50, int(configs.get('crawl_limit', '5') or 5)))
    except (TypeError, ValueError):
        limit = 5
    keyword_filter = configs.get('crawl_keyword_filter', '1') != '0'
    last_crawl_at = None
    raw_at = configs.get('last_crawl_at', '')
    if raw_at:
        try:
            last_crawl_at = datetime.strptime(str(raw_at)[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            last_crawl_at = None
    return {
        "sources": sources, "days": days, "limit": limit,
        "keyword_filter": keyword_filter, "last_crawl_at": last_crawl_at,
    }


SKIP_TYPES = ("中标", "成交", "废标", "终止", "更正", "结果", "流标")

# 政府采购网搜索接口
SEARCH_BASE = "https://search.ccgp.gov.cn/bxsearch"


def _build_search_url(kw, start_date, end_date, page_index=1, bid_type=0):
    """构建政府采购网搜索URL。日期格式：2026:08:19（接口要求冒号分隔）。"""
    from urllib.parse import quote
    start = start_date.strftime("%Y:%m:%d")
    end = end_date.strftime("%Y:%m:%d")
    return (
        f"{SEARCH_BASE}?searchtype=1&page_index={page_index}"
        f"&bidSort=0&bidType={bid_type}&dbselect=bidx"
        f"&kw={quote(kw)}&start_time={start}&end_time={end}"
        f"&timeType=1&displayZone=&zoneId=&pppStatus=0&agentName="
    )


def parse_search_item(li):
    """解析搜索结果 li（ul.vT-srch-result-list-bid 下的项），返回 dict 或 None。

    每条结构：<a>标题</a> <p>摘要</p> <span>日期|采购人|代理  公告类型|地区</span>
    """
    a = li.find("a")
    if not a:
        return None
    title = a.get_text(strip=True)
    href = a.get("href", "")
    if not title or len(title) < 5 or not href:
        return None
    p = li.find("p")
    summary = p.get_text(" ", strip=True) if p else ""
    span = li.find("span")
    span_text = span.get_text(" ", strip=True) if span else ""
    # 日期：2026.08.21 23:46:51
    m_date = re.search(r"(\d{4}\.\d{2}\.\d{2})", span_text)
    dt = None
    if m_date:
        try:
            dt = datetime.strptime(m_date.group(1), "%Y.%m.%d")
        except ValueError:
            dt = None
    # 采购人
    m_buyer = re.search(r"采购人[：:]\s*(.*?)(?=\s*\|)", span_text)
    purchaser = m_buyer.group(1).strip() if m_buyer else ""
    # 公告类型（<strong> 标签）
    atype = ""
    strong = span.find("strong")
    if strong:
        atype = strong.get_text(strip=True)
    if any(k in atype for k in SKIP_TYPES):
        return None
    # 地区（公告类型后的 | 地区）
    parts = [s.strip() for s in span_text.split("|")]
    region = parts[2] if len(parts) >= 3 else ""
    return {
        "title": title,
        "url": href,
        "dt": dt,
        "date": m_date.group(1) if m_date else None,
        "purchaser": purchaser,
        "type": atype,
        "region": region,
        "summary": summary,
    }


def fetch_search_results(kw, start_date, end_date, session, max_pages=2):
    """按关键词搜索政府采购网，翻页采集。返回 (items, error)。"""
    items = []
    for page in range(1, max_pages + 1):
        url = _build_search_url(kw, start_date, end_date, page_index=page)
        try:
            resp = session.get(url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                return items, f"HTTP {resp.status_code}"
            # 搜索接口反爬检测：只检测"频繁访问"（正常页面注释中含"验证码"字样，不能用作判据）
            if "频繁访问" in resp.text or "访问过于频繁" in resp.text:
                return items, "访问过于频繁，被网站限流（请稍后重试）"
            soup = BeautifulSoup(resp.text, "html.parser")
            ul = soup.find("ul", class_="vT-srch-result-list-bid")
            if not ul:
                return items, ""  # 无结果或结构变化，不算错误
            page_items = []
            for li in ul.find_all("li"):
                item = parse_search_item(li)
                if item:
                    page_items.append(item)
            if not page_items:
                break
            items.extend(page_items)
            time.sleep(REQUEST_DELAY)  # 翻页间延迟，避免反爬
        except Exception as e:
            return items, f"请求异常: {str(e)[:80]}"
    return items, ""


def fetch_detail_text(url, session):
    """抓取公告详情页并清洗为纯文本。"""
    resp = session.get(url, timeout=20)
    resp.encoding = resp.apparent_encoding or "utf-8"
    if resp.status_code != 200:
        raise RuntimeError(f"详情页 HTTP {resp.status_code}")
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return text[:8000]


def extract_contact_rules(text):
    """规则兜底：从公告文本提取 联系人/电话/地址/采购单位（AI 未抽到时使用）。"""
    contact = phone = address = purchaser = ""
    m = re.search(r"项目联系人\s*([\u4e00-\u9fa5·]{2,8})\s*项目联系电话\s*([0-9\-—()（）\s]{5,30})", text)
    if m:
        contact, phone = m.group(1), m.group(2)
    if not contact:
        m = re.search(r"联系人[:：]?\s*([\u4e00-\u9fa5·]{2,8})\s*电话[:：]?\s*([0-9\-—()（）\s]{5,30})", text)
        if m:
            contact, phone = m.group(1), m.group(2)
    if not contact:
        m = re.search(r"项目联系人[:：]\s*([\u4e00-\u9fa5·]{2,8})", text)
        if m:
            contact = m.group(1)
    if not phone:
        m = re.search(r"项目联系电话[:：]?\s*([0-9\-—()（）\s]{5,30})", text)
        if m:
            phone = m.group(1)
    m = re.search(r"采购单位地址[:：]?\s*([^\s，。；,]{4,60})", text)
    if m:
        address = m.group(1)
    m = re.search(r"采购单位[:：]?\s*([\u4e00-\u9fa5（）()]{4,50}?)(?=\s|$)", text)
    if m:
        purchaser = m.group(1)
    return {
        "contact_name": re.sub(r"\s+", "", contact),
        "contact_phone": re.sub(r"[^\d-]", "", phone),
        "address": address,
        "purchaser": purchaser,
    }


def _update_status(**kw):
    _crawl_status.update(kw)


def run_crawl(app=None):
    """搜索接口采集：按关键词+时间范围搜索 → 详情页 → AI 抽取 → 生成线索。
    返回 (count, errors)。"""
    cfg = get_crawl_config()
    errors = []
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.ccgp.gov.cn/", timeout=15)
        time.sleep(2)  # 主页与搜索间留间隔，降低反爬触发概率
    except Exception:
        pass

    # 计算搜索时间范围：增量采集从检查点开始，首次回溯最近 N 天
    now = datetime.now()
    checkpoint = cfg["last_crawl_at"]
    if checkpoint:
        start_date = checkpoint
    else:
        start_date = now - timedelta(days=cfg["days"])
    end_date = now

    # 按关键词搜索政府采购网
    keywords = get_crawl_keywords()
    _update_status(phase="关键词搜索", total=len(keywords), current=",".join(keywords))
    candidates = []
    seen_urls = set()
    for kw in keywords:
        _update_status(current=f"搜索关键词: {kw}")
        try:
            results, err = fetch_search_results(kw, start_date, end_date, session)
            if err:
                errors.append(f"[关键词:{kw}] {err}")
            for it in results:
                if it["url"] not in seen_urls:
                    seen_urls.add(it["url"])
                    it["source_name"] = f"搜索:{kw}"
                    candidates.append(it)
            if not results and not err:
                errors.append(f"[关键词:{kw}] 搜索结果为0条")
        except Exception as e:
            errors.append(f"[关键词:{kw}] 搜索失败: {str(e)[:100]}")
        time.sleep(REQUEST_DELAY)

    # 按时间倒序，取 limit 条进入 AI 抽取
    candidates = [it for it in candidates if it.get("dt")]
    candidates.sort(key=lambda it: it["dt"], reverse=True)
    filtered = candidates[: cfg["limit"]]

    _update_status(phase="AI抽取", total=len(filtered), count=0, errors=errors)
    if checkpoint:
        _update_status(message=f"增量采集：从 {checkpoint.strftime('%Y-%m-%d %H:%M')} 起，搜索到 {len(candidates)} 条候选")
        _crawl_status["from_at"] = checkpoint.strftime("%Y-%m-%d %H:%M")
    count = 0
    for idx, item in enumerate(filtered, 1):
        _update_status(progress=idx, current=item["title"][:60])
        try:
            if Lead.query.filter_by(source_url=item["url"]).first():
                continue
            page_text = fetch_detail_text(item["url"], session)
            ai = extract_lead(item["title"], page_text, item["url"])
            rules = extract_contact_rules(page_text)
            for f in ("contact_name", "contact_phone", "address", "purchaser"):
                if not ai.get(f) and rules.get(f):
                    ai[f] = rules[f]
            budget = ai["budget"]
            if budget is None:
                budget = extract_budget(page_text)
            deadline = ai["deadline"]
            if deadline:
                try:
                    deadline = datetime.strptime(str(deadline)[:10], "%Y-%m-%d")
                except ValueError:
                    deadline = None
            region = item["region"] or extract_region(page_text)
            service = "；".join(
                f"{k}: {v}" for k, v in [
                    ("客户方", ai["purchaser"]), ("联系人", ai["contact_name"]),
                    ("联系方式", ai["contact_phone"]), ("地址", ai["address"]),
                    ("预算", budget), ("摘要", ai["summary"]),
                ] if v
            )
            lead = Lead(
                title=ai["title"][:500],
                budget=str(budget) if budget else "",
                deadline=deadline,
                region=region,
                purchaser=ai["purchaser"],
                contact_name=(ai["contact_name"] or "")[:100],
                contact_phone=(ai["contact_phone"] or "")[:100],
                address=(ai["address"] or "")[:300],
                service_content=service,
                source_url=item["url"],
                source_platform=item.get("source_name", "中国政府采购网"),
                status="active",
            )
            match_lead(lead)
            db.session.add(lead)
            db.session.commit()
            count += 1
            _update_status(count=count)
        except Exception as e:
            errors.append(f"[{item['title'][:30]}] {str(e)[:120]}")
            db.session.rollback()
        time.sleep(1)

    _update_status(phase="完成", count=count, errors=errors)
    # 记录本次采集时间点，供下次增量采集使用（搜索成功时推进）
    if candidates:
        ts = now.strftime("%Y-%m-%d %H:%M")
        store = SystemConfig.query.filter_by(key='last_crawl_at').first()
        if store:
            store.value = ts
        else:
            store = SystemConfig(key='last_crawl_at', value=ts, description='上次采集时间点(增量采集)')
            db.session.add(store)
        db.session.commit()
    return count, errors


_crawl_status = {
    "running": False, "phase": "", "progress": 0, "total": 0,
    "current": "", "count": 0, "errors": [], "message": "",
    "started_at": None, "finished_at": None,
}


def start_crawl_background(app):
    """后台线程执行采集，避免 AI 抽取长时间阻塞请求。"""
    import threading
    if _crawl_status["running"]:
        return False
    _crawl_status.update({
        "running": True, "phase": "准备中", "progress": 0, "total": 0,
        "current": "", "count": 0, "errors": [], "message": "",
        "from_at": "",
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": None,
    })
    threading.Thread(target=_crawl_worker, args=(app,), daemon=True).start()
    return True


def _crawl_worker(app):
    try:
        with app.app_context():
            count, errors = run_crawl(app)
            extra = f"（自 {_crawl_status.get('from_at', '首次/回溯')} 起）" if _crawl_status.get("from_at") else ""
            _crawl_status.update({
                "message": f"采集完成，新增 {count} 条线索{extra}" + (f"（{len(errors)} 个异常）" if errors else ""),
            })
    except Exception as e:
        _crawl_status.update({"message": f"采集失败: {str(e)[:200]}"})
    finally:
        _crawl_status.update({"running": False, "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


def get_crawl_status():
    return dict(_crawl_status)
