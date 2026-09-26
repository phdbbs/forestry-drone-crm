"""金额解析与归一化：把混存的预算/金额字符串统一折算为「万元」。

背景
----
budget / amount 字段是 String(50)，历史上多种写法混存：
"150万"、"150 万元"、"1,500.50"、"3亿"、"500000元"、"面议"……
旧版 analytics 用 ``re.search(r'[\\d.]+')`` 提取数字，遇到带千分位的
"1,500.50" 只会取到 "1"，且完全不区分元/万/亿，漏斗金额严重失真。

约定
----
* 解析目标单位统一为 **万元**（float）；
* 无显式单位的裸数字，按招标字段惯例视为万元；
* 无法解析的文本（如"面议"）原样保留，不丢信息。
"""
import re

# 首个数字串：支持千分位逗号与小数
_NUM_RE = re.compile(r'\d[\d,]*(?:\.\d+)?')


def parse_amount_wan(value):
    """把金额字符串解析为「万元」float；无法解析返回 None。

    >>> parse_amount_wan("150万")        # 150.0
    >>> parse_amount_wan("1,500.50万元") # 1500.5
    >>> parse_amount_wan("3亿")          # 30000.0
    >>> parse_amount_wan("500000元")     # 50.0
    >>> parse_amount_wan("150")          # 150.0（裸数字按万元惯例）
    >>> parse_amount_wan("面议")          # None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(' ', '').replace('，', ',')
    if not s:
        return None
    m = _NUM_RE.search(s)
    if not m:
        return None
    try:
        num = float(m.group(0).replace(',', ''))
    except ValueError:
        return None
    if '亿' in s:
        return round(num * 10000, 4)
    if '万' in s:
        return round(num, 4)
    if '元' in s:
        # 明确写"元"而无万/亿 → 按元折算
        return round(num / 10000, 4)
    # 无单位：预算/金额字段惯例为万元
    return round(num, 4)


def normalize_amount_text(value):
    """把混存金额串规范为 "N万"（万元）字符串，用于入库前清洗。

    无法解析的文本（"面议"、"待定"等）原样返回，避免丢失信息；
    空值返回空串。
    """
    if value is None:
        return ''
    s = str(value).strip()
    if not s:
        return ''
    wan = parse_amount_wan(s)
    if wan is None:
        return s
    # g 格式去掉多余的 .0：150.0 → 150，150.50 → 150.5
    return f"{wan:g}万"
