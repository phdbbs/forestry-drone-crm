#!/usr/bin/env python3
"""
UNIT — 服务层单元测试

覆盖 services 下各模块的纯逻辑与容错分支：关键词匹配、流水号、
行政区划解析、爬虫解析/兜底提取、AI 客户端 JSON 容错、新闻采集。
所有外部依赖（HTTP、AI）全部打桩，可离线运行。

用法：
    pytest tests/test_services.py -v
    python tests/test_services.py
"""
import json
import os
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ═══════════════════════════════════════════════════════════════
# UNIT-01 线索匹配度（services/matcher.py）
# ═══════════════════════════════════════════════════════════════


class TestMatcher:
    def _lead(self, title, content=''):
        return SimpleNamespace(title=title, service_content=content,
                               match_keywords=None, match_level=None,
                               match_score=None, match_reason=None)

    def test_unit_01_001_high_match(self):
        """UNIT-01-001 命中高匹配关键词且无低匹配词 → 高匹配。"""
        from app.services.matcher import match_lead
        lead = self._lead('无人机飞行检查项目', '航拍核查服务')
        match_lead(lead)
        assert lead.match_level == '高匹配'
        assert 70 <= lead.match_score <= 95
        assert '高匹配关键词' in lead.match_reason

    def test_unit_01_002_low_match(self):
        """UNIT-01-002 仅命中低匹配关键词 → 低匹配。"""
        from app.services.matcher import match_lead
        lead = self._lead('林木砍伐清运项目', '消杀施工')
        match_lead(lead)
        assert lead.match_level == '低匹配'
        assert 15 <= lead.match_score <= 30

    def test_unit_01_003_medium_match(self):
        """UNIT-01-003 仅命中通用关键词 → 中匹配。"""
        from app.services.matcher import match_lead
        lead = self._lead('林业监测服务', '森林资源调查')
        match_lead(lead)
        assert lead.match_level == '中匹配'
        assert 40 <= lead.match_score <= 75

    def test_unit_01_004_high_and_low_conflict(self):
        """UNIT-01-004 同时含高/低匹配关键词时降级为中匹配（避免误判高价值）。"""
        from app.services.matcher import match_lead
        lead = self._lead('无人机飞行检查与林木砍伐项目', '清运施工')
        match_lead(lead)
        assert lead.match_level == '中匹配'

    def test_unit_01_005_no_match(self):
        """UNIT-01-005 无任何关键词命中 → 低匹配且分数为 10。"""
        from app.services.matcher import match_lead
        lead = self._lead('办公用品采购项目')
        match_lead(lead)
        assert lead.match_level == '低匹配'
        assert lead.match_score == 10
        assert lead.match_keywords == ''

    def test_unit_01_006_score_capped(self):
        """UNIT-01-006 分数不超过上限 95 / 不低于 15。"""
        from app.services.matcher import match_lead
        lead = self._lead('无人机飞行检查 无人机林区巡检 航拍核查 林区审计 AI病虫害算法识别 无人机巡检',
                          '松材线虫病防治 林业病虫害监测 林业航拍核查 林区审计巡检 森林 防治 监测')
        match_lead(lead)
        assert lead.match_score <= 95

    def test_unit_01_007_keywords_joined(self):
        """UNIT-01-007 命中关键词以逗号连接写入 match_keywords。"""
        from app.services.matcher import match_lead
        lead = self._lead('无人机巡检项目')
        match_lead(lead)
        assert '无人机巡检' in lead.match_keywords
        assert ',' in lead.match_keywords


# ═══════════════════════════════════════════════════════════════
# UNIT-02 线索流水号（services/serial.py）
# ═══════════════════════════════════════════════════════════════


class TestSerial:
    @pytest.mark.parametrize('year,expected', [
        (2026, '6'), (2029, '9'), (2030, '0'), (2031, 'a'), (2032, 'b'),
    ])
    def test_unit_02_001_year_char(self, year, expected):
        """UNIT-02-001 年份字符编码规则。"""
        from app.services.serial import _year_char
        assert _year_char(year) == expected

    @pytest.mark.parametrize('month,expected', [
        (1, '1'), (9, '9'), (10, '0'), (11, 'N'), (12, 'D'),
    ])
    def test_unit_02_002_month_char(self, month, expected):
        """UNIT-02-002 月份字符编码规则（10→0 / 11→N / 12→D）。"""
        from app.services.serial import _MONTH_CHARS
        assert _MONTH_CHARS[month] == expected

    def test_unit_02_003_prefix_format(self, app):
        """UNIT-02-003 流水号 = 年1 + 月1 + 日2 + 流水2。"""
        from app.services.serial import gen_serial
        with app.app_context():
            serial = gen_serial(datetime(2026, 9, 13))
            assert serial.startswith('6913')
            assert len(serial) == 6

    def test_unit_02_004_increments_same_day(self, app):
        """UNIT-02-004 同日多次生成流水号递增。"""
        from app import db
        from app.models import Lead
        from app.services.serial import gen_serial
        from crm_test_utils import wipe_all
        with app.app_context():
            # 线索被商机 lead_id 外键引用，必须按依赖顺序清库（SQLite 已开启外键校验）
            wipe_all(db.session)
            first = gen_serial(datetime(2026, 9, 13))
            db.session.add(Lead(title='x', serial_no=first))
            db.session.commit()
            second = gen_serial(datetime(2026, 9, 13))
            assert first.endswith('01') and second.endswith('02')

    def test_unit_02_005_december(self, app):
        """UNIT-02-005 12 月流水号前缀为 D。"""
        from app.services.serial import gen_serial
        with app.app_context():
            assert gen_serial(datetime(2026, 12, 1)).startswith('6D01')


