"""行政区划解析：基于离线数据（data/divisions.json，31省/342市/3056县区）
从公告文本/采购单位/地址中精准提取 省+市+县区 简称，如"黑龙江哈尔滨依兰"。

核心原则：县级名称必须通过离线索引校验，省/市归属以索引为准，
杜绝"北京省依兰县"这类把网页页脚省份拼到县名前面的错误。
"""
import json
import os
import re

_DATA = None


def _load():
    global _DATA
    if _DATA is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'divisions.json')
        with open(path, encoding='utf-8') as f:
            _DATA = json.load(f)
    return _DATA


def _entries_unique(entries):
    return len({(e['p'], e['c'], e.get('n', '')) for e in entries}) == 1


def _pick(entries, prov_hint='', city_hint=''):
    """重名县区消歧：优先用市名提示，其次省名提示。"""
    if _entries_unique(entries):
        return entries[0]
    if city_hint:
        for e in entries:
            c = e.get('c') or ''
            if c and (city_hint.startswith(c) or c.startswith(city_hint)):
                return e
    if prov_hint:
        for e in entries:
            p = e['p']
            if prov_hint.startswith(p) or p.startswith(prov_hint):
                return e
    return entries[0]


def _match_county(name):
    """县区名（含/不含后缀）查询合并索引，返回 entries 列表或空。"""
    counties = _load()['counties']
    return counties.get(name) or []


def _match_county_orig(name):
    """县区原名（含后缀）查询，用于文本匹配，避免简称键被子串误命中
    （如'黄梅县'误匹配简称'梅县'、'天津市'误匹配简称'津市'）。"""
    return _load()['counties_orig'].get(name) or []


def _match_city(name):
    cities = _load()['cities']
    return cities.get(name) or []


def _match_province(name):
    provs = _load()['provinces']
    if name in provs:
        return provs[name]
    return None


def _extract_candidates(s):
    """从一段文本提取 省/市/县 候选原名（不校验）。

    县级：对每个行政区划后缀（县/区/旗/市…），从后缀往前取 1~6 字逐长度
    尝试命中索引，避免贪婪匹配把市名吞进县名（如"泉州市洛江区"）。
    """
    if not s:
        return '', '', ''
    prov = ''
    m = re.search(r'[\u4e00-\u9fa5]{2,8}?(?:自治区|特别行政区)|[\u4e00-\u9fa5]{2,6}省', s)
    if m:
        prov = m.group(0)
    else:
        for dm in ('北京', '上海', '天津', '重庆'):
            if re.search(dm + r'市', s):
                prov = dm + '市'
                break
    city = ''
    m = re.search(r'[\u4e00-\u9fa5]{2,10}?(?:自治州|地区|盟)', s)
    if m:
        city = m.group(0)
    else:
        # 普通地级市：取"XX市"，排除直辖市（已归为省）
        for mm in re.finditer(r'([\u4e00-\u9fa5]{2,6})市', s):
            name = mm.group(1)
            if name not in ('北京', '上海', '天津', '重庆'):
                city = name + '市'
                break
    county = ''
    # 对每个行政区划后缀，从后缀向前取最长候选优先尝试原名索引（最长12字县名）
    for mm in re.finditer(r'自治县|自治旗|林区|特区|新区|矿区|[县区旗市]', s):
        end, start_min = mm.end(), max(0, mm.start() - 12)
        for start in range(start_min, mm.start()):
            cand = s[start:end]
            if _match_county_orig(cand):
                county = cand
                break
        if county:
            break
    return prov, city, county


def resolve_region(*sources):
    """按来源优先级解析地区，返回"省简称+市简称+县区简称"（如"浙江丽水松阳"）。

    sources 依次为：地址 > AI region > 采购单位 > 标题 > 正文片段。
    县级命中索引后，省/市一律以索引为准（含重名消歧），忽略文本中的干扰省份。
    """
    sources = [s for s in sources if s]
    for src in sources:
        prov_raw, city_raw, county_raw = _extract_candidates(src)
        prov_hint = _match_province(prov_raw) if prov_raw else ''
        city_hint = ''
        if city_raw:
            city_entries = _match_city(city_raw)
            if city_entries:
                ce = _pick(city_entries, prov_hint)
                prov_hint = prov_hint or ce['p']
                city_hint = ce['c']
        if county_raw:
            entries = _match_county(county_raw)
            if entries:
                e = _pick(entries, prov_hint, city_hint)
                # 城市/省份提示与索引冲突时，以索引为准；市县同名/前缀（黄山市黄山区、威海经济技术开发区）去重
                n = e['n'] or ''
                c = e['c'] or ''
                if n == c or (c and n.startswith(c)):
                    n = ''
                return e['p'] + c + n
        if city_hint:
            return prov_hint + city_hint
        if prov_hint:
            return prov_hint
    # 无任何索引命中：从全文按传统正则兜底（仅省级+市，不硬拼县）
    for src in sources:
        prov_raw, city_raw, _ = _extract_candidates(src)
        prov_hint = _match_province(prov_raw) if prov_raw else ''
        if city_raw:
            city_entries = _match_city(city_raw)
            if city_entries:
                ce = _pick(city_entries, prov_hint)
                return ce['p'] + (ce['c'] or '')
        if prov_hint:
            return prov_hint
    # 最终兜底：特殊区划（昆嵛山保护区/长岛综试区等）不在标准数据中，
    # 用城市简称/省份简称做宽松子串匹配
    data = _load()
    prov_full = [k for k in data['provinces'] if k.endswith(('省', '自治区', '市'))]
    prov_shorts = sorted(set(data['provinces'].values()), key=len, reverse=True)
    city_shorts = sorted({e['c'] for es in data['cities'].values() for e in es if e['c']},
                         key=len, reverse=True)
    for src in sources:
        # 城市简称命中 → 省+市（省份归属来自城市索引）
        for cs in city_shorts:
            if cs in src:
                entries = _match_city(cs)
                if entries:
                    return entries[0]['p'] + entries[0]['c']
        for fs in prov_full:
            if fs in src:
                return data['provinces'][fs]
        for ps in prov_shorts:
            if ps in src:
                return ps
    return ''
