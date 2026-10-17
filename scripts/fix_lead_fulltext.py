"""修复线索公告全文：编码解错的乱码重抓，缺正文的按需补齐，被旧上限截断的补长。

用法（在 /Users/wl/M4/CRM 下）：
    .venv/bin/python scripts/fix_lead_fulltext.py                     # 只报告
    .venv/bin/python scripts/fix_lead_fulltext.py --apply             # 修乱码
    .venv/bin/python scripts/fix_lead_fulltext.py --apply --truncated  # 重抓截断的
    .venv/bin/python scripts/fix_lead_fulltext.py --apply --missing    # 乱码 + 无正文都补

背景：netutil 早先按 chardet 猜编码，把 ccgp 的 UTF-8 中文页猜成 ptcp154 西里尔编码，
存进库的正文整篇是 «д»Ӣдј‘…»；另一批 8-9 月的存量根本没抓过详情页。
乱码那几条除了正文，采购方/联系人也是从乱码里抽的（多数干脆是空），所以顺手用
规则路径把空字段填上——只填空，已有值一律不动。
采集旧上限是 8000 字，整好卡在这个长度的行一定是被砍过尾部的，现在上限已放到
FULL_TEXT_LIMIT，按老写法长度精确匹配就能把它们挑出来重抓。
"""
import argparse
import sys
import time

sys.path.insert(0, ".")

from bs4 import BeautifulSoup

from app import create_app, db
from app.models import Lead
from app.services import crawler
from app.services.netutil import safe_get
from app.services.textutil import clean_text, looks_garbled, FULL_TEXT_LIMIT

FIELD_LIMIT = FULL_TEXT_LIMIT
OLD_LIMIT = 8000  # 采集旧口径的长度上限，正好等于它=尾部被截


def state_of(lead):
    text = lead.full_text or ''
    if not text.strip():
        return 'missing'
    if looks_garbled(text):
        return 'garbled'
    return 'truncated' if len(text) == OLD_LIMIT else 'ok'


def fetch_text(url, session):
    """抓详情页正文纯文本（与采集同一口径，但不再截到 8000 字）。"""
    resp = safe_get(url, timeout=20, session=session)
    soup = BeautifulSoup(resp.text, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    return clean_text(soup.get_text('\n'))[:FIELD_LIMIT]


def fill_empty_fields(lead, text):
    """只填当前为空的字段，规则路径抽取，避免覆盖 AI 或人工已有的值。"""
    filled = []
    rules = crawler.extract_contact_rules(text)
    for field in ('contact_name', 'contact_phone', 'address', 'purchaser'):
        if not (getattr(lead, field) or '').strip() and (rules.get(field) or '').strip():
            setattr(lead, field, clean_text(rules[field], collapse_space=True))
            filled.append(field)
    if not (lead.budget or '').strip():
        budget = crawler.normalize_amount_text(crawler.extract_budget(text))
        if budget:
            lead.budget = budget
            filled.append('budget')
    if not (lead.winner or '').strip():
        winner = clean_text(crawler.extract_winner(text), collapse_space=True)
        if winner:
            lead.winner = winner
            filled.append('winner')
    if '公告概要' not in (lead.service_content or ''):
        summary = crawler.extract_notice_summary(text)
        if summary:
            lead.service_content = crawler.build_service_content(lead, summary)
            filled.append('service_content')
    return filled


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正写库（默认只报告）')
    ap.add_argument('--missing', action='store_true', help='连「从未抓过正文」的一起补')
    ap.add_argument('--truncated', action='store_true',
                    help='连「被旧 8000 字上限截断」的一起重抓')
    ap.add_argument('--limit', type=int, default=0, help='最多处理多少条，0 表示不限')
    ap.add_argument('--delay', type=float, default=crawler.REQUEST_DELAY,
                    help='每条之间的 politeness 间隔（秒）')
    args = ap.parse_args()

    want = {'garbled'}
    if args.missing:
        want.add('missing')
    if args.truncated:
        want.add('truncated')

    app = create_app()
    with app.app_context():
        leads = Lead.query.filter(Lead.is_deleted.is_(False)).all()
        states = [state_of(l) for l in leads]
        todo = [l for l, s in zip(leads, states) if s in want]
        print(f'线索 {len(leads)} 条，待修 {len(todo)} 条'
              f'（乱码 {states.count("garbled")}，无正文 {states.count("missing")}'
              f'，旧上限截断 {states.count("truncated")}）')
        if not todo:
            return
        if not args.apply:
            for l in todo[:20]:
                print(f'  #{l.id} {l.serial_no} {state_of(l)} {(l.source_url or "")[:70]}')
            print('（以上仅报告，加 --apply 才写库）')
            return

        session = crawler.html_session()
        fixed = failed = 0
        todo = todo[:args.limit] if args.limit else todo
        for idx, lead in enumerate(todo, 1):
            url = (lead.source_url or '').strip()
            if not url.startswith('http'):
                failed += 1
                print(f'  [{idx}/{len(todo)}] #{lead.id} 无原文链接，跳过')
                continue
            try:
                text = fetch_text(url, session)
            except Exception as e:  # 单条失败不该中断整轮（含 SafeFetchError）
                failed += 1
                print(f'  [{idx}/{len(todo)}] #{lead.id} {lead.serial_no} 抓取失败: {str(e)[:70]}')
                time.sleep(args.delay)
                continue
            if not text or looks_garbled(text):
                failed += 1
                print(f'  [{idx}/{len(todo)}] #{lead.id} {lead.serial_no} 抓到仍是空/乱码')
                time.sleep(args.delay)
                continue
            lead.full_text = text
            filled = fill_empty_fields(lead, text)
            db.session.commit()
            fixed += 1
            print(f'  [{idx}/{len(todo)}] #{lead.id} {lead.serial_no} 正文 {len(text)} 字'
                  f'{"，补 " + ",".join(filled) if filled else ""}')
            time.sleep(args.delay)
        print(f'完成：修复 {fixed} 条，失败/跳过 {failed} 条')


if __name__ == '__main__':
    main()
