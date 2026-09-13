import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from app import db
from app.models import Lead, SystemConfig
from app.services.matcher import match_lead
from app.services.ai_client import extract_lead
from app.services.regions import resolve_region
from app.services.serial import gen_serial
import re, time, json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Referer": "https://www.ccgp.gov.cn/",
}

# Delay between keyword requests (seconds) to avoid triggering rate limits
REQUEST_DELAY = 3


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
        except (json.JSONDecodeError, TypeError):
            pass
    # Also read from keywords config (comma-separated)
    kw_config = configs.get('keywords', '')
    if kw_config:
        for kw in kw_config.split(','):
            kw = kw.strip()
            if kw and kw not in keywords:
                keywords.append(kw)
    return keywords or ["无人机", "林业", "病虫害", "巡检"]


def extract_budget(text):
    for p in [r"预算[金额价格]*[:：]\s*([\d,.]+)\s*[万]?元", r"项目预算[:：]\s*([\d,.]+)", r"总预算[:：]\s*([\d,.]+)"]:
        m = re.search(p, text)
        if m:
            return m.group(1)
    return ""


def extract_region(text):
    """简易省份提取（向后兼容）。"""
    provinces = ["北京", "上海", "重庆", "天津", "河北", "山西", "辽宁", "吉林",
                 "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
                 "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
                 "甘肃", "青海", "内蒙古", "广西", "西藏", "宁夏", "新疆"]
    for p in provinces:
        if p in text:
            return p
    return ""


