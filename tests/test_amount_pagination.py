"""金额归一化 + 线索分页 + 数据库索引的回归测试。

对应 v3.1 优化：
* 写入侧：lead.budget / opportunity.amount 统一归一为 "N万" 规范串；
* 解析侧：analytics 汇总统一按万元口径（parse_amount_wan）；
* 分页：/api/leads 可选 page/page_size，向后兼容（不传参仍返回全量数组）；
* 索引：热列（status/created_at/source_url/FK/plan_date）建索引。
"""
import pytest
from sqlalchemy import text


def ok(r):
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


# ═══════════════════════════════════════════════════════════════
# 纯函数：amountutil
# ═══════════════════════════════════════════════════════════════

class TestAmountUtil:
    @pytest.mark.parametrize('raw,wan', [
        ('150万', 150.0),
        ('150万元', 150.0),
        ('1,500.50万元', 1500.5),      # 千分位 + 小数，旧正则会把 "1,500.50" 截成 "1"
        ('3亿', 30000.0),
        ('2.5亿元', 25000.0),
        ('500000元', 50.0),
        ('150', 150.0),                # 裸数字按行业惯例视为万元
        ('预算：1,200 万元', 1200.0),   # 带前缀/空格也能抽数
        ('人民币380万', 380.0),
        ('面议', None),
        ('', None),
        (None, None),
    ])
    def test_parse_amount_wan(self, raw, wan):
        from app.services.amountutil import parse_amount_wan
        assert parse_amount_wan(raw) == wan

    @pytest.mark.parametrize('raw,canon', [
        ('150万元', '150万'),
        ('1,500.50万元', '1500.5万'),
        ('3亿', '30000万'),
        ('500000元', '50万'),
        ('150', '150万'),
        ('面议', '面议'),               # 不可解析的文本原样保留，不吞数据
        ('', ''),
        (None, ''),
    ])
    def test_normalize_amount_text(self, raw, canon):
        from app.services.amountutil import normalize_amount_text
        assert normalize_amount_text(raw) == canon

    def test_extract_budget_keeps_unit(self):
        """爬虫正则抽取必须带出单位：'150万元' 不再被剥成 '150'。"""
        from app.services.crawler import extract_budget
        assert extract_budget('预算金额：150万元') == '150万'
        assert extract_budget('项目预算：1,200') == '1200万'
        assert extract_budget('总预算：88') == '88万'
        assert extract_budget('预算金额：3亿元') == '30000万'
        assert extract_budget('无预算信息') == ''


# ═══════════════════════════════════════════════════════════════
# API 写入侧归一化
# ═══════════════════════════════════════════════════════════════

class TestAmountNormalizationApi:
    def test_create_lead_normalizes_budget(self, client):
        lid = ok(client.post('/api/leads', json={'title': '金额归一线索', 'budget': '1,500.50万元'}))['id']
        assert ok(client.get(f'/api/leads/{lid}'))['budget'] == '1500.5万'

    def test_update_lead_normalizes_budget(self, client):
        lid = ok(client.post('/api/leads', json={'title': '金额归一线索2', 'budget': '100万'}))['id']
        ok(client.put(f'/api/leads/{lid}', json={'budget': '3亿'}))
        assert ok(client.get(f'/api/leads/{lid}'))['budget'] == '30000万'

    def test_unparseable_budget_preserved(self, client):
        lid = ok(client.post('/api/leads', json={'title': '金额归一线索3', 'budget': '面议'}))['id']
        assert ok(client.get(f'/api/leads/{lid}'))['budget'] == '面议'

    def test_convert_lead_normalizes_amount(self, client, seed):
        lid = ok(client.post('/api/leads', json={'title': '转化金额归一', 'budget': '2亿'}))['id']
        oid = ok(client.post(f'/api/leads/{lid}/convert', json={'customer_id': seed['customer']}))['id']
        assert ok(client.get(f'/api/opportunities/{oid}'))['amount'] == '20000万'

    def test_opportunity_create_update_normalizes(self, client, seed):
        oid = ok(client.post('/api/opportunities', json={
            'title': '商机金额归一', 'customer_id': seed['customer'], 'amount': '500000元'}))['id']
        assert ok(client.get(f'/api/opportunities/{oid}'))['amount'] == '50万'
        ok(client.put(f'/api/opportunities/{oid}', json={'amount': '88万'}))
        assert ok(client.get(f'/api/opportunities/{oid}'))['amount'] == '88万'

    def test_analytics_uses_wan_caliber(self, client, seed):
        """ Analytics 汇总口径：'1亿' + '200万' = 10200 万。"""
        ok(client.post('/api/opportunities', json={'title': '口径甲', 'customer_id': seed['customer'], 'amount': '1亿'}))
        ok(client.post('/api/opportunities', json={'title': '口径乙', 'customer_id': seed['customer'], 'amount': '200万'}))
        summary = ok(client.get('/api/analytics'))['summary']
        assert summary['total_amount'] >= 10200.0


