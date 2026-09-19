"""文本清洗：去掉网页/公告正文里混进来的控制字符与不可见字符。

背景
----
招标公告页面抓下来的正文里常带这些字符，``str.strip()`` 一个都去不掉：

* ``0x1E`` 记录分隔符 —— 公告批量导出常见，会跟着"中标单位/采购单位"一起被抽出来；
* ``0xA0`` 不换行空格（NBSP）—— 网页排版残留；
* ``0x200D`` 零宽连接符、``0xFEFF`` BOM 等 —— 肉眼完全不可见。

它们一旦写进数据库，在界面上会渲染成"乱码方块"。真实案例：
客户名被存成 ``"\\x1e安徽铁塔"``，于是所有下拉框、列表、甚至弹窗标题
（``执行联络 · □安徽铁塔``）都带一个方块。
"""
import re

# 保留 \t \n \r，其余 C0/C1 控制字符与 DEL 一律去掉
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
# 零宽字符、BOM、行/段分隔符、双向控制符
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u2028\u2029\u202a-\u202e\u2060-\u2064\ufeff]")
# 各种"看起来像空格"的字符：NBSP、窄空格、全角空格等
_SPACE_RE = re.compile(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]")


def clean_text(value, collapse_space=False):
    """清洗文本，返回 str。

    :param value: 任意值；None 返回空串，非字符串先 str() 转换
    :param collapse_space: True 时把连续空格/制表符压成单个空格（适合单行字段，
        不适合正文）
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = _CONTROL_RE.sub("", value)
    value = _ZERO_WIDTH_RE.sub("", value)
    value = _SPACE_RE.sub(" ", value)
    if collapse_space:
        value = re.sub(r"[ \t]+", " ", value)
    return value.strip()
