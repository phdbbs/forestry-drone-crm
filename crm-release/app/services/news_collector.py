"""客户新闻 / 联系人动态信息采集。

来源：客户官网、配置的媒体/官网来源（含中国政府采购网公告），
按客户名称/联系人姓名匹配，支持同一新闻同时关联客户与联系人。
每次采集任务写入 CrawlLog。
"""
import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

from app import db
from app.models import Customer, Contact, CustomerNews, ContactNews, CrawlLog, SystemConfig

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get_news_sources():
    """读取新闻采集来源配置，默认中国政府采购网中央/地方公告。"""
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    sources = []
    raw = configs.get('news_sources', '')
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for s in parsed:
                    if isinstance(s, dict) and s.get('url'):
                        sources.append({
                            "name": str(s.get('name') or s['url']),
                            "url": str(s['url']).strip(),
                            "enabled": bool(s.get('enabled', True)),
                        })
        except (json.JSONDecodeError, TypeError):
            for u in str(raw).replace('，', ',').split(','):
                u = u.strip()
                if u:
                    sources.append({"name": u, "url": u, "enabled": True})
    if not sources:
        sources = [
            {"name": "中国政府采购网-中央公告", "url": "https://www.ccgp.gov.cn/cggg/zygg/", "enabled": True},
            {"name": "中国政府采购网-地方公告", "url": "https://www.ccgp.gov.cn/cggg/dfgg/", "enabled": True},
        ]
    return sources


def _fetch(url, session, timeout=20):
    resp = session.get(url, timeout=timeout)
    resp.encoding = resp.apparent_encoding or 'utf-8'
    return resp


def _page_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    return re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))


def _ccgp_items(html, base_url):
    """解析 ccgp 公告列表 li。"""
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    for li in soup.find_all('li'):
        a = li.find('a')
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a.get('href', '')
        if len(title) < 6 or not href:
            continue
        text = li.get_text(' ', strip=True)
        m = re.search(r'发布时间[:：]\s*(\d{4}-\d{2}-\d{2})', text)
        items.append({
            "title": title,
            "url": urljoin(base_url, href),
            "date": m.group(1) if m else None,
        })
    return items


def _generic_items(html, base_url):
    """通用列表页：提取 a 链接作为候选新闻。"""
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    seen = set()
    for a in soup.find_all('a'):
        title = a.get_text(strip=True)
        href = a.get('href', '')
        if len(title) < 8 or not href or href.startswith('javascript'):
            continue
        url = urljoin(base_url, href)
        if url in seen or not url.startswith('http'):
            continue
        seen.add(url)
        # 忽略明显非新闻链接
        if re.search(r'\.(jpg|jpeg|png|gif|pdf|zip|js|css)(\?|$)', url, re.I):
            continue
        items.append({"title": title, "url": url, "date": None})
    return items[:50]


def _parse_date(text):
    m = re.search(r'20\d{2}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}', text)
    if not m:
        return None
    s = m.group().replace('年', '-').replace('月', '-').replace('/', '-')
    s = re.sub(r'\s+', '', s)
    try:
        return datetime.strptime(s[:10], '%Y-%m-%d')
    except ValueError:
        return None


def _summary_with(text, keyword, limit=200):
    """提取包含关键字的句子作为摘要。"""
    idx = text.find(keyword)
    if idx >= 0:
        return text[max(0, idx - 50): idx + 120].strip()[:limit]
    return text[:limit]


def _sources_for(customer=None, contact=None):
    """组装本次采集来源：配置源 + 客户官网。"""
    sources = [s for s in get_news_sources() if s.get('enabled')]
    if customer and customer.website:
        sources.append({"name": f"{customer.name}官网", "url": customer.website, "enabled": True})
    elif contact and contact.customer and contact.customer.website:
        sources.append({"name": f"{contact.customer.name}官网", "url": contact.customer.website, "enabled": True})
    return sources


