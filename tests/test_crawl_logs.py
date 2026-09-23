"""采集日志与报错分类的单元/接口测试。

覆盖：
- error_classifier：原始报错 → 可识别类型（模型额度不足 / 网站反爬拒绝访问 …）
- crawl_log：start_log / finish_log 落库、mark_stale_logs 中断补记
- /api/crawl/logs 列表（筛选 + 统计）、详情、清空，/api/error-types 字典
"""
from datetime import datetime, timedelta

import pytest

from app import db
from app.models import CrawlLog
from app.services.error_classifier import classify_error, classify_record, summarize, taxonomy
from app.services.crawl_log import start_log, finish_log, mark_stale_logs


# ---------------------------------------------------------------------------
# 报错分类
# ---------------------------------------------------------------------------
class TestErrorClassifier:
    @pytest.mark.parametrize('raw,stage,expected', [
        # 模型侧
        ('AI 接口返回 HTTP 402: {"code":"insufficient_quota"}', 'AI抽取', 'ai_quota'),
        ('AI 接口返回 HTTP 400: 账户余额不足，请充值', 'AI抽取', 'ai_quota'),
        ('AI 接口返回 HTTP 401: Incorrect API key provided', 'AI抽取', 'ai_auth'),
        ('AI 接口返回 HTTP 429: rate limit exceeded', 'AI抽取', 'ai_rate_limit'),
        ('AI 请求异常: Connection refused', 'AI抽取', 'ai_unavailable'),
        ('AI 请求异常: Read timed out. (read timeout=240)', 'AI抽取', 'ai_timeout'),
        ('AI 输出无法解析为 JSON: 抱歉', 'AI抽取', 'ai_bad_response'),
        # 网站侧
        ('HTTP 403', '关键词搜索', 'antibot'),
        ('触发验证码，需人工介入', '详情抓取', 'web_captcha'),
        ('访问过于频繁，被网站限流（请稍后重试）', '关键词搜索', 'web_rate_limited'),
        ('详情页 HTTP 404', '详情抓取', 'not_found'),
        ('请求异常: Read timed out. (read timeout=20)', '关键词搜索', 'network_error'),
        ('搜索结果为0条', '关键词搜索', 'empty_result'),
        # 数据侧
        ('批量入库失败: (sqlite3.OperationalError) attempt to write a readonly database', '入库', 'db_error'),
        ('Something unexpected', '', 'unknown'),
    ])
    def test_classify_error(self, raw, stage, expected):
        assert classify_error(raw, stage)['code'] == expected

    def test_port_number_not_treated_as_status(self):
        """端口号 443 / 超时秒数 240 不能被当成 HTTP 状态码。"""
        v = classify_error('AI 请求异常: HTTPSConnectionPool(host=x, port=443): Read timed out.', 'ai')
        assert v['code'] == 'ai_timeout'

    def test_same_status_differs_by_stage(self):
        """同一个 403，模型侧是鉴权失败，网站侧是反爬拒绝。"""
        assert classify_error('AI 接口返回 HTTP 403: forbidden', 'ai')['code'] == 'ai_auth'
        assert classify_error('HTTP 403', 'web')['code'] == 'antibot'

    def test_labels_are_human_readable(self):
        assert classify_error('AI 接口返回 HTTP 402: insufficient_quota', 'ai')['label'] == '模型额度不足'
        assert classify_error('HTTP 403', 'web')['label'] == '网站反爬拒绝访问'

    def test_classify_record_and_summarize(self):
        recs = [
            classify_record({'stage': 'AI抽取', 'target': 'A', 'raw': 'AI 接口返回 HTTP 402: insufficient_quota'}),
            classify_record({'stage': 'AI抽取', 'target': 'B', 'raw': 'AI 接口返回 HTTP 402: insufficient_quota'}),
            classify_record({'stage': '关键词搜索', 'target': 'kw', 'raw': 'HTTP 403'}),
        ]
        assert recs[0]['code'] == 'ai_quota'
        summary = summarize(recs)
        assert summary[0] == {'code': 'ai_quota', 'label': '模型额度不足', 'category': '模型服务',
                              'severity': 'error', 'count': 2}
        assert len(summary) == 2

    def test_taxonomy_covers_named_types(self):
        labels = {t['label'] for t in taxonomy()}
        assert {'模型额度不足', '网站反爬拒绝访问', '模型鉴权失败'} <= labels
        for t in taxonomy():
            assert t['hint'], f'{t["code"]} 缺少处理建议'