# 城市 → 省份映射（用于补全省份前缀）
CITY_TO_PROVINCE = {
    # 四川省
    "成都": "四川省", "绵阳": "四川省", "德阳": "四川省", "南充": "四川省",
    "宜宾": "四川省", "泸州": "四川省", "乐山": "四川省", "达州": "四川省",
    "眉山": "四川省", "内江": "四川省", "遂宁": "四川省", "雅安": "四川省",
    "广安": "四川省", "巴中": "四川省", "资阳": "四川省", "凉山": "四川省",
    "攀枝花": "四川省", "广元": "四川省", "自贡": "四川省", "凉山彝族自治州": "四川省",
    "巴塘县": "四川省", "理塘县": "四川省", "乡城县": "四川省", "稻城县": "四川省",
    "得荣县": "四川省", "九龙县": "四川省", "新龙县": "四川省", "雅江县": "四川省",
    "道孚县": "四川省", "炉霍县": "四川省", "甘孜县": "四川省",
    # 重庆市（直辖市）
    "重庆": "重庆市", "两江新区": "重庆市", "渝中区": "重庆市", "南岸区": "重庆市",
    "江北区": "重庆市", "沙坪坝区": "重庆市", "九龙坡区": "重庆市", "大渡口区": "重庆市",
    "渝北区": "重庆市", "北碚区": "重庆市", "巴南区": "重庆市", "璧山区": "重庆市",
    "合川区": "重庆市", "永川区": "重庆市", "铜梁区": "重庆市", "大足区": "重庆市",
    "荣昌区": "重庆市", "黔江区": "重庆市", "长寿区": "重庆市", "江津区": "重庆市",
    "綦江区": "重庆市", "潼南区": "重庆市", "南川区": "重庆市", "万州区": "重庆市",
    "涪陵区": "重庆市", "城口县": "重庆市", "丰都县": "重庆市", "垫江县": "重庆市",
    "武隆区": "重庆市", "忠县": "重庆市", "开州区": "重庆市", "云阳县": "重庆市",
    "奉节县": "重庆市", "巫山县": "重庆市", "巫溪县": "重庆市", "石柱县": "重庆市",
    "秀山县": "重庆市", "酉阳县": "重庆市", "彭水县": "重庆市",
    # 安徽省
    "合肥": "安徽省", "芜湖": "安徽省", "蚌埠": "安徽省", "淮南": "安徽省",
    "马鞍山": "安徽省", "淮北": "安徽省", "铜陵": "安徽省", "安庆": "安徽省",
    "黄山": "安徽省", "滁州": "安徽省", "阜阳": "安徽省", "宿州": "安徽省",
    "六安": "安徽省", "亳州": "安徽省", "池州": "安徽省", "宣城": "安徽省",
    "贵池区": "安徽省", "池州市": "安徽省",
    # 山东省
    "济南": "山东省", "青岛": "山东省", "淄博": "山东省", "枣庄": "山东省",
    "东营": "山东省", "烟台": "山东省", "潍坊": "山东省", "济宁": "山东省",
    "泰安": "山东省", "威海": "山东省", "日照": "山东省", "临沂": "山东省",
    "德州": "山东省", "聊城": "山东省", "滨州": "山东省", "菏泽": "山东省",
    "岱岳区": "山东省", "泰安市": "山东省",
    # 陕西省
    "西安": "陕西省", "咸阳": "陕西省", "宝鸡": "陕西省", "渭南": "陕西省",
    "汉中": "陕西省", "榆林": "陕西省", "安康": "陕西省", "商洛": "陕西省",
    "延安": "陕西省", "铜川": "陕西省", "略阳县": "陕西省",
    # 浙江省
    "杭州": "浙江省", "宁波": "浙江省", "温州": "浙江省", "嘉兴": "浙江省",
    "湖州": "浙江省", "绍兴": "浙江省", "金华": "浙江省", "衢州": "浙江省",
    "舟山": "浙江省", "台州": "浙江省", "丽水": "浙江省", "云和县": "浙江省",
    "龙游县": "浙江省",
    # 山西省
    "太原": "山西省", "大同": "山西省", "阳泉": "山西省", "长治": "山西省",
    "晋城": "山西省", "朔州": "山西省", "晋中": "山西省", "运城": "山西省",
    "忻州": "山西省", "临汾": "山西省", "吕梁": "山西省", "潞州区": "山西省",
    "长治市": "山西省",
    "长治": "山西省",
    # 新疆
    "乌鲁木齐": "新疆维吾尔自治区", "喀什": "新疆维吾尔自治区", "库尔勒市": "新疆维吾尔自治区",
    "库尔勒": "新疆维吾尔自治区",
    "巴音郭楞": "新疆维吾尔自治区", "巴音郭楞蒙古自治州": "新疆维吾尔自治区",
    # 内蒙古
    "呼和浩特": "内蒙古自治区", "包头": "内蒙古自治区", "赤峰": "内蒙古自治区",
    "鄂尔多斯": "内蒙古自治区", "呼伦贝尔": "内蒙古自治区", "通辽": "内蒙古自治区",
    "乌兰察布": "内蒙古自治区", "达拉特旗": "内蒙古自治区",
    # 吉林省
    "长春": "吉林省", "吉林": "吉林省", "四平": "吉林省", "辽源": "吉林省",
    "通化": "吉林省", "白山": "吉林省", "松原": "吉林省", "白城": "吉林省",
    "延边": "吉林省",
    # 黑龙江省
    "哈尔滨": "黑龙江省", "齐齐哈尔": "黑龙江省", "鸡西": "黑龙江省",
    "鹤岗": "黑龙江省", "双鸭山": "黑龙江省", "大庆": "黑龙江省",
    "伊春": "黑龙江省", "佳木斯": "黑龙江省", "七台河": "黑龙江省",
    "牡丹江": "黑龙江省", "黑河": "黑龙江省", "绥化": "黑龙江省", "大兴安岭": "黑龙江省",
    # 辽宁省
    "沈阳": "辽宁省", "大连": "辽宁省", "鞍山": "辽宁省", "抚顺": "辽宁省",
    "本溪": "辽宁省", "丹东": "辽宁省", "锦州": "辽宁省", "营口": "辽宁省",
    "阜新": "辽宁省", "辽阳": "辽宁省", "盘锦": "辽宁省", "铁岭": "辽宁省",
    "朝阳": "辽宁省", "葫芦岛": "辽宁省",
    # 甘肃省
    "兰州": "甘肃省", "嘉峪关": "甘肃省", "金昌": "甘肃省", "白银": "甘肃省",
    "天水": "甘肃省", "武威": "甘肃省", "张掖": "甘肃省", "平凉": "甘肃省",
    "酒泉": "甘肃省", "庆阳": "甘肃省", "定西": "甘肃省", "陇南": "甘肃省",
    "临夏": "甘肃省", "甘南": "甘肃省",
    # 青海省
    "西宁": "青海省", "海东": "青海省", "海北": "青海省", "黄南": "青海省",
    "海南": "青海省", "果洛": "青海省", "玉树": "青海省", "海西": "青海省",
    # 宁夏
    "银川": "宁夏回族自治区", "石嘴山": "宁夏回族自治区", "吴忠": "宁夏回族自治区",
    "固原": "宁夏回族自治区", "中卫": "宁夏回族自治区",
    # 广西
    "南宁": "广西壮族自治区", "柳州": "广西壮族自治区", "桂林": "广西壮族自治区",
    "梧州": "广西壮族自治区", "北海": "广西壮族自治区", "防城港": "广西壮族自治区",
    "钦州": "广西壮族自治区", "贵港": "广西壮族自治区", "玉林": "广西壮族自治区",
    "百色": "广西壮族自治区", "贺州": "广西壮族自治区", "河池": "广西壮族自治区",
    "来宾": "广西壮族自治区", "崇左": "广西壮族自治区",
    # 西藏
    "拉萨": "西藏自治区", "日喀则": "西藏自治区", "昌都": "西藏自治区",
    "林芝": "西藏自治区", "山南": "西藏自治区", "那曲": "西藏自治区",
    "阿里": "西藏自治区",
    # 云南
    "昆明": "云南省", "曲靖": "云南省", "玉溪": "云南省", "保山": "云南省",
    "昭通": "云南省", "丽江": "云南省", "普洱": "云南省", "临沧": "云南省",
    "楚雄": "云南省", "红河": "云南省", "文山": "云南省", "西双版纳": "云南省",
    "大理": "云南省", "德宏": "云南省", "怒江": "云南省", "迪庆": "云南省",
    # 贵州
    "贵阳": "贵州省", "六盘水": "贵州省", "遵义": "贵州省", "安顺": "贵州省",
    "毕节": "贵州省", "铜仁": "贵州省", "黔西南": "贵州省", "黔东南": "贵州省",
    "黔南": "贵州省",
    # 湖南省
    "长沙": "湖南省", "株洲": "湖南省", "湘潭": "湖南省", "衡阳": "湖南省",
    "邵阳": "湖南省", "岳阳": "湖南省", "常德": "湖南省", "张家界": "湖南省",
    "益阳": "湖南省", "郴州": "湖南省", "永州": "湖南省", "怀化": "湖南省",
    "娄底": "湖南省", "湘西": "湖南省",
    # 湖北省
    "武汉": "湖北省", "黄石": "湖北省", "十堰": "湖北省", "宜昌": "湖北省",
    "襄阳": "湖北省", "鄂州": "湖北省", "荆门": "湖北省", "孝感": "湖北省",
    "荆州": "湖北省", "黄冈": "湖北省", "咸宁": "湖北省", "随州": "湖北省",
    "恩施": "湖北省",
    # 河南省
    "郑州": "河南省", "开封": "河南省", "洛阳": "河南省", "平顶山": "河南省",
    "安阳": "河南省", "鹤壁": "河南省", "新乡": "河南省", "焦作": "河南省",
    "濮阳": "河南省", "许昌": "河南省", "漯河": "河南省", "三门峡": "河南省",
    "南阳": "河南省", "商丘": "河南省", "信阳": "河南省", "周口": "河南省",
    "驻马店": "河南省",
    # 河北省
    "石家庄": "河北省", "唐山": "河北省", "秦皇岛": "河北省", "邯郸": "河北省",
    "邢台": "河北省", "保定": "河北省", "张家口": "河北省", "承德": "河北省",
    "沧州": "河北省", "廊坊": "河北省", "衡水": "河北省",
    # 江苏省
    "南京": "江苏省", "无锡": "江苏省", "徐州": "江苏省", "常州": "江苏省",
    "苏州": "江苏省", "南通": "江苏省", "连云港": "江苏省", "淮安": "江苏省",
    "盐城": "江苏省", "扬州": "江苏省", "镇江": "江苏省", "泰州": "江苏省",
    "宿迁": "江苏省",
    # 安徽省补充
    "礼泉县": "陕西省",
    "咸阳市": "陕西省",
}