# ═══════════════════════════════════════════════════════════════
# UNIT-03 行政区划解析（services/regions.py）
# ═══════════════════════════════════════════════════════════════


class TestRegions:
    def test_unit_03_001_extract_candidates(self):
        """UNIT-03-001 从完整地址提取省/市/县候选。"""
        from app.services.regions import _extract_candidates
        prov, city, county = _extract_candidates('浙江省丽水市松阳县')
        assert prov == '浙江省'
        assert city == '丽水市'
        assert county == '松阳县'

    def test_unit_03_002_resolve_full(self):
        """UNIT-03-002 解析为「省简称+市简称+县区简称」。"""
        from app.services.regions import resolve_region
        result = resolve_region('浙江省丽水市松阳县')
        assert result == '浙江丽水松阳'

    def test_unit_03_003_resolve_province_only(self):
        """UNIT-03-003 只有省份时返回省份简称。"""
        from app.services.regions import resolve_region
        assert resolve_region('本项目建设地点在福建省') == '福建'

    def test_unit_03_004_resolve_empty(self):
        """UNIT-03-004 无有效行政区划时返回空字符串。"""
        from app.services.regions import resolve_region
        assert resolve_region('', None, '无地名文本') == ''

    def test_unit_03_005_priority_order(self):
        """UNIT-03-005 多来源按优先级取第一个命中。"""
        from app.services.regions import resolve_region
        assert resolve_region('山东省威海市荣成市', '浙江省') == '山东威海荣成'

    def test_unit_03_006_duplicate_city_county(self):
        """UNIT-03-006 市县同名去重（黄山市黄山区 → 安徽黄山，而非安徽黄山黄山）。"""
        from app.services.regions import resolve_region
        result = resolve_region('安徽省黄山市黄山区')
        assert result == '安徽黄山'
        assert result.count('黄山') == 1

    def test_unit_03_007_city_only_no_county(self):
        """UNIT-03-007 只有省+市、无县区时不得丢失市级（回归：城市正则曾吞掉省名）。"""
        from app.services.regions import _extract_candidates, resolve_region
        assert _extract_candidates('山东省威海市')[1] == '威海市'
        assert resolve_region('山东省威海市') == '山东威海'
        assert resolve_region('项目位于浙江省杭州市') == '浙江杭州'

    def test_unit_03_008_province_not_swallowed(self):
        """UNIT-03-008 省份候选不受前文干扰（回归：曾匹配出"设地点在福建省"）。"""
        from app.services.regions import _extract_candidates, resolve_region
        assert _extract_candidates('本项目建设地点在福建省')[0] == '福建省'
        assert _extract_candidates('内蒙古自治区呼和浩特市新城区')[0] == '内蒙古自治区'
        assert resolve_region('本项目建设地点在福建省') == '福建'


# ═══════════════════════════════════════════════════════════════
# UNIT-04 爬虫解析与兜底提取（services/crawler.py）
# ═══════════════════════════════════════════════════════════════


