"""一次性清理存量脏数据：把已入库的控制字符/零宽字符/异常空格洗掉。

用法（在 /Volumes/M4/CRM_work 下）：
    /Users/wl-macbookair/.workbuddy-ai/binaries/python/envs/crm-test/bin/python scripts/clean_dirty_text.py [--apply]

不带 --apply 只报告，不写库。
"""
import sys
import unicodedata

sys.path.insert(0, ".")

from app import create_app, db
from app.models import Customer, Lead, FollowUp
from app.services.textutil import clean_text

APPLY = "--apply" in sys.argv

# 只处理这几张表的这些字段：实际扫描出的污染就在这儿。
# 第三项是 collapse_space —— 单行标识类字段压空格，长正文保留原始排版。
TARGETS = [
    (Customer, [
        ("name", True), ("short_name", True), ("customer_type", True), ("level", True),
        ("region", True), ("address", True), ("website", True),
        ("registration_capital", True), ("operation_years", True), ("department", True),
        ("source", True), ("business_scope", True), ("intellectual_property", True),
        ("remark", True),
    ]),
    (Lead, [
        ("title", True), ("bid_number", True), ("region", True), ("purchaser", True),
        ("contact_name", True), ("contact_phone", True), ("address", True),
        ("winner", True), ("source_platform", True), ("bid_type", True),
        ("assignee", True), ("match_level", True), ("match_reason", True),
        ("match_keywords", True), ("reason", True),
        ("service_content", True),
        # 公告全文：保留原始排版，只去不可见字符
        ("full_text", False),
    ]),
    (FollowUp, [("ai_suggested_content", True)]),
]


def bad_chars(value):
    out = []
    for ch in value:
        o = ord(ch)
        if ch in "\t\n\r":
            continue
        if o < 32 or 0x7f <= o <= 0x9f:
            out.append(ch)
        elif o in (0x200b, 0x200c, 0x200d, 0x200e, 0x200f, 0xfeff, 0x00a0, 0x3000):
            out.append(ch)
        elif unicodedata.category(ch) in ("Cf", "Co", "Cs"):
            out.append(ch)
    return out


def main():
    app = create_app()
    with app.app_context():
        changed_rows = 0
        changed_cells = 0
        for model, fields in TARGETS:
            for row in model.query.all():
                touched = []
                for f, collapse in fields:
                    val = getattr(row, f, None)
                    if not isinstance(val, str) or not val:
                        continue
                    hits = bad_chars(val)
                    if not hits:
                        continue
                    cleaned = clean_text(val, collapse_space=collapse)
                    if cleaned != val:
                        touched.append((f, val, cleaned, sorted({ord(c) for c in hits})))
                        if APPLY:
                            setattr(row, f, cleaned)
                        changed_cells += 1
                if touched:
                    changed_rows += 1
                    pk = getattr(row, "id", "?")
                    print(f"[{model.__tablename__} id={pk}]")
                    for f, before, after, codes in touched:
                        code_s = ",".join(f"0x{c:02x}" for c in codes)
                        print(f"    .{f}  [{code_s}]  {len(before)} -> {len(after)} 字符")
                        # 定位第一个坏字符，避免被截断隐藏
                        pos = next(i for i, ch in enumerate(before) if ord(ch) in codes)
                        lo, hi = max(0, pos - 18), pos + 18
                        print(f"        坏字符位置 {pos}，上下文: ...{before[lo:hi]!r}...")
        if APPLY:
            db.session.commit()
            print(f"\n已提交：{changed_rows} 行 / {changed_cells} 个字段")
        else:
            print(f"\n[dry-run] 待清理：{changed_rows} 行 / {changed_cells} 个字段（加 --apply 才写库）")


if __name__ == "__main__":
    main()