def extract_region_full(text, purchaser=""):
    """从公告文本提取完整省市区县，如'山东省威海市荣成市'。

    按优先级：采购单位地址 > 行政区域+采购单位名 > 标题省份兜底。
    从地址中非重叠提取 省/自治区/直辖市 + 市/州 + 县/区。
    """
    def _parse_addr(addr):
        """从地址字符串中按省→市→县顺序非重叠提取。"""
        province = muni = county = ""
        rest = addr
        # 1. 省/自治区（如"安徽省"、"内蒙古自治区"）
        p = re.search(r"([\u4e00-\u9fa5]{2,8}(?:省|自治区))", rest)
        if p:
            province = p.group(1)
            rest = rest[p.end():]
        else:
            # 只匹配四个直辖市（北京/上海/天津/重庆），不匹配其他带"市"的地名
            for _dm in ("北京", "上海", "天津", "重庆"):
                _m = re.match(rf'^({re.escape(_dm)}市)', rest)
                if _m:
                    province = _m.group(1)
                    rest = rest[_m.end():]
                    break
        # 2. 市/州/盟（非贪婪匹配，避免"长治市潞州区"被误匹配为"长治市潞州"）
        #    如候选城市在映射表中且无省份，用城市补全省份
        m = re.search(r"([\u4e00-\u9fa5]+?[市州盟])", rest)
        if m:
            candidate = m.group(1)
            if candidate in CITY_TO_PROVINCE and not province:
                province = CITY_TO_PROVINCE[candidate]
            if not (province and candidate in province):
                muni = candidate
                rest = rest[m.end():]
        # 3. 县/区/旗：先贪婪匹配，若结果含连续两个后缀字符（如"县县"）则回退到非贪婪
        c = re.search(r"([\u4e00-\u9fa5]+[县区旗])", rest)
        if c:
            candidate = c.group(1)
            if re.search(r'[县区旗]{2}', candidate):
                c2 = re.search(r"([\u4e00-\u9fa5]+?[县区旗])", rest)
                county = c2.group(1) if c2 else candidate
            else:
                county = candidate
        return province, muni, county

    def _resolve_province(prov, city_name):
        """用映射表补全省份。"""
        if prov and prov.endswith(("省", "自治区", "市")):
            return prov
        if city_name and city_name in CITY_TO_PROVINCE:
            return CITY_TO_PROVINCE[city_name]
        return extract_region(text)

    # 1. 从采购单位地址 / 采购人地址 / 地址 提取（兼容完整页文本与服务详情）
    m = re.search(r"(?:采购单位|采购人(?:办公)?|)?地址[:：\s]*([^\s，。；\n]{4,80})", text)
    if m:
        province, muni, county = _parse_addr(m.group(1).strip())
        if province or len(muni) >= 3:
            return province + muni + county
        # 地址只提取到县级，尝试补全省份
        if county:
            # 先查城市→省份映射表
            for city_name in reversed([muni, county]):
                if city_name and city_name in CITY_TO_PROVINCE:
                    return CITY_TO_PROVINCE[city_name] + city_name + (" " + county if city_name != county else "")
            # 退回到从文本提取省份
            prov = extract_region(text)
            if prov and prov not in county:
                return prov + ("省" if not prov.endswith("市") else "") + county
            return county

    # 2. 行政区域（省级）+ 采购单位名称中的市县
    province = ""
    m = re.search(r"行政区域[:：\s]*([\u4e00-\u9fa5]{2,4})", text)
    if m:
        province = m.group(1).strip()
    else:
        province = extract_region(text)

    city_county = ""
    if purchaser and not (province and province.endswith("市")):
        m = re.search(r"([\u4e00-\u9fa5]+?[县区市])", purchaser)
        if m:
            city_county = m.group(1)
            # 查映射表补全省份
            if not province:
                province = _resolve_province("", city_county)

    if province and city_county:
        return province + city_county
    elif province:
        return province
    elif city_county:
        return city_county
    return ""