class TestCrawlerHelpers:
    def test_unit_04_001_extract_budget(self):
        """UNIT-04-001 预算提取支持三种常见写法。"""
        from app.services.crawler import extract_budget
        assert extract_budget('预算金额：150万元') == '150'
        assert extract_budget('项目预算：1,200') == '1,200'
        assert extract_budget('总预算：88') == '88'
        assert extract_budget('无预算信息') == ''

    def test_unit_04_002_extract_region(self):
        """UNIT-04-002 省份简易提取。"""
        from app.services.crawler import extract_region
        assert extract_region('项目位于浙江省杭州市') == '浙江'
        assert extract_region('无地名') == ''

    def test_unit_04_003_extract_region_full(self):
        """UNIT-04-003 完整地区提取：地址优先于标题兜底。"""
        from app.services.crawler import extract_region_full
        assert extract_region_full('采购单位地址：安徽省合肥市庐阳区') == '安徽省合肥市庐阳区'
        assert extract_region_full('山东省威海市某项目', '威海市林业局') == '山东省威海市'

    def test_unit_04_003b_extract_region_full_consistent_format(self):
        """UNIT-04-003b 省份一律输出全称，不出现"山东威海市"这类简称/全称混排。"""
        from app.services.crawler import extract_region_full
        assert extract_region_full('项目位于四川省成都市', '成都市林业局') == '四川省成都市'
        assert extract_region_full('行政区域：内蒙古 项目', '呼和浩特市林业局') == '内蒙古自治区呼和浩特市'
        assert extract_region_full('采购单位地址：重庆市万州区') == '重庆市万州区'
        assert extract_region_full('采购单位地址：北京市通州区') == '北京市通州区'
        assert extract_region_full('采购单位地址：浙江省杭州市余杭区') == '浙江省杭州市余杭区'

    def test_unit_04_003c_province_full(self):
        """UNIT-04-003c 省份简称补全规则（省/自治区/直辖市）。"""
        from app.services.crawler import province_full
        assert province_full('山东') == '山东省'
        assert province_full('内蒙古') == '内蒙古自治区'
        assert province_full('广西') == '广西壮族自治区'
        assert province_full('新疆') == '新疆维吾尔自治区'
        assert province_full('北京') == '北京市'
        assert province_full('重庆市') == '重庆市'
        assert province_full('') == ''

    def test_unit_04_004_extract_deadline(self):
        """UNIT-04-004 截止日期提取支持 - / 年月日 三种分隔。"""
        from app.services.crawler import extract_deadline
        assert extract_deadline('截止时间 2026-08-19') == datetime(2026, 8, 19)
        assert extract_deadline('2026/8/19 开标') == datetime(2026, 8, 19)
        assert extract_deadline('2026年8月19日') == datetime(2026, 8, 19)
        assert extract_deadline('无日期') is None

    def test_unit_04_005_detect_antibot(self):
        """UNIT-04-005 反爬/限流页面识别。"""
        from app.services.crawler import detect_antibot
        assert '频繁' in detect_antibot('访问过于频繁，请稍后再试')
        assert '验证码' in detect_antibot('请输入验证码')
        assert 'JavaScript' in detect_antibot('请开启JavaScript')
        assert detect_antibot('正常页面内容' * 200) is None

    def test_unit_04_006_extract_contact_rules(self):
        """UNIT-04-006 联系人/电话/地址规则兜底提取。"""
        from app.services.crawler import extract_contact_rules
        text = ('项目联系人：王小明 项目联系电话：0571-12345678 '
                '采购单位地址：杭州市西湖区体育场路 采购单位：浙江省林业局')
        result = extract_contact_rules(text)
        assert result['contact_name'] == '王小明'
        assert '0571-12345678' in result['contact_phone']
        assert '杭州市西湖区' in result['address']

    def test_unit_04_007_extract_contact_rules_empty(self):
        """UNIT-04-007 无匹配内容时返回空值不报错。"""
        from app.services.crawler import extract_contact_rules
        result = extract_contact_rules('')
        assert result == {'contact_name': '', 'contact_phone': '',
                          'address': '', 'purchaser': ''}

    def test_unit_04_008_extract_winner(self):
        """UNIT-04-008 中标单位提取三种写法。"""
        from app.services.crawler import extract_winner
        assert extract_winner('中标（成交）供应商名称：某某科技有限公司') == '某某科技有限公司'
        assert extract_winner('成交供应商：另一家公司') == '另一家公司'
        assert extract_winner('无中标信息') == ''

    def test_unit_04_009_extract_notice_summary(self):
        """UNIT-04-009 公告概要区块整理为「标签：值；」格式。"""
        from app.services.crawler import extract_notice_summary
        text = ('公告概要\n采购项目名称\n无人机巡检服务\n采购单位\n浙江省林业局\n'
                '预算金额\n150万元\n项目概况\n本项目采用无人机巡检。')
        summary = extract_notice_summary(text)
        assert '采购项目名称：无人机巡检服务' in summary
        assert '采购单位：浙江省林业局' in summary
        assert '项目概况' not in summary

    def test_unit_04_010_extract_notice_summary_missing(self):
        """UNIT-04-010 无「公告概要」时返回空字符串。"""
        from app.services.crawler import extract_notice_summary
        assert extract_notice_summary('正文没有概要区块') == ''
        assert extract_notice_summary('') == ''

    def test_unit_04_011_build_service_content(self):
        """UNIT-04-011 概要优先拼装 service_content，空值字段被跳过。"""
        from app.services.crawler import build_service_content
        lead = SimpleNamespace(purchaser='浙江省林业局', winner='', contact_name='王处长',
                               contact_phone='', address='', budget='150')
        content = build_service_content(lead, '采购项目名称：无人机巡检')
        assert content.startswith('公告概要: 采购项目名称：无人机巡检')
        assert '客户方: 浙江省林业局' in content
        assert '联系人: 王处长' in content
        assert '预算: 150' in content
        assert '中标/成交单位' not in content

    def test_unit_04_012_build_search_url(self):
        """UNIT-04-012 搜索 URL 日期使用冒号分隔且关键词被编码。"""
        from app.services.crawler import _build_search_url
        url = _build_search_url('无人机', datetime(2026, 8, 19), datetime(2026, 8, 21))
        assert 'start_time=2026:08:19' in url
        assert 'end_time=2026:08:21' in url
        assert 'kw=%E6%97%A0%E4%BA%BA%E6%9C%BA' in url

    def test_unit_04_013_parse_search_item(self):
        """UNIT-04-013 搜索结果条目解析：标题/链接/日期/采购人/公告类型/地区。"""
        from app.services.crawler import parse_search_item
        html = ('<li><a href="/x/1.htm">浙江省林业局无人机巡检服务采购公告</a>'
                '<p>本项目采购无人机巡检服务</p>'
                '<span>2026.08.21 23:46:51|采购人：浙江省林业局|代理机构：某代理 '
                '<strong>公开招标</strong>|浙江省</span></li>')
        li = BeautifulSoup(html, 'html.parser').find('li')
        item = parse_search_item(li)
        assert item['title'].startswith('浙江省林业局')
        assert item['url'] == '/x/1.htm'
        assert item['dt'] == datetime(2026, 8, 21)
        assert item['purchaser'] == '浙江省林业局'
        assert item['type'] == '公开招标'

    def test_unit_04_014_parse_search_item_rejects_short(self):
        """UNIT-04-014 标题过短或无链接的条目被丢弃。"""
        from app.services.crawler import parse_search_item
        soup = BeautifulSoup('<li><a href="/x">短</a></li>', 'html.parser')
        assert parse_search_item(soup.find('li')) is None
        soup2 = BeautifulSoup('<li><a>没有链接的长标题文本</a></li>', 'html.parser')
        assert parse_search_item(soup2.find('li')) is None

    def test_unit_04_015_get_crawl_keywords_from_targets(self, app):
        """UNIT-04-015 关键词来源：优先启用站点的 keywords，其次 keywords 配置。"""
        from app import db
        from app.models import SystemConfig
        from app.services.crawler import get_crawl_keywords
        with app.app_context():
            SystemConfig.query.filter_by(key='crawl_targets').delete()
            SystemConfig.query.filter_by(key='keywords').delete()
            db.session.add(SystemConfig(key='crawl_targets', value=json.dumps([
                {'name': 'A', 'url': 'http://a', 'enabled': True, 'keywords': '甲,乙'},
                {'name': 'B', 'url': 'http://b', 'enabled': False, 'keywords': '丙'},
            ])))
            db.session.add(SystemConfig(key='keywords', value='乙,丁'))
            db.session.commit()
            assert get_crawl_keywords() == ['甲', '乙', '丁']

    def test_unit_04_016_get_crawl_keywords_default(self, app):
        """UNIT-04-016 无任何配置时返回内置默认关键词。"""
        from app import db
        from app.models import SystemConfig
        from app.services.crawler import get_crawl_keywords
        with app.app_context():
            SystemConfig.query.delete()
            db.session.commit()
            assert get_crawl_keywords() == ['无人机', '林业', '病虫害', '巡检']

    def test_unit_04_017_get_crawl_config_defaults(self, app):
        """UNIT-04-017 采集配置默认值与边界收敛（天数/条数）。"""
        from app import db
        from app.models import SystemConfig
        from app.services.crawler import get_crawl_config
        with app.app_context():
            SystemConfig.query.delete()
            db.session.commit()
            cfg = get_crawl_config()
            assert cfg['days'] == 7 and cfg['limit'] == 5
            assert len(cfg['sources']) == 2 and cfg['keyword_filter'] is True
            assert cfg['last_crawl_at'] is None
            # 越界值被夹取
            db.session.add_all([
                SystemConfig(key='crawl_days', value='999'),
                SystemConfig(key='crawl_limit', value='0'),
                SystemConfig(key='crawl_keyword_filter', value='0'),
                SystemConfig(key='last_crawl_at', value='2026-09-18 18:37'),
            ])
            db.session.commit()
            cfg = get_crawl_config()
            assert cfg['days'] == 30 and cfg['limit'] == 1
            assert cfg['keyword_filter'] is False
            assert cfg['last_crawl_at'] == datetime(2026, 9, 18, 18, 37)

    def test_unit_04_018_get_crawl_config_invalid(self, app):
        """UNIT-04-018 非法配置值回落到默认，不抛异常。"""
        from app import db
        from app.models import SystemConfig
        from app.services.crawler import get_crawl_config
        with app.app_context():
            SystemConfig.query.delete()
            db.session.add_all([
                SystemConfig(key='crawl_days', value='abc'),
                SystemConfig(key='crawl_limit', value=''),
                SystemConfig(key='last_crawl_at', value='不是时间'),
                SystemConfig(key='crawl_sources', value='not-json'),
            ])
            db.session.commit()
            cfg = get_crawl_config()
            assert cfg['days'] == 7 and cfg['limit'] == 5
            assert cfg['last_crawl_at'] is None
            # 非 JSON 时按逗号分隔的纯 URL 列表解析
            assert all(s['url'] for s in cfg['sources'])

    def test_unit_04_019_crawl_status_is_copy(self):
        """UNIT-04-019 采集状态接口返回副本，外部修改不影响内部状态。"""
        from app.services.crawler import get_crawl_status
        snapshot = get_crawl_status()
        snapshot['running'] = 'tampered'
        assert get_crawl_status()['running'] is not snapshot['running']

    def test_unit_04_020_start_guard(self, app):
        """UNIT-04-020 采集运行中时拒绝重复启动。"""
        from app.services.crawler import _crawl_status, start_crawl_background
        original = dict(_crawl_status)
        try:
            _crawl_status['running'] = True
            assert start_crawl_background(app) is False
        finally:
            _crawl_status.clear()
            _crawl_status.update(original)

    def test_unit_04_021_run_crawl_pipeline(self, app, monkeypatch):
        """UNIT-04-021 采集主流程：搜索 → 详情 → AI 抽取 → 入库 → 推进检查点。"""
        import requests

        from app import db
        from app.models import Lead, SystemConfig
        from app.services import crawler

        class FakeSession:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=None):
                raise RuntimeError('测试中不应发起真实网络请求')

        monkeypatch.setattr(requests, 'Session', FakeSession)
        monkeypatch.setattr(crawler.time, 'sleep', lambda s: None)
        monkeypatch.setattr(crawler, 'get_crawl_keywords', lambda: ['无人机'])
        monkeypatch.setattr(crawler, 'fetch_search_results', lambda *a, **k: ([{
            'title': 'AICS 采集到的无人机巡检公告', 'url': 'https://example.com/1.htm',
            'dt': datetime(2026, 9, 10), 'date': '2026.09.10',
            'purchaser': 'AICS 采集采购方', 'type': '公开招标',
            'region': '浙江省', 'summary': '摘要',
        }], ''))
        monkeypatch.setattr(crawler, 'fetch_detail_text',
                            lambda url, session: '公告概要\n采购项目名称\n无人机巡检\n采购单位\nAICS 采集采购方')
        monkeypatch.setattr(crawler, 'extract_lead', lambda *a, **k: {
            'title': 'AICS 采集到的无人机巡检公告', 'purchaser': 'AICS 采集采购方',
            'contact_name': '王处长', 'contact_phone': '0571-1234', 'address': '杭州市',
            'region': '浙江省杭州市', 'budget': '150', 'deadline': '2026-10-01',
            'summary': '摘要', 'winner': '',
        })
        with app.app_context():
            Lead.query.filter_by(title='AICS 采集到的无人机巡检公告').delete()
            SystemConfig.query.filter_by(key='last_crawl_at').delete()
            db.session.commit()
            count, errors = crawler.run_crawl(app)
            assert count == 1 and errors == []
            lead = Lead.query.filter_by(title='AICS 采集到的无人机巡检公告').first()
            assert lead is not None
            assert lead.purchaser == 'AICS 采集采购方'
            assert lead.source_url == 'https://example.com/1.htm'
            assert lead.match_level == '高匹配'
            assert lead.serial_no
            # 增量检查点被推进
            assert SystemConfig.query.filter_by(key='last_crawl_at').first() is not None
            # 状态机回到完成态
            assert crawler.get_crawl_status()['phase'] == '完成'

    def test_unit_04_022_run_crawl_dedup(self, app, monkeypatch):
        """UNIT-04-022 已入库 URL 不会重复采集。"""
        import requests

        from app import db
        from app.models import Lead
        from app.services import crawler

        class FakeSession:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=None):
                raise RuntimeError('不应联网')

        monkeypatch.setattr(requests, 'Session', FakeSession)
        monkeypatch.setattr(crawler.time, 'sleep', lambda s: None)
        monkeypatch.setattr(crawler, 'get_crawl_keywords', lambda: ['无人机'])
        monkeypatch.setattr(crawler, 'fetch_search_results', lambda *a, **k: ([{
            'title': 'AICS 已存在的公告', 'url': 'https://example.com/dup.htm',
            'dt': datetime(2026, 9, 10), 'date': '2026.09.10',
            'purchaser': '', 'type': '', 'region': '', 'summary': '',
        }], ''))
        monkeypatch.setattr(crawler, 'fetch_detail_text', lambda url, session: '正文')
        monkeypatch.setattr(crawler, 'extract_lead', lambda *a, **k: {
            'title': 'x', 'purchaser': '', 'contact_name': '', 'contact_phone': '',
            'address': '', 'region': '', 'budget': None, 'deadline': None,
            'summary': '', 'winner': '',
        })
        with app.app_context():
            Lead.query.filter_by(source_url='https://example.com/dup.htm').delete()
            db.session.add(Lead(title='AICS 已存在的公告',
                                source_url='https://example.com/dup.htm', status='active'))
            db.session.commit()
            count, _ = crawler.run_crawl(app)
            assert count == 0


