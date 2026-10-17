"""v5.2 存量数据回填：联系人的来源线索 + 客户类型映射到新枚举。

用法（在 /Users/wl/M4/CRM 下，先用 daemonize/CRM.app 停服或确认无并发写入）：
    .venv/bin/python scripts/backfill_v52.py            # 只报告，不写库
    .venv/bin/python scripts/backfill_v52.py --apply    # 真正写库

两件事都能重复执行：已回填的联系人会被 lead_id is null 过滤掉，客户类型映射只匹配旧值。
"""
import os
import re
import sys

sys.path.insert(0, ".")

from sqlalchemy import text

from app import create_app, db

APPLY = "--apply" in sys.argv

# 来源线索的备注由 convert_lead 写入：「由线索[标题前 60 字]转化自动创建」
NOTE_RE = re.compile(r'^由线索\[(.+?)\]')

# 旧枚举 → 新枚举（只列能明确归类的；归不进的一律不动，宁可保留原值也不瞎猜）
CUSTOMER_TYPE_MAP = {
    '政府部门': '政府/林场',
    '事业单位': '政府/林场',
    '国有企业': '政府/林场',
    '政府': '政府/林场',
    '其他': '其他占位1',
}


def backfill_contact_leads(s):
    """给「由线索转化自动创建」的老联系人补 lead_id。

    优先级：商机上记录的 lead_id（转化时写死的，最可信）> 标题前缀唯一命中。
    命中多条说明同一项目发过好几类公告，宁可不填也不猜一条挂上去。
    """
    rows = s.execute(text(
        "select id, notes from contacts "
        "where lead_id is null and is_deleted = 0 and notes like '由线索[%'"
    )).fetchall()
    filled, by_opp, by_title, skipped = [], 0, 0, []
    for cid, notes in rows:
        lead_ids = s.execute(text(
            "select distinct lead_id from opportunities "
            "where contact_id = :c and lead_id is not null and is_deleted = 0"
        ), {'c': cid}).scalars().all()
        target = None
        if len(lead_ids) == 1:
            target, by_opp = lead_ids[0], by_opp + 1
            filled.append((cid, target, '商机回链'))
        else:
            m = NOTE_RE.match(notes or '')
            if m:
                frag = m.group(1)
                hits = s.execute(text(
                    "select id from leads where is_deleted = 0 and substr(title, 1, :n) = :f"
                ), {'n': len(frag), 'f': frag}).scalars().all()
                if len(hits) == 1:
                    target, by_title = hits[0], by_title + 1
                    filled.append((cid, target, '标题唯一命中'))
        if target is None:
            skipped.append(cid)
    return filled, skipped, (len(rows), by_opp, by_title)


def map_customer_types(s):
    rows = s.execute(text(
        "select coalesce(customer_type, '(空)') as t, count(*) from customers "
        "where is_deleted = 0 group by 1 order by 2 desc"
    )).fetchall()
    plan = [(old, new, n) for old, new in CUSTOMER_TYPE_MAP.items()
            for t, n in rows if t == old]
    return rows, plan


def main():
    # 演练时可以指向别的库（升级前的备份副本），默认动实机库
    db_file = os.environ.get('CRM_DB_FILE')
    app = create_app({'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + os.path.abspath(db_file)} if db_file else None)
    with app.app_context():
        s = db.session
        filled, skipped, (total, by_opp, by_title) = backfill_contact_leads(s)
        print(f'待回填联系人 {total} 条：商机回链 {by_opp}，标题唯一命中 {by_title}，'
              f'歧义跳过 {len(skipped)}')
        if skipped:
            print(f'  歧义联系人 id（公告标题前缀命中多条，需人工确认）: {skipped}')

        cur_rows, plan = map_customer_types(s)
        print('客户类型现状: ' + ', '.join(f'{t}={n}' for t, n in cur_rows))
        for old, new, n in plan:
            print(f'  映射: {old} -> {new}（{n} 条）')

        if not APPLY:
            print('（演练模式，未写库；加 --apply 才执行）')
            return
        for cid, lid, _ in filled:
            s.execute(text("update contacts set lead_id = :l where id = :c"), {'l': lid, 'c': cid})
        for old, new, _ in plan:
            s.execute(text("update customers set customer_type = :n where customer_type = :o and is_deleted = 0"),
                      {'n': new, 'o': old})
        s.commit()
        print(f'已写入：{len(filled)} 个联系人补上来源线索，{sum(n for _, _, n in plan)} 个客户换类型')


if __name__ == '__main__':
    main()