_NOTICE_LABELS = (
    "采购项目名称", "项目名称", "采购单位", "行政区域", "公告时间", "发布时间",
    "获取招标文件时间", "获取资格预审文件时间", "招标文件售价", "获取招标文件的地点",
    "获取招标、资格预审文件的地点", "开标时间", "开标地点", "开启时间", "开启地点",
    "预算金额", "最高限价", "合同履行期限", "采购需求", "项目联系人", "项目联系电话",
    "采购单位地址", "采购单位联系方式", "代理机构名称", "代理机构地址", "代理机构联系方式",
    "公告信息", "联系人及联系方式", "资格要求", "对本次招标提出询问",
)


def extract_notice_summary(page_text):
    """提取"公告概要"区块全文，整理为"标签：值；标签：值"格式。

    政府采购公告页的概要是标准结构化区块，从"公告概要"行起、
    到"项目概况"等正文起始标记止；标签行后跟内容行，配对整理。
    """
    if not page_text:
        return ""
    lines = [l.strip() for l in page_text.split('\n') if l.strip()]
    start = None
    for i, l in enumerate(lines):
        if "公告概要" in l:
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith(("项目概况", "公告正文", "一、", "根据")):
            end = j
            break
    block = lines[start:end]
    if not block:
        return ""

    def is_label(l):
        if l in _NOTICE_LABELS:
            return l
        for nl in _NOTICE_LABELS:
            if l.startswith(nl + "：") or l.startswith(nl + ":"):
                return nl
        if l.endswith(("：", ":")):
            core = l.rstrip("：:")
            if 2 <= len(core) <= 15:
                return core
        return None

    pairs, cur, buf = [], None, []
    for l in block:
        lab = is_label(l)
        if lab:
            if cur:
                pairs.append((cur, " ".join(buf)))
            cur, buf = lab, []
            rest = l[len(lab):].lstrip("：: ").strip() if l != lab else ""
            if rest:
                buf.append(rest)
        else:
            if cur is None:
                cur, buf = "公告信息", []
            buf.append(l)
    if cur:
        pairs.append((cur, " ".join(buf)))
    return "；".join(f"{k}：{v}" for k, v in pairs if v)


