import requests
from bs4 import BeautifulSoup
from datetime import datetime
from app import db
from app.models import Lead
from app.services.matcher import match_lead
import re, time, json

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
        except:
            pass
    # Also read from keywords config (comma-separated)
    kw_config = configs.get('keywords', '')
    if kw_config:
        for kw in kw_config.split(','):
            kw = kw.strip()
            if kw and kw not in keywords:
                keywords.append(kw)
    return keywords or ["无人机", "林业", "病虫害", "巡检"]

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def extract_budget(text):
    for p in [r"预算[金额价格]*[:：]\s*([\d,.]+)\s*[万]?元", r"项目预算[:：]\s*([\d,.]+)", r"总预算[:：]\s*([\d,.]+)"]:
        m = re.search(p, text)
        if m: return m.group(1)
    return ""

def extract_region(text):
    for p in ["北京","上海","重庆","天津","河北","山西","辽宁","吉林","黑龙江","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","海南","四川","贵州","云南","陕西","甘肃","青海","内蒙古","广西","西藏","宁夏","新疆"]:
        if p in text: return p
    return ""

def extract_deadline(text):
    m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", text)
    if m:
        try:
            s = m.group(1).replace("年","-").replace("月","-").replace("/","-")
            return datetime.strptime(s, "%Y-%m-%d")
        except: pass
    return None

def crawl_gov_ccgp():
    results = []
    keywords = get_crawl_keywords()
    for keyword in keywords:
        try:
            params = {"fields":"","kw":keyword,"page_index":1,"bidSort":0,"buyerName":"","projectId":"","pinMu":0,"bidType":0,"dbselect":"bidx","kw_type":1,"start_time":"","end_time":"","timeType":0,"displayZone":"","zoneId":"","pppStatus":0,"agentName":""}
            resp = requests.get("http://search.ccgp.gov.cn/bxsearch", params=params, headers=HEADERS, timeout=15)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for item in soup.select(".vT-srch-result li"):
                    a = item.select_one("a")
                    if not a: continue
                    title = a.get_text(strip=True)
                    url = a.get("href","")
                    if not title or len(title) < 5: continue
                    if not url.startswith('http'): url = "http://search.ccgp.gov.cn" + url
                    lead = Lead(title=title, budget=extract_budget(title), deadline=extract_deadline(title), region=extract_region(title), purchaser="", service_content=title, source_url=url, source_platform="中国政府采购网")
                    results.append(lead)
            time.sleep(2)
        except Exception as e:
            print(f"Crawl error: {e}")
    return results

def run_crawl(app=None):
    leads = crawl_gov_ccgp()
    count = 0
    for lead in leads:
        if not Lead.query.filter_by(title=lead.title, source_url=lead.source_url).first():
            match_lead(lead)
            db.session.add(lead)
            count += 1
    db.session.commit()
    return count