# ═══════════════════════════════════════════════════════════════
# UNIT-05 AI 客户端（services/ai_client.py）
# ═══════════════════════════════════════════════════════════════


class TestAIClient:
    def test_unit_05_001_extract_json_plain(self):
        """UNIT-05-001 解析纯 JSON。"""
        from app.services.ai_client import _extract_json
        assert _extract_json('{"a": 1}') == {'a': 1}

    def test_unit_05_002_extract_json_fenced(self):
        """UNIT-05-002 解析 ```json 围栏包裹的 JSON。"""
        from app.services.ai_client import _extract_json
        assert _extract_json('```json\n{"a": 2}\n```') == {'a': 2}

    def test_unit_05_003_extract_json_embedded(self):
        """UNIT-05-003 从解释性文字中提取 JSON 对象。"""
        from app.services.ai_client import _extract_json
        assert _extract_json('好的，结果如下：{"a": 3} 以上。') == {'a': 3}

    def test_unit_05_004_extract_json_invalid(self):
        """UNIT-05-004 空输出 / 非 JSON 输出抛出明确异常。"""
        from app.services.ai_client import _extract_json
        with pytest.raises(ValueError):
            _extract_json('')
        with pytest.raises(ValueError):
            _extract_json('完全不是 JSON')

    def test_unit_05_005_get_ai_config_defaults(self, app):
        """UNIT-05-005 AI 配置缺省值：本机 LM Studio 端点。"""
        from app import db
        from app.models import SystemConfig
        from app.services.ai_client import get_ai_config
        with app.app_context():
            SystemConfig.query.filter(SystemConfig.key.like('ai_%')).delete()
            db.session.commit()
            cfg = get_ai_config()
            assert cfg['endpoint'] == 'http://127.0.0.1:1234/v1'
            assert cfg['model'] == 'qwen3-14b-mlx'

    def test_unit_05_006_get_ai_config_configured(self, app):
        """UNIT-05-006 AI 配置读取并去除端点尾部斜杠。"""
        from app import db
        from app.models import SystemConfig
        from app.services.ai_client import get_ai_config
        with app.app_context():
            # seed 已写入 ai_* 配置键，必须 upsert 而非直接 add（system_config.key 唯一）
            for key, value in (('ai_api_endpoint', 'https://api.example.com/v1/'),
                               ('ai_model', 'AICS 模型'),
                               ('ai_api_key', 'sk-test')):
                row = SystemConfig.query.filter_by(key=key).first()
                if row:
                    row.value = value
                else:
                    db.session.add(SystemConfig(key=key, value=value))
            db.session.commit()
            cfg = get_ai_config()
            assert cfg['endpoint'] == 'https://api.example.com/v1'
            assert cfg['model'] == 'AICS 模型' and cfg['api_key'] == 'sk-test'

    def test_unit_05_007_chat_success(self, app, monkeypatch):
        """UNIT-05-007 chat 正常返回 assistant 内容。"""
        import requests

        from app.services import ai_client

        class FakeResp:
            status_code = 200
            text = ''

            def json(self):
                return {'choices': [{'message': {'content': '你好'}}]}

        monkeypatch.setattr(requests, 'post', lambda *a, **k: FakeResp())
        with app.app_context():
            assert ai_client.chat([{'role': 'user', 'content': 'hi'}]) == '你好'

    def test_unit_05_008_chat_http_error(self, app, monkeypatch):
        """UNIT-05-008 非 200 响应重试后抛出明确异常。"""
        import requests

        from app.services import ai_client

        class FakeResp:
            status_code = 500
            text = 'boom'

        monkeypatch.setattr(requests, 'post', lambda *a, **k: FakeResp())
        monkeypatch.setattr(ai_client.time, 'sleep', lambda s: None)
        with app.app_context():
            with pytest.raises(RuntimeError, match='HTTP 500'):
                ai_client.chat([{'role': 'user', 'content': 'hi'}])

    def test_unit_05_009_chat_bad_json(self, app, monkeypatch):
        """UNIT-05-009 响应非 JSON 时抛出明确异常。"""
        import requests

        from app.services import ai_client

        class FakeResp:
            status_code = 200
            text = 'not json'

            def json(self):
                raise ValueError('bad')

        monkeypatch.setattr(requests, 'post', lambda *a, **k: FakeResp())
        with app.app_context():
            with pytest.raises(RuntimeError, match='非 JSON'):
                ai_client.chat([{'role': 'user', 'content': 'hi'}])

    def test_unit_05_010_chat_connection_error(self, app, monkeypatch):
        """UNIT-05-010 连接失败重试后抛出异常（重试间隔已打桩）。"""
        import requests

        from app.services import ai_client

        def boom(*a, **k):
            raise ConnectionError('refused')

        monkeypatch.setattr(requests, 'post', boom)
        monkeypatch.setattr(ai_client.time, 'sleep', lambda s: None)
        with app.app_context():
            with pytest.raises(RuntimeError, match='AI 请求异常'):
                ai_client.chat([{'role': 'user', 'content': 'hi'}])

    def test_unit_05_011_extract_lead_normalization(self, app, monkeypatch):
        """UNIT-05-011 extract_lead 字段归一化：缺失字段补空、标题兜底。"""
        from app.services import ai_client
        monkeypatch.setattr(ai_client, 'chat', lambda *a, **k: json.dumps({
            'purchaser': ' 浙江省林业局 ', 'budget': None, 'deadline': None,
        }))
        with app.app_context():
            result = ai_client.extract_lead('兜底标题', '正文', 'https://e.com')
            assert result['title'] == '兜底标题'
            assert result['purchaser'] == '浙江省林业局'
            assert result['contact_name'] == '' and result['winner'] == ''
            assert result['budget'] is None

    def test_unit_05_012_generate_daily_plan(self, app, monkeypatch):
        """UNIT-05-012 每日方案生成：任务字段归一化 + 默认值兜底。"""
        from app.services import ai_client
        monkeypatch.setattr(ai_client, 'chat', lambda *a, **k: json.dumps({
            'date': '2026-09-18',
            'tasks': [
                {'type': 'contact', 'title': '联系王处长', 'content': '确认需求',
                 'priority': 'high', 'related': '浙江省林业局'},
                {'title': '缺少 type 的任务'},
                'not-a-dict',
            ],
        }))
        with app.app_context():
            plan = ai_client.generate_daily_plan()
            assert plan['date'] == '2026-09-18'
            assert len(plan['tasks']) == 2
            assert plan['tasks'][0]['type'] == 'contact'
            assert plan['tasks'][1]['type'] == 'followup'
            assert plan['tasks'][1]['priority'] == 'medium'

    def test_unit_05_013_generate_daily_plan_empty_tasks(self, app, monkeypatch):
        """UNIT-05-013 AI 未返回 tasks 时给出空列表而非报错。"""
        from app.services import ai_client
        monkeypatch.setattr(ai_client, 'chat', lambda *a, **k: '{}')
        with app.app_context():
            plan = ai_client.generate_daily_plan()
            assert plan['tasks'] == []


