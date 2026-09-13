"""线索流水编号：年1位 + 月1位 + 日2位 + 流水2位，共6位。

年：6=2026, 7=2027, 8=2028, 9=2029, 0=2030, a=2031, b=2032 ...
月：1-9=1-9月, 0=10月, N=11月, D=12月
示例：691301 = 2026年9月13日第01号
"""
from app.models import Lead, db

_MONTH_CHARS = {1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6',
                7: '7', 8: '8', 9: '9', 10: '0', 11: 'N', 12: 'D'}


def _year_char(year):
    if 2020 <= year <= 2029:
        return str(year % 10)
    if year == 2030:
        return '0'
    return chr(ord('a') + year - 2031)


def gen_serial(created_at):
    """按创建日期生成流水号：当年当日已有 N 条则流水为 N+1（超过99则继续用3位以保唯一）。"""
    y = _year_char(created_at.year)
    m = _MONTH_CHARS[created_at.month]
    prefix = f"{y}{m}{created_at.day:02d}"
    count = db.session.query(Lead).filter(Lead.serial_no.like(prefix + '%')).count()
    seq = count + 1
    return prefix + (f"{seq:02d}" if seq <= 99 else str(seq))
