import requests
from bs4 import BeautifulSoup
from datetime import datetime
from app import db
from app.models import Lead
from app.services.matcher import match_lead
import re, time, json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "http://www.ccgp.gov.cn/",
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


def parse_search_results(html_text):
    """Parse search result HTML and extract lead data."""
    soup = BeautifulSoup(html_text, "html.parser")
    results = []

    # Try multiple CSS selectors (site structure may vary across versions)
    selectors = [
        ".vT-srch-result li",
        "ul.vT-srch-result li",
        ".vT_z_result_container li",
        ".search_results li",
        "div.vT-srch-result-list li",
    ]
    items = []
    for sel in selectors:
        items = soup.select(sel)
        if items:
            break

    for item in items:
        a = item.select_one("a")
        if not a:
            continue
        title = a.get_text(strip=True)
        url = a.get("href", "")
        if not title or len(title) < 5:
            continue
        if url and not url.startswith("http"):
            url = "http://search.ccgp.gov.cn" + url

        # Extract additional info from the full list item text
        item_text = item.get_text()
        lead = Lead(
            title=title,
            budget=extract_budget(item_text),
            deadline=extract_deadline(item_text),
            region=extract_region(item_text),
            purchaser="",
            service_content=title,
            source_url=url,
            source_platform="中国政府采购网",
        )
        results.append(lead)

    return results


def crawl_gov_ccgp():
    """Crawl the government procurement website.
    Returns (leads_list, errors_list) tuple.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    keywords = get_crawl_keywords()
    all_results = []
    errors = []

    # Warm up session by visiting main page (establishes cookies)
    try:
        session.get("http://www.ccgp.gov.cn/", timeout=10)
        time.sleep(1)
    except Exception:
        pass  # Non-critical

    for i, keyword in enumerate(keywords):
        if i > 0:
            time.sleep(REQUEST_DELAY)
        try:
            params = {
                "fields": "", "kw": keyword, "page_index": 1,
                "bidSort": 0, "buyerName": "", "projectId": "",
                "pinMu": 0, "bidType": 0, "dbselect": "bidx",
                "kw_type": 1, "start_time": "", "end_time": "",
                "timeType": 0, "displayZone": "", "zoneId": "",
                "pppStatus": 0, "agentName": "",
            }
            resp = session.get(
                "http://search.ccgp.gov.cn/bxsearch",
                params=params, timeout=15
            )
            resp.encoding = resp.apparent_encoding or "utf-8"

            if resp.status_code != 200:
                errors.append(f"[{keyword}] HTTP {resp.status_code}")
                continue

            # Check for anti-bot page
            block_reason = detect_antibot(resp.text)
            if block_reason:
                errors.append(f"[{keyword}] {block_reason}")
                time.sleep(REQUEST_DELAY * 2)
                continue

            leads = parse_search_results(resp.text)
            all_results.extend(leads)

        except requests.exceptions.Timeout:
            errors.append(f"[{keyword}] 请求超时(15s)")
        except requests.exceptions.ConnectionError:
            errors.append(f"[{keyword}] 网络连接失败")
        except Exception as e:
            errors.append(f"[{keyword}] {str(e)[:120]}")

    return all_results, errors


def run_crawl(app=None):
    """Execute crawl and save new leads to database.
    Returns (count, errors) tuple.
    """
    leads, errors = crawl_gov_ccgp()
    count = 0
    for lead in leads:
        existing = Lead.query.filter_by(title=lead.title, source_url=lead.source_url).first()
        if not existing:
            match_lead(lead)
            db.session.add(lead)
            count += 1
    db.session.commit()
    return count, errors