# ═══════════════════════════════════════════════════════════════
# UNIT-06 新闻/动态采集（services/news_collector.py）
# ═══════════════════════════════════════════════════════════════


class TestNewsCollector:
    def test_unit_06_001_parse_date(self):
        """UNIT-06-001 正文日期解析支持 - / 年月日。"""
        from app.services.news_collector import _parse_date
        assert _parse_date('发布于 2026-05-01') == datetime(2026, 5, 1)
        assert _parse_date('2026/05/01') == datetime(2026, 5, 1)
        assert _parse_date('2026年5月1日') == datetime(2026, 5, 1)
        assert _parse_date('无日期') is None

    def test_unit_06_002_summary_with(self):
        """UNIT-06-002 摘要围绕关键词截取。"""
        from app.services.news_collector import _summary_with
        text = '前文内容' * 20 + '王处长出席签约仪式' + '后文内容' * 20
        summary = _summary_with(text, '王处长', limit=60)
        assert '王处长' in summary and len(summary) <= 60

    def test_unit_06_003_ccgp_items(self):
        """UNIT-06-003 政府采购网列表解析（标题/绝对链接/发布时间）。"""
        from app.services.news_collector import _ccgp_items
        html = ('<ul><li><a href="/cggg/1.htm">浙江省林业局无人机巡检演练</a>'
                '发布时间：2026-05-01</li>'
                '<li><a href="/cggg/2.htm">短</a></li></ul>')
        items = _ccgp_items(html, 'https://www.ccgp.gov.cn/cggg/')
        assert len(items) == 1
        assert items[0]['url'] == 'https://www.ccgp.gov.cn/cggg/1.htm'
        assert items[0]['date'] == '2026-05-01'

    def test_unit_06_004_generic_items(self):
        """UNIT-06-004 通用列表解析：过滤脚本/图片/重复链接。"""
        from app.services.news_collector import _generic_items
        html = ('<a href="javascript:void(0)">脚本链接文本</a>'
                '<a href="/news/1.html">这是一条足够长的新闻标题</a>'
                '<a href="/img/a.png">这是一张图片的说明文字</a>'
                '<a href="/news/1.html">这是一条足够长的新闻标题</a>')
        items = _generic_items(html, 'https://example.com/')
        assert len(items) == 1
        assert items[0]['url'] == 'https://example.com/news/1.html'

    def test_unit_06_005_get_news_sources_default(self, app):
        """UNIT-06-005 新闻来源缺省为中国政府采购网中央/地方公告。"""
        from app import db
        from app.models import SystemConfig
        from app.services.news_collector import get_news_sources
        with app.app_context():
            SystemConfig.query.filter_by(key='news_sources').delete()
            db.session.commit()
            sources = get_news_sources()
            assert len(sources) == 2 and all(s['enabled'] for s in sources)

    def test_unit_06_006_sources_for_customer(self, app):
        """UNIT-06-006 采集来源追加客户官网。"""
        from app.models import Customer
        from app.services.news_collector import _sources_for
        with app.app_context():
            customer = Customer.query.filter(Customer.website.isnot(None)).first()
            names = [s['name'] for s in _sources_for(customer=customer)]
            assert any('官网' in n for n in names)

    def test_unit_06_007_collect_customer_news(self, app, monkeypatch):
        """UNIT-06-007 客户新闻采集：命中入库 + 联系人动态双关联 + 采集日志。"""
        import requests

        from app import db
        from app.models import Contact, ContactNews, CrawlLog, Customer, CustomerNews
        from app.services import news_collector as nc

        customer = None
        with app.app_context():
            customer = Customer.query.order_by(Customer.id).first()
            contact = Contact.query.filter_by(customer_id=customer.id).first()
            names = [customer.name] + ([customer.short_name] if customer.short_name else [])
            contact_name = contact.name if contact else ''

        list_html = ('<ul><li><a href="/cggg/1.htm">AICS 新闻：%s 无人机巡检演练</a>'
                     '发布时间：2026-05-01</li></ul>' % customer.name)
        detail_html = '<html><body>%s 与 %s 共同出席签约仪式，时间 2026-05-01</body></html>' % (
            customer.name, contact_name)

        class FakeResp:
            def __init__(self, text):
                self.text = text
                self.encoding = 'utf-8'
                self.apparent_encoding = 'utf-8'
                self.status_code = 200

        class FakeSession:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=None):
                return FakeResp('<html></html>')

        monkeypatch.setattr(requests, 'Session', FakeSession)

        def fake_fetch(url, session, timeout=20):
            # 列表页以 / 结尾 → 返回列表 HTML；详情页（如 /cggg/1.htm）→ 返回含联系人姓名的正文
            return FakeResp(list_html if url.endswith('/') else detail_html)

        monkeypatch.setattr(nc, '_fetch', fake_fetch)

        with app.app_context():
            CustomerNews.query.filter(CustomerNews.title.like('AICS 新闻%')).delete()
            ContactNews.query.delete()
            CrawlLog.query.filter_by(task_type='客户新闻').delete()
            db.session.commit()
            result = nc.collect_customer_news(customer.id)
            assert result['count'] >= 1
            news = CustomerNews.query.filter(CustomerNews.title.like('AICS 新闻%')).all()
            assert news and news[0].customer_id == customer.id
            assert news[0].source_name
            # 正文含联系人姓名 → 同时写入联系人动态
            assert ContactNews.query.filter_by(contact_id=contact.id).count() >= 1
            log = CrawlLog.query.filter_by(task_type='客户新闻').first()
            assert log is not None and log.items_count >= 1

    def test_unit_06_008_collect_contact_news(self, app, monkeypatch):
        """UNIT-06-008 联系人动态采集按姓名匹配。"""
        import requests

        from app import db
        from app.models import Contact, ContactNews
        from app.services import news_collector as nc

        with app.app_context():
            contact = Contact.query.order_by(Contact.id).first()
            name = contact.name

        list_html = '<ul><li><a href="/cggg/2.htm">AICS 动态：%s 调研林业工作</a>发布时间：2026-06-01</li></ul>' % name
        detail_html = '<html><body>%s 赴林区调研无人机巡检工作，时间 2026-06-01</body></html>' % name

        class FakeResp:
            def __init__(self, text):
                self.text = text
                self.encoding = 'utf-8'
                self.apparent_encoding = 'utf-8'
                self.status_code = 200

        class FakeSession:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=None):
                return FakeResp('<html></html>')

        monkeypatch.setattr(requests, 'Session', FakeSession)
        monkeypatch.setattr(nc, '_fetch', lambda url, session, timeout=20: FakeResp(
            list_html if 'cggg' in url else detail_html))

        with app.app_context():
            ContactNews.query.delete()
            db.session.commit()
            result = nc.collect_contact_news(contact.id)
            assert result['count'] >= 1
            news = ContactNews.query.filter_by(contact_id=contact.id).all()
            assert news and name in news[0].summary

    def test_unit_06_009_collect_all_kind_filter(self, app, monkeypatch):
        """UNIT-06-009 批量采集按 kind 过滤，未知 kind 不做任何采集。"""
        from app.services import news_collector as nc
        called = []
        monkeypatch.setattr(nc, 'collect_customer_news',
                            lambda cid: called.append(('customer', cid)) or {'count': 1, 'errors': []})
        monkeypatch.setattr(nc, 'collect_contact_news',
                            lambda cid: called.append(('contact', cid)) or {'count': 1, 'errors': []})
        with app.app_context():
            assert nc.collect_all('none') == {'count': 0, 'errors': []}
            assert called == []
            nc.collect_all('customer')
            assert called and all(k == 'customer' for k, _ in called)

    def test_unit_06_010_collect_error_logged(self, app, monkeypatch):
        """UNIT-06-010 采集过程异常被记录到日志而非抛出。"""
        import requests

        from app import db
        from app.models import CrawlLog, Customer
        from app.services import news_collector as nc

        class FakeSession:
            def __init__(self):
                self.headers = {}

            def get(self, url, timeout=None):
                raise ConnectionError('网络不可达')

        monkeypatch.setattr(requests, 'Session', FakeSession)
        monkeypatch.setattr(nc, '_fetch', lambda *a, **k: (_ for _ in ()).throw(
            ConnectionError('网络不可达')))
        with app.app_context():
            CrawlLog.query.filter_by(task_type='客户新闻').delete()
            db.session.commit()
            customer = Customer.query.order_by(Customer.id).first()
            result = nc.collect_customer_news(customer.id)
            assert result['count'] == 0 and result['errors']
            log = CrawlLog.query.filter_by(task_type='客户新闻').first()
            assert log.status == 'failed' and log.error_count >= 1