# ═══════════════════════════════════════════════════════════════
# /api/leads 可选分页（向后兼容）
# ═══════════════════════════════════════════════════════════════

class TestLeadPagination:
    def _make(self, client, n):
        for i in range(n):
            assert ok(client.post('/api/leads', json={'title': f'分页线索{i:03d}'}))

    def test_no_params_returns_plain_array(self, client):
        data = ok(client.get('/api/leads'))
        assert isinstance(data, list) and len(data) >= 1

    def test_pagination_envelope_shape(self, client):
        self._make(client, 3)
        total = len(ok(client.get('/api/leads')))
        body = ok(client.get('/api/leads?page=1&page_size=2'))
        assert {'items', 'total', 'page', 'page_size', 'pages'} <= set(body)
        assert body['total'] == total
        assert len(body['items']) == 2
        assert body['pages'] == (total + 1) // 2

    def test_pages_cover_full_list_without_overlap(self, client):
        self._make(client, 5)
        ids_full = [x['id'] for x in ok(client.get('/api/leads'))]
        collected, page = [], 1
        while True:
            body = ok(client.get(f'/api/leads?page={page}&page_size=2'))
            collected += [x['id'] for x in body['items']]
            if page >= body['pages']:
                break
            page += 1
        assert collected == ids_full  # 顺序一致、不重不漏

    def test_filter_combined_with_pagination(self, client):
        for i in range(3):
            ok(client.post('/api/leads', json={'title': f'组合筛选{i}', 'status': 'active', 'region': '测试省'}))
        body = ok(client.get('/api/leads?region=测试省&page=1&page_size=2'))
        assert body['total'] == 3 and len(body['items']) == 2

    def test_page_beyond_end_clamped(self, client):
        body = ok(client.get('/api/leads?page=99999&page_size=10'))
        assert body['page'] == body['pages']

    def test_page_size_capped_at_500(self, client):
        body = ok(client.get('/api/leads?page=1&page_size=99999'))
        assert body['page_size'] == 500


# ═══════════════════════════════════════════════════════════════
# 数据库索引
# ═══════════════════════════════════════════════════════════════

class TestIndexes:
    def test_hot_columns_indexed(self, app):
        from app import db
        with app.app_context():
            rows = db.session.execute(text(
                "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL"
            )).fetchall()
        found = {(r[1], r[0]) for r in rows}
        needed = {
            ('leads', 'ix_leads_created_at'),
            ('leads', 'ix_leads_source_url'),
            ('leads', 'ix_leads_customer_id'),
            ('leads', 'ix_leads_match_level'),
            ('leads', 'ix_leads_status_created_at'),
            ('opportunities', 'ix_opportunities_lead_id'),
            ('opportunities', 'ix_opportunities_customer_id'),
            ('activities', 'ix_activities_customer_id'),
            ('activities', 'ix_activities_activity_time'),
            ('contacts', 'ix_contacts_customer_id'),
            ('customer_news', 'ix_customer_news_customer_id'),
            ('followups', 'ix_followups_plan_date'),
            ('followups', 'ix_followups_contact_id'),
            ('kanban_columns', 'ix_kanban_columns_board_id'),
            ('kanban_cards', 'ix_kanban_cards_column_id'),
        }
        missing = needed - found
        assert not missing, f"缺失索引: {sorted(missing)}"
