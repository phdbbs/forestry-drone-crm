from app import db
from app.models import Customer, Lead, Opportunity, Contact, Activity, KanbanBoard, KanbanColumn, KanbanCard, OpportunityStage, StageRecord, SystemConfig
from datetime import datetime
import os

def seed_if_empty():
    if os.environ.get('CRM_SKIP_SEED') == '1':
        return
    if Customer.query.first():
        return
    print("Seeding demo data...")
    c1 = Customer(name="浙江省林业局", short_name="浙江林业局", customer_type="政府", level="省级", region="杭州", website="http://lyj.zj.gov.cn", remark="省级核心客户")
    c2 = Customer(name="福建省林业厅", short_name="福建林厅", customer_type="政府", level="省级", region="福州", website="http://lyj.fj.gov.cn", remark="二期项目620万")
    c3 = Customer(name="江西省林业局", short_name="江西林局", customer_type="政府", level="省级", region="南昌", remark="航拍核查合作")
    c4 = Customer(name="中国铁塔浙江分公司", short_name="铁塔浙江", customer_type="运营商", region="杭州", remark="5G专网通信合作")
    c5 = Customer(name="大疆行业应用", short_name="大疆", customer_type="科技公司", region="深圳", website="https://www.dji.com", remark="竞对信息源")
    c6 = Customer(name="西南林业大学", short_name="西南林大", customer_type="科研院所", region="昆明", website="https://www.swfu.edu.cn", remark="AI模型学术支持")
    db.session.add_all([c1, c2, c3, c4, c5, c6])
    db.session.flush()
    ct1 = Contact(name="王处长", customer_id=c1.id, title="林业管理处处长", phone="138-0571-1234", email="wang@zjly.gov.cn", wechat="wangzjly", importance="关键", role="决策人", business_scope="松材线虫病防控、林业无人机巡检")
    ct2 = Contact(name="李科长", customer_id=c2.id, title="科技处处长", phone="139-0591-5678", email="li@fjly.gov.cn", wechat="li_fjly", importance="关键", role="业务负责人", business_scope="森林防火监测、智慧林业")
    ct3 = Contact(name="张主任", customer_id=c3.id, title="资源处处长", phone="137-0791-9012", email="zhang@jxly.gov.cn", wechat="zhangjx", importance="重要", role="决策人", business_scope="森林资源普查、航拍核查")
    ct4 = Contact(name="刘经理", customer_id=c4.id, title="政企客户部经理", phone="136-0571-3456", email="liu@china-tower.com", wechat="liutower", importance="重要", role="采购执行", business_scope="无人机通信中继")
    ct5 = Contact(name="周教授", customer_id=c6.id, title="教授/AI实验室主任", phone="139-8711-2233", email="zhou@swfu.edu.cn", wechat="zhou_ai", importance="重要", role="技术对接", business_scope="AI病虫害算法")
    db.session.add_all([ct1, ct2, ct3, ct4, ct5])
    db.session.flush()
    l1 = Lead(title="2026年浙江省松材线虫病防治无人机巡检项目", bid_number="ZJ-2026-0342", budget="150", deadline=datetime(2026,8,15), region="浙江省", purchaser="浙江省林业局", service_content="松材线虫病无人机飞行检查、林区巡检、航拍核查、AI病虫害算法识别", match_keywords="松材线虫病防治,无人机飞行检查,林区巡检,航拍核查,AI病虫害算法识别", match_level="高匹配", match_score=85, match_reason="包含高匹配关键词", source_platform="中国政府采购网", source_url="#", status="active", customer_id=c1.id)
    l2 = Lead(title="福建省森林防火无人机监测服务采购", bid_number="FJ-2026-0189", budget="280", deadline=datetime(2026,7,30), region="福建省", purchaser="福建省林业厅", service_content="森林防火无人机监测、热成像监测、应急通信保障", match_keywords="无人机监测,森林,监测", match_level="中匹配", match_score=60, match_reason="匹配关键词", source_platform="全国公共资源交易平台", source_url="#", status="active", customer_id=c2.id)
    l3 = Lead(title="江西省林区航拍核查服务", bid_number="JX-2026-0056", budget="90", deadline=datetime(2026,6,22), region="江西省", purchaser="江西省林业局", service_content="林区航拍核查、森林资源普查", match_keywords="林区航拍核查,航拍,林区", match_level="高匹配", match_score=80, match_reason="包含高匹配关键词", source_platform="江西省公共资源交易中心", source_url="#", status="active", customer_id=c3.id)
    l4 = Lead(title="四川省松材线虫病林木砍伐清运施工", bid_number="SC-2026-0421", budget="65", deadline=datetime(2026,9,1), region="四川省", purchaser="四川省林业和草原局", service_content="松材线虫病林木砍伐、清运、消杀施工", match_keywords="林木砍伐,清运,消杀施工", match_level="低匹配", match_score=30, match_reason="仅含低匹配关键词", source_platform="中国政府采购网", source_url="#", status="active", customer_id=None)
    l5 = Lead(title="中国移动无人机通信中继服务", bid_number="YD-2026-0112", budget="200", deadline=datetime(2026,8,30), region="全国", purchaser="中国移动政企客户部", service_content="无人机通信中继基站建设、巡检数据回传", match_keywords="无人机,通信中继", match_level="中匹配", match_score=55, match_reason="匹配关键词", source_platform="中国移动采购网", source_url="#", status="active", customer_id=c4.id)
    db.session.add_all([l1, l2, l3, l4, l5])
    db.session.flush()
    o1 = Opportunity(title="浙江无人机巡检服务商机", lead_id=l1.id, customer_id=c1.id, contact_id=ct1.id, amount="150", probability=60, expected_close=datetime(2026,9,30), current_stage="方案报价", created_at=datetime(2026,6,10))
    o2 = Opportunity(title="福建森林防火监测商机", lead_id=l2.id, customer_id=c2.id, contact_id=ct2.id, amount="280", probability=45, expected_close=datetime(2026,10,15), current_stage="签约谈判", created_at=datetime(2026,6,5))
    db.session.add_all([o1, o2])
    db.session.flush()
    db.session.add_all([
        StageRecord(opportunity_id=o1.id, stage_name="初步接触", content="与浙江省林业局王处长进行初次沟通", deadline=datetime(2026,6,15), status="completed"),
        StageRecord(opportunity_id=o1.id, stage_name="方案报价", content="提交无人机巡检技术方案及报价单", deadline=datetime(2026,6,20), status="pending"),
        StageRecord(opportunity_id=o2.id, stage_name="初步接触", content="与福建省林业厅李科长沟通防火监测需求", deadline=datetime(2026,6,10), status="completed"),
        StageRecord(opportunity_id=o2.id, stage_name="方案报价", content="提交热成像无人机监测方案", deadline=datetime(2026,6,18), status="completed"),
        StageRecord(opportunity_id=o2.id, stage_name="签约谈判", content="合同条款协商中", deadline=datetime(2026,7,1), status="pending"),
    ])
    db.session.add_all([
        Activity(customer_id=c1.id, contact_id=ct1.id, opportunity_id=o1.id, lead_id=l1.id, method="电话", content="确认标书密封要求", activity_time=datetime(2026,6,17,14,0), next_followup_time=datetime(2026,6,20), next_followup_content="电话询问评标结果"),
        Activity(customer_id=c2.id, contact_id=ct2.id, opportunity_id=o2.id, lead_id=l2.id, method="拜访", content="大理二期项目预计7月初发公告，预算约620万", activity_time=datetime(2026,6,16,10,0), next_followup_time=datetime(2026,7,1), next_followup_content="关注招标公告发布"),
    ])
    b1 = KanbanBoard(name="业务跟进看板")
    db.session.add(b1)
    db.session.flush()
    col1 = KanbanColumn(board_id=b1.id, name="待处理", sort_order=0)
    col2 = KanbanColumn(board_id=b1.id, name="进行中", sort_order=1)
    col3 = KanbanColumn(board_id=b1.id, name="已完成", sort_order=2)
    db.session.add_all([col1, col2, col3])
    db.session.flush()
    db.session.add_all([
        KanbanCard(column_id=col1.id, title="方案报价 - 浙江无人机巡检", description="提交技术方案及报价单", label_color="red", deadline=datetime(2026,6,20)),
        KanbanCard(column_id=col1.id, title="联络王处长", description="沟通方案细节", label_color="blue", deadline=datetime(2026,6,17)),
        KanbanCard(column_id=col2.id, title="合同签约 - 福建林业监测", description="合同条款协商中", label_color="yellow", deadline=datetime(2026,7,1)),
        KanbanCard(column_id=col3.id, title="初步接触 - 浙江林业局", description="已确认项目需求", label_color="green", deadline=datetime(2026,6,15)),
    ])
    for i, name in enumerate(["初步接触","需求调研","方案报价","方案评审","签约谈判","合同签约","项目交付","售后服务"]):
        db.session.add(OpportunityStage(name=name, sort_order=i))
    db.session.add_all([
        SystemConfig(key="crawl_urls", value="https://www.ccgp.gov.cn/", description="爬取URL列表"),
        SystemConfig(key="crawl_time", value="08:00", description="每日爬取时间"),
        SystemConfig(key="keywords", value="松材线虫病防治,林业病虫害监测,无人机巡检,无人机飞行检查,林业航拍核查,林区审计巡检", description="业务核心关键词"),
        SystemConfig(key="ai_api_key", value="", description="AI API Key"),
        SystemConfig(key="ai_api_endpoint", value="", description="AI API Endpoint URL"),
        SystemConfig(key="ai_model", value="gpt-4o", description="AI模型名称"),
        SystemConfig(key="crawl_enabled", value="true", description="是否启用自动爬取"),
        SystemConfig(key="daily_brief_enabled", value="true", description="是否启用每日简报"),
    ])
    db.session.commit()
    print("Seed complete!")