# ═══════════════════════════════════════════════════════════════
# UNIT-07 技能注册表与建议引擎
# ═══════════════════════════════════════════════════════════════


class TestSkillRegistryAndSuggestions:
    def test_unit_07_001_registry_builtin(self):
        """UNIT-07-001 内置技能注册齐全。"""
        from app.services.skills import SkillRegistry
        names = {s['name'] for s in SkillRegistry.get_all()}
        assert {'read_database', 'analyze_data', 'crawl_leads',
                'get_config', 'update_config'} <= names

    def test_unit_07_002_registry_unknown(self):
        """UNIT-07-002 未知技能返回 error 而非抛异常。"""
        from app.services.skills import SkillRegistry
        assert SkillRegistry.execute('nope') == {'error': 'Skill not found'}

    def test_unit_07_003_registry_exception_wrapped(self, app, monkeypatch):
        """UNIT-07-003 技能内部异常被包装为 error 字段。"""
        from app.services import skills
        monkeypatch.setattr(skills, '_read_db',
                            lambda: (_ for _ in ()).throw(RuntimeError('AICS 内部错误')))
        with app.app_context():
            result = skills.SkillRegistry.execute('read_database')
            assert 'AICS 内部错误' in result['error']

    def test_unit_07_004_stale_contact_suggestion(self, app):
        """UNIT-07-004 超过 14 天未联络的联系人产生 stale_contact 建议。"""
        from datetime import date, timedelta
        from app import db
        from app.models import Contact, FollowUp
        from app.services.suggestion_engine import generate_suggestions
        with app.app_context():
            contact = Contact(name='AICS 久未联络联系人')
            db.session.add(contact)
            db.session.flush()
            db.session.add(FollowUp(contact_id=contact.id,
                                    plan_date=date.today() - timedelta(days=30),
                                    content='AICS 历史计划'))
            db.session.commit()
            items = generate_suggestions()
            hit = [s for s in items if s['type'] == 'stale_contact'
                   and 'AICS 久未联络联系人' in s['title']]
            assert hit and hit[0]['priority'] == 'medium'

    def test_unit_07_005_priority_sorting(self, app):
        """UNIT-07-005 建议按优先级 high → medium → low 排序。"""
        from app.services.suggestion_engine import generate_suggestions
        with app.app_context():
            items = generate_suggestions()
            order = {'high': 0, 'medium': 1, 'low': 2}
            keys = [order[i['priority']] for i in items]
            assert keys == sorted(keys)


if __name__ == '__main__':
    raise SystemExit(pytest.main([os.path.abspath(__file__), '-v', '-p', 'no:cacheprovider']))