def collect_customer_news(customer_id):
    """采集单个客户的新闻（含官网与媒体源），并同步识别该客户下的联系人动态。"""
    customer = Customer.query.get_or_404(customer_id)
    log = CrawlLog(task_type='客户新闻', sources='', status='success', items_count=0, error_count=0,
                   started_at=datetime.now())
    db.session.add(log)
    errors = []
    count = 0
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get('https://www.ccgp.gov.cn/', timeout=15)
    except Exception:
        pass
    names = [customer.name, customer.short_name] if customer.short_name else [customer.name]
    sources = _sources_for(customer=customer)
    log.sources = '; '.join(s["name"] for s in sources)
    try:
        for source in sources:
            try:
                resp = _fetch(source['url'], session)
                html = resp.text
                items = _ccgp_items(html, source['url']) if 'ccgp.gov.cn' in source['url'] else _generic_items(html, source['url'])
                for item in items:
                    if any(n and n in item['title'] for n in names):
                        if CustomerNews.query.filter_by(url=item['url']).first():
                            continue
                        try:
                            detail = _fetch(item['url'], session)
                            text = _page_text(detail.text)
                            if not any(n and n in text for n in names):
                                continue
                            publish = _parse_date(text) or (datetime.strptime(item['date'], '%Y-%m-%d') if item['date'] else None)
                            news = CustomerNews(
                                customer_id=customer.id, title=item['title'][:500],
                                content=text[:4000], url=item['url'],
                                source_name=source['name'], change_type='news',
                                publish_date=publish, event_time=publish, crawled_at=datetime.now(),
                            )
                            db.session.add(news)
                            db.session.flush()
                            count += 1
                            _sync_contact_news_from_text(customer, text, item['title'], item['url'], source['name'], publish)
                        except Exception as e:
                            errors.append(f"[{source['name']}] {item['title'][:20]}: {str(e)[:80]}")
            except Exception as e:
                errors.append(f"[{source['name']}] 列表页失败: {str(e)[:100]}")
            db.session.commit()
    except Exception as e:
        errors.append(str(e)[:150])
        db.session.rollback()
    log.status = 'failed' if len(sources) and len(errors) >= len(sources) else ('partial' if errors else 'success')
    log.items_count = count
    log.error_count = len(errors)
    log.message = f"客户[{customer.name}] 新增 {count} 条新闻" + (f"，{len(errors)} 个异常" if errors else "")
    log.finished_at = datetime.now()
    db.session.commit()
    return {"count": count, "errors": errors, "message": log.message}


def _sync_contact_news_from_text(customer, text, title, url, source_name, publish):
    """新闻正文匹配该客户下联系人姓名，同时写入联系人动态。"""
    for contact in customer.contacts:
        if not contact.name or contact.name in ('暂无', '未知'):
            continue
        if contact.name in text:
            if ContactNews.query.filter_by(contact_id=contact.id, url=url).first():
                continue
            cn = ContactNews(
                contact_id=contact.id, customer_id=customer.id, title=title[:500],
                content=text[:4000], url=url, source_name=source_name,
                change_type='news', publish_date=publish, event_time=publish,
                summary=_summary_with(text, contact.name),
                crawled_at=datetime.now(),
            )
            db.session.add(cn)


def collect_contact_news(contact_id):
    """采集单个联系人的动态信息（官网+媒体源按姓名匹配）。"""
    contact = Contact.query.get_or_404(contact_id)
    log = CrawlLog(task_type='联系人动态', sources='', status='success', items_count=0, error_count=0,
                   started_at=datetime.now())
    db.session.add(log)
    errors = []
    count = 0
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get('https://www.ccgp.gov.cn/', timeout=15)
    except Exception:
        pass
    sources = _sources_for(contact=contact)
    log.sources = '; '.join(s["name"] for s in sources)
    try:
        for source in sources:
            try:
                resp = _fetch(source['url'], session)
                items = _ccgp_items(resp.text, source['url']) if 'ccgp.gov.cn' in source['url'] else _generic_items(resp.text, source['url'])
                for item in items:
                    try:
                        detail = _fetch(item['url'], session)
                        text = _page_text(detail.text)
                        if contact.name not in text:
                            continue
                        if ContactNews.query.filter_by(contact_id=contact.id, url=item['url']).first():
                            continue
                        publish = _parse_date(text) or (datetime.strptime(item['date'], '%Y-%m-%d') if item['date'] else None)
                        cn = ContactNews(
                            contact_id=contact.id, customer_id=contact.customer_id,
                            title=item['title'][:500], content=text[:4000], url=item['url'],
                            source_name=source['name'], change_type='news',
                            publish_date=publish, event_time=publish,
                            summary=_summary_with(text, contact.name),
                            crawled_at=datetime.now(),
                        )
                        db.session.add(cn)
                        count += 1
                    except Exception as e:
                        errors.append(f"[{source['name']}] {item['title'][:20]}: {str(e)[:80]}")
            except Exception as e:
                errors.append(f"[{source['name']}] 列表页失败: {str(e)[:100]}")
            db.session.commit()
    except Exception as e:
        errors.append(str(e)[:150])
        db.session.rollback()
    log.status = 'failed' if len(sources) and len(errors) >= len(sources) else ('partial' if errors else 'success')
    log.items_count = count
    log.error_count = len(errors)
    log.message = f"联系人[{contact.name}] 新增 {count} 条动态" + (f"，{len(errors)} 个异常" if errors else "")
    log.finished_at = datetime.now()
    db.session.commit()
    return {"count": count, "errors": errors, "message": log.message}


def collect_all(kind='all'):
    """批量采集：all / customer / contact。"""
    customers = Customer.query.filter_by(is_archived=False).all()
    contacts = Contact.query.all()
    total = 0
    errors = []
    if kind in ('all', 'customer'):
        for c in customers:
            try:
                r = collect_customer_news(c.id)
                total += r['count']
                errors += r['errors']
            except Exception as e:
                errors.append(f"[{c.name}] {str(e)[:100]}")
    if kind in ('all', 'contact'):
        for ct in contacts:
            try:
                r = collect_contact_news(ct.id)
                total += r['count']
                errors += r['errors']
            except Exception as e:
                errors.append(f"[{ct.name}] {str(e)[:100]}")
    return {"count": total, "errors": errors}