def build_service_content(lead, summary):
    """用公告概要重建线索的 service_content（概要优先展示）。"""
    parts = [
        ("公告概要", summary), ("客户方", lead.purchaser),
        ("中标/成交单位", lead.winner), ("联系人", lead.contact_name),
        ("联系方式", lead.contact_phone), ("地址", lead.address),
        ("预算", lead.budget),
    ]
    return "；".join(f"{k}: {v}" for k, v in parts if v)


def extract_deadline(text):
    m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", text)
    if m:
        try:
            s = m.group(1).replace("年", "-").replace("月", "-").replace("/", "-")
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            pass
    return None


def detect_antibot(html_text):
    """Detect anti-bot/rate-limit pages. Returns reason string or None."""
    if "频繁访问" in html_text or "访问过于频繁" in html_text:
        return "访问过于频繁，被网站限流（请稍后重试或减少关键词数量）"
    if "验证码" in html_text or "captcha" in html_text.lower():
        return "触发验证码，需人工介入"
    if "请开启JavaScript" in html_text:
        return "网站要求启用JavaScript"
    if len(html_text) < 500 and ("error" in html_text.lower() or "错误" in html_text):
        return "网站返回错误页面"
    return None


def get_crawl_config():
    """读取采集配置：多来源 URL、首次回溯天数、抽取上限、关键词过滤开关、上次采集时间点。"""
    from app.models import SystemConfig
    configs = {c.key: c.value for c in SystemConfig.query.all()}

    sources = []
    raw_sources = configs.get('crawl_sources', '')
    if raw_sources:
        try:
            parsed = json.loads(raw_sources)
            if isinstance(parsed, list):
                for s in parsed:
                    if isinstance(s, dict) and s.get('url'):
                        sources.append({
                            "name": str(s.get('name') or s['url']),
                            "url": str(s['url']).strip(),
                            "enabled": bool(s.get('enabled', True)),
                        })
        except (json.JSONDecodeError, TypeError):
            for u in str(raw_sources).replace('，', ',').split(','):
                u = u.strip()
                if u:
                    sources.append({"name": u, "url": u, "enabled": True})
    if not sources:
        sources = [
            {"name": "中国政府采购网-中央公告", "url": "https://www.ccgp.gov.cn/cggg/zygg/", "enabled": True},
            {"name": "中国政府采购网-地方公告", "url": "https://www.ccgp.gov.cn/cggg/dfgg/", "enabled": True},
        ]

    try:
        days = max(1, min(30, int(configs.get('crawl_days', '7') or 7)))
    except (TypeError, ValueError):
        days = 7
    try:
        limit = max(1, min(50, int(configs.get('crawl_limit', '5') or 5)))
    except (TypeError, ValueError):
        limit = 5
    keyword_filter = configs.get('crawl_keyword_filter', '1') != '0'
    last_crawl_at = None
    raw_at = configs.get('last_crawl_at', '')
    if raw_at:
        try:
            last_crawl_at = datetime.strptime(str(raw_at)[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            last_crawl_at = None
    return {
        "sources": sources, "days": days, "limit": limit,
        "keyword_filter": keyword_filter, "last_crawl_at": last_crawl_at,
    }


# SKIP_TYPES 不再过滤：各类公告（含中标/成交/更正）均采集，由人工判断。

# 政府采购网搜索接口
SEARCH_BASE = "https://search.ccgp.gov.cn/bxsearch"


def _build_search_url(kw, start_date, end_date, page_index=1, bid_type=0):
    """构建政府采购网搜索URL。日期格式：2026:08:19（接口要求冒号分隔）。"""
    from urllib.parse import quote
    start = start_date.strftime("%Y:%m:%d")
    end = end_date.strftime("%Y:%m:%d")
    return (
        f"{SEARCH_BASE}?searchtype=1&page_index={page_index}"
        f"&bidSort=0&bidType={bid_type}&dbselect=bidx"
        f"&kw={quote(kw)}&start_time={start}&end_time={end}"
        f"&timeType=1&displayZone=&zoneId=&pppStatus=0&agentName="
    )


def parse_search_item(li):
    """解析搜索结果 li（ul.vT-srch-result-list-bid 下的项），返回 dict 或 None。

    每条结构：<a>标题</a> <p>摘要</p> <span>日期|采购人|代理  公告类型|地区</span>
    """
    a = li.find("a")
    if not a:
        return None
    title = a.get_text(strip=True)
    href = a.get("href", "")
    if not title or len(title) < 5 or not href:
        return None
    p = li.find("p")
    summary = p.get_text(" ", strip=True) if p else ""
    span = li.find("span")
    span_text = span.get_text(" ", strip=True) if span else ""
    # 日期：2026.08.21 23:46:51
    m_date = re.search(r"(\d{4}\.\d{2}\.\d{2})", span_text)
    dt = None
    if m_date:
        try:
            dt = datetime.strptime(m_date.group(1), "%Y.%m.%d")
        except ValueError:
            dt = None
    # 采购人
    m_buyer = re.search(r"采购人[：:]\s*(.*?)(?=\s*\|)", span_text)
    purchaser = m_buyer.group(1).strip() if m_buyer else ""
    # 公告类型（<strong> 标签）；部分条目无 span/strong，需判空防止解析中断
    atype = ""
    if span:
        strong = span.find("strong")
        if strong:
            atype = strong.get_text(strip=True)
    # 地区（公告类型后的 | 地区）：parts[2] 常混入"代理机构：xxx 公告类型"，取其后的纯地区段，否则留空走正文兜底
    parts = [s.strip() for s in span_text.split("|")]
    region = parts[2] if len(parts) >= 3 else ""
    if "代理机构" in region or "公告" in region:
        region = parts[3] if len(parts) >= 4 and parts[3] else ""
    return {
        "title": title,
        "url": href,
        "dt": dt,
        "date": m_date.group(1) if m_date else None,
        "purchaser": purchaser,
        "type": atype,
        "region": region,
        "summary": summary,
    }


def fetch_search_results(kw, start_date, end_date, session, max_pages=2):
    """按关键词搜索政府采购网，翻页采集。返回 (items, error)。"""
    items = []
    for page in range(1, max_pages + 1):
        url = _build_search_url(kw, start_date, end_date, page_index=page)
        try:
            resp = session.get(url, timeout=20)
            resp.encoding = resp.apparent_encoding or "utf-8"
            if resp.status_code != 200:
                return items, f"HTTP {resp.status_code}"
            # 搜索接口反爬检测：只检测"频繁访问"（正常页面注释中含"验证码"字样，不能用作判据）
            if "频繁访问" in resp.text or "访问过于频繁" in resp.text:
                return items, "访问过于频繁，被网站限流（请稍后重试）"
            soup = BeautifulSoup(resp.text, "html.parser")
            ul = soup.find("ul", class_="vT-srch-result-list-bid")
            if not ul:
                return items, ""  # 无结果或结构变化，不算错误
            page_items = []
            for li in ul.find_all("li"):
                item = parse_search_item(li)
                if item:
                    page_items.append(item)
            if not page_items:
                break
            items.extend(page_items)
            time.sleep(REQUEST_DELAY)  # 翻页间延迟，避免反爬
        except Exception as e:
            return items, f"请求异常: {str(e)[:80]}"
    return items, ""


def fetch_detail_text(url, session):
    """抓取公告详情页并清洗为纯文本。"""
    resp = session.get(url, timeout=20)
    resp.encoding = resp.apparent_encoding or "utf-8"
    if resp.status_code != 200:
        raise RuntimeError(f"详情页 HTTP {resp.status_code}")
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return text[:8000]


def extract_contact_rules(text):
    """规则兜底：从公告文本提取 联系人/电话/地址/采购单位（AI 未抽到时使用）。"""
    contact = phone = address = purchaser = ""
    m = re.search(r"项目联系人\s*([\u4e00-\u9fa5·]{2,8})\s*项目联系电话\s*([0-9\-—()（）\s]{5,30})", text)
    if m:
        contact, phone = m.group(1), m.group(2)
    if not contact:
        m = re.search(r"联系人[:：]?\s*([\u4e00-\u9fa5·]{2,8})\s*电话[:：]?\s*([0-9\-—()（）\s]{5,30})", text)
        if m:
            contact, phone = m.group(1), m.group(2)
    if not contact:
        m = re.search(r"项目联系人[:：]\s*([\u4e00-\u9fa5·]{2,8})", text)
        if m:
            contact = m.group(1)
    if not phone:
        m = re.search(r"项目联系电话[:：]?\s*([0-9\-—()（）\s]{5,30})", text)
        if m:
            phone = m.group(1)
    m = re.search(r"采购单位地址[:：]?\s*([^\s，。；,]{4,60})", text)
    if m:
        address = m.group(1)
    m = re.search(r"采购单位[:：]?\s*([\u4e00-\u9fa5（）()]{4,50}?)(?=\s|$)", text)
    if m:
        purchaser = m.group(1)
    return {
        "contact_name": re.sub(r"\s+", "", contact),
        "contact_phone": re.sub(r"[^\d-]", "", phone),
        "address": address,
        "purchaser": purchaser,
    }


def extract_winner(text):
    """从中标/成交公告文本提取中标单位名称（AI 未抽到时的规则兜底）。"""
    for p in [
        r"中标（成交）供应商(?:名称)?[:：]\s*([\u4e00-\u9fa5（）()·A-Za-z0-9\-]{4,60})",
        r"(?:中标|成交)(?:供应商|单位)(?:名称)?[:：]\s*([\u4e00-\u9fa5（）()·A-Za-z0-9\-]{4,60})",
        r"供应商名称[:：]\s*([\u4e00-\u9fa5（）()·A-Za-z0-9\-]{4,60})",
    ]:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return ""


def _update_status(**kw):
    _crawl_status.update(kw)


def run_crawl(app=None):
    """搜索接口采集：按关键词+时间范围搜索 → 详情页 → AI 抽取 → 生成线索。
    返回 (count, errors)。"""
    cfg = get_crawl_config()
    errors = []
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        session.get("https://www.ccgp.gov.cn/", timeout=15)
        time.sleep(2)  # 主页与搜索间留间隔，降低反爬触发概率
    except Exception:
        pass

    # 计算搜索时间范围：增量采集从检查点开始，首次回溯最近 N 天
    now = datetime.now()
    checkpoint = cfg["last_crawl_at"]
    if checkpoint:
        start_date = checkpoint
    else:
        start_date = now - timedelta(days=cfg["days"])
    end_date = now

    # 按关键词搜索政府采购网
    keywords = get_crawl_keywords()
    _update_status(phase="关键词搜索", total=len(keywords), current=",".join(keywords))
    candidates = []
    seen_urls = set()
    for kw in keywords:
        _update_status(current=f"搜索关键词: {kw}")
        try:
            results, err = fetch_search_results(kw, start_date, end_date, session)
            if err:
                errors.append(f"[关键词:{kw}] {err}")
            for it in results:
                if it["url"] not in seen_urls:
                    seen_urls.add(it["url"])
                    it["source_name"] = f"搜索:{kw}"
                    candidates.append(it)
            if not results and not err:
                errors.append(f"[关键词:{kw}] 搜索结果为0条")
        except Exception as e:
            errors.append(f"[关键词:{kw}] 搜索失败: {str(e)[:100]}")
        time.sleep(REQUEST_DELAY)

    # 按时间倒序；已入库 URL 先剔除（避免重复项占用抽取上限，回溯重采时能捞到漏网新公告），再取 limit 条
    candidates = [it for it in candidates if it.get("dt")]
    existing_urls = {u for (u,) in db.session.query(Lead.source_url).all() if u}
    candidates = [it for it in candidates if it["url"] not in existing_urls]
    candidates.sort(key=lambda it: it["dt"], reverse=True)
    filtered = candidates[: cfg["limit"]]

    _update_status(phase="AI抽取", total=len(filtered), count=0, errors=errors)
    if checkpoint:
        _update_status(message=f"增量采集：从 {checkpoint.strftime('%Y-%m-%d %H:%M')} 起，搜索到 {len(candidates)} 条候选")
        _crawl_status["from_at"] = checkpoint.strftime("%Y-%m-%d %H:%M")
    count = 0
    for idx, item in enumerate(filtered, 1):
        _update_status(progress=idx, current=item["title"][:60])
        try:
            # 候选列表已按 existing_urls + seen_urls 去重，无需再逐条查库
            page_text = fetch_detail_text(item["url"], session)
            ai = extract_lead(item["title"], page_text, item["url"], item.get("type",""))
            rules = extract_contact_rules(page_text)
            for f in ("contact_name", "contact_phone", "address", "purchaser"):
                if not ai.get(f) and rules.get(f):
                    ai[f] = rules[f]
            budget = ai["budget"]
            if budget is None:
                budget = extract_budget(page_text)
            deadline = ai["deadline"]
            if deadline:
                try:
                    deadline = datetime.strptime(str(deadline)[:10], "%Y-%m-%d")
                except ValueError:
                    deadline = None
            region = resolve_region(
                ai.get("address"), ai.get("region"), ai.get("purchaser"),
                item.get("region"), item["title"], page_text[:3000],
            ) or item.get("region") or extract_region(page_text)
            winner = (ai.get("winner") or extract_winner(page_text) or "").strip()
            summary = extract_notice_summary(page_text) or ai["summary"]
            service = "；".join(
                f"{k}: {v}" for k, v in [
                    ("公告概要", summary), ("客户方", ai["purchaser"]),
                    ("中标/成交单位", winner),
                    ("联系人", ai["contact_name"]),
                    ("联系方式", ai["contact_phone"]), ("地址", ai["address"]),
                    ("预算", budget),
                ] if v
            )
            lead = Lead(
                title=ai["title"][:500],
                budget=str(budget) if budget else "",
                deadline=deadline,
                region=region,
                purchaser=ai["purchaser"],
                contact_name=(ai["contact_name"] or "")[:100],
                contact_phone=(ai["contact_phone"] or "")[:100],
                address=(ai["address"] or "")[:300],
                service_content=service,
                source_url=item["url"],
                source_platform=item.get("source_name", "中国政府采购网"),
                bid_type=(item.get("type") or "")[:50],
                winner=winner[:200] if winner else "",
                created_at=item["dt"],
                status="active",
                full_text=(page_text or "")[:60000],
            )
            lead.serial_no = gen_serial(item["dt"])
            match_lead(lead)
            db.session.add(lead)
            count += 1
            _update_status(count=count)
        except Exception as e:
            errors.append(f"[{item['title'][:30]}] {str(e)[:120]}")
        time.sleep(1)

    # 统一提交：避免逐条 commit 的 I/O 开销，且失败条目不影响已成功条目入库
    if count > 0:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            errors.append(f"批量入库失败: {str(e)[:120]}")
            count = 0

    _update_status(phase="完成", count=count, errors=errors)
    # 记录本次采集时间点，供下次增量采集使用（仅在有新线索成功入库时推进，
    # 防止 AI 全部抽取失败时检查点空转、漏掉本批次公告）
    if count > 0:
        ts = now.strftime("%Y-%m-%d %H:%M")
        store = SystemConfig.query.filter_by(key='last_crawl_at').first()
        if store:
            store.value = ts
        else:
            store = SystemConfig(key='last_crawl_at', value=ts, description='上次采集时间点(增量采集)')
            db.session.add(store)
        db.session.commit()
    return count, errors


_crawl_status = {
    "running": False, "phase": "", "progress": 0, "total": 0,
    "current": "", "count": 0, "errors": [], "message": "",
    "started_at": None, "finished_at": None,
}


def start_crawl_background(app):
    """后台线程执行采集，避免 AI 抽取长时间阻塞请求。"""
    import threading
    if _crawl_status["running"]:
        return False
    _crawl_status.update({
        "running": True, "phase": "准备中", "progress": 0, "total": 0,
        "current": "", "count": 0, "errors": [], "message": "",
        "from_at": "",
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "finished_at": None,
    })
    threading.Thread(target=_crawl_worker, args=(app,), daemon=True).start()
    return True


def _crawl_worker(app):
    try:
        with app.app_context():
            count, errors = run_crawl(app)
            extra = f"（自 {_crawl_status.get('from_at', '首次/回溯')} 起）" if _crawl_status.get("from_at") else ""
            _crawl_status.update({
                "message": f"采集完成，新增 {count} 条线索{extra}" + (f"（{len(errors)} 个异常）" if errors else ""),
            })
    except Exception as e:
        _crawl_status.update({"message": f"采集失败: {str(e)[:200]}"})
    finally:
        _crawl_status.update({"running": False, "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


def get_crawl_status():
    return dict(_crawl_status)
