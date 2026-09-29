"""线索流水编号：年1位 + 月1位 + 日2位 + 流水2位，共6位。

年：6=2026, 7=2027, 8=2028, 9=2029, 0=2030, a=2031, b=2032 ...
月：1-9=1-9月, 0=10月, N=11月, D=12月
示例：691301 = 2026年9月13日第01号
"""
import sqlalchemy.exc
from app.models import Lead, db

_MONTH_CHARS = {1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6',
                7: '7', 8: '8', 9: '9', 10: '0', 11: 'N', 12: 'D'}


def _year_char(year):
    if 2020 <= year <= 2029:
        return str(year % 10)
    if year == 2030:
        return '0'
    return chr(ord('a') + year - 2031)


def _next_serial(created_at):
    """按当日已有编号的最大序号 +1 生成（MAX 而非 count，避免删除后编号复用）。"""
    y = _year_char(created_at.year)
    m = _MONTH_CHARS[created_at.month]
    prefix = f"{y}{m}{created_at.day:02d}"
    rows = (db.session.query(Lead.serial_no)
            .filter(Lead.serial_no.like(prefix + '%')).all())
    max_seq = 0
    for (sn,) in rows:
        tail = sn[len(prefix):]
        if tail.isdigit():
            max_seq = max(max_seq, int(tail))
    seq = max_seq + 1
    return prefix + (f"{seq:02d}" if seq <= 99 else str(seq))


def gen_serial(created_at):
    """生成唯一流水号：与库中已有编号冲突时（并发）自动重试。"""
    for _ in range(50):
        sn = _next_serial(created_at)
        if not db.session.query(Lead.id).filter(Lead.serial_no == sn).first():
            return sn
    raise RuntimeError("流水号生成失败：当日序号异常拥挤")