# ---------------------------------------------------------------------------
# 日志落库
# ---------------------------------------------------------------------------
class TestCrawlLogStore:
    def test_start_and_finish_log(self, app):
        with app.app_context():
            log = start_log('线索采集', sources='中国政府采购网', keywords='无人机,林业',
                            range_start='2026-09-01 00:00', range_end='2026-09-23 09:00')
            assert log.id and log.status == 'running'

            res = finish_log(log, items_count=3, errors=[
                {'stage': 'AI抽取', 'target': '某项目', 'raw': 'AI 接口返回 HTTP 402: insufficient_quota'},
                {'stage': '关键词搜索', 'target': '关键词:无人机', 'raw': 'HTTP 403'},
            ], message='新增 3 条')

            assert res['status'] == 'partial'
            assert res['error_count'] == 2

            saved = CrawlLog.query.get(log.id)
            assert saved.status == 'partial'
            assert saved.items_count == 3
            assert saved.finished_at is not None
            assert saved.duration_ms >= 0
            # 报错已分类落库
            assert '模型额度不足' in saved.error_types
            assert '网站反爬拒绝访问' in saved.error_types
            assert 'insufficient_quota' in saved.error_detail

    def test_status_auto_all_failed(self, app):
        with app.app_context():
            log = start_log('线索采集')
            res = finish_log(log, items_count=0, errors=[{'stage': 'web', 'raw': 'HTTP 403'}])
            assert res['status'] == 'failed'

    def test_status_success_without_error(self, app):
        with app.app_context():
            log = start_log('线索采集')
            res = finish_log(log, items_count=5, errors=[])
            assert res['status'] == 'success'
            assert res['error_types'] == []

    def test_mark_stale_logs(self, app):
        with app.app_context():
            log = start_log('客户新闻')
            log.started_at = log.started_at - timedelta(minutes=30)
            db.session.commit()
            assert mark_stale_logs() == 1
            assert CrawlLog.query.get(log.id).status == 'interrupted'

    def test_recent_running_log_not_touched(self, app):
        with app.app_context():
            log = start_log('客户新闻')
            assert mark_stale_logs() == 0
            assert CrawlLog.query.get(log.id).status == 'running'


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------
class TestCrawlLogAPI:
    @pytest.fixture()
    def seeded(self, app):
        with app.app_context():
            log = start_log('线索采集', keywords='无人机', sources='中国政府采购网',
                            range_start='2026-09-01 00:00', range_end='2026-09-23 09:00')
            finish_log(log, items_count=4, errors=[
                {'stage': 'AI抽取', 'target': 'A项目', 'raw': 'AI 接口返回 HTTP 402: insufficient_quota'},
                {'stage': '关键词搜索', 'target': '关键词:林业', 'raw': '访问过于频繁，被网站限流'},
            ], message='新增 4 条线索')
            return log.id

    def test_list_with_stats(self, client, seeded):
        r = client.get('/api/crawl/logs?days=all').get_json()
        assert r['total'] >= 1
        assert r['items'][0]['id'] == seeded
        assert r['items'][0]['error_types'] and 'error_detail' not in r['items'][0]
        codes = {t['code'] for t in r['items'][0]['error_types']}
        assert {'ai_quota', 'web_rate_limited'} <= codes
        assert r['stats']['error_total'] >= 2
        assert r['stats']['by_status'].get('partial', 0) >= 1
        assert '线索采集' in r['task_types']

    def test_filter_by_error_code(self, client, seeded):
        r = client.get('/api/crawl/logs?error_code=ai_quota&days=all').get_json()
        assert r['total'] == 1 and r['items'][0]['id'] == seeded
        assert client.get('/api/crawl/logs?error_code=network_error&days=all').get_json()['total'] == 0

    def test_filter_by_status_and_task_type(self, client, seeded):
        assert client.get('/api/crawl/logs?status=partial&days=all').get_json()['total'] == 1
        assert client.get('/api/crawl/logs?task_type=线索采集&days=all').get_json()['total'] == 1
        assert client.get('/api/crawl/logs?task_type=客户新闻&days=all').get_json()['total'] == 0

    def test_filter_by_time_window(self, client, seeded, app):
        """today / days=1 的时间窗过滤。"""
        assert client.get('/api/crawl/logs?days=today').get_json()['total'] == 1
        with app.app_context():
            log = CrawlLog.query.get(seeded)
            log.started_at = datetime.now() - timedelta(days=30)
            db.session.commit()
        assert client.get('/api/crawl/logs?days=1').get_json()['total'] == 0
        assert client.get('/api/crawl/logs?days=today').get_json()['total'] == 0
        assert client.get('/api/crawl/logs?days=all').get_json()['total'] == 1

    def test_detail_includes_classified_errors(self, client, seeded):
        r = client.get(f'/api/crawl/logs/{seeded}').get_json()
        assert r['id'] == seeded
        assert len(r['error_detail']) == 2
        first = r['error_detail'][0]
        assert first['label'] == '模型额度不足'
        assert first['stage'] == 'AI抽取' and first['hint']
        assert first['retryable'] is False

    def test_daily_filter_and_delete(self, client, seeded):
        assert client.delete('/api/crawl/logs?days=7').get_json()['deleted'] == 0
        r = client.delete('/api/crawl/logs?days=all').get_json()
        assert r['ok'] and r['deleted'] >= 1
        assert client.get('/api/crawl/logs?days=all').get_json()['total'] == 0

    def test_error_types_dictionary(self, client):
        data = client.get('/api/error-types').get_json()
        assert isinstance(data, list) and len(data) >= 15
        assert {'code', 'label', 'category', 'severity', 'hint'} <= set(data[0].keys())

    def test_news_logs_backward_compatible(self, client, seeded):
        """旧的 /api/news/logs 仍可用，且字段与新接口对齐。"""
        data = client.get('/api/news/logs').get_json()
        assert isinstance(data, list) and data
        assert 'error_types' in data[0]
