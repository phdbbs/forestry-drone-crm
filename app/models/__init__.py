from app import db
from datetime import datetime
from sqlalchemy.orm import validates
from app.models.followup import FollowUp
from app.services.textutil import clean_text


def _clean(value):
    """None 保持 None（不改变 nullable 语义），其余走 clean_text。

    collapse_space=True 只把连续空格/制表符压成一个，不动换行，
    所以 address / remark 这类多行字段也能安全使用。
    """
    return None if value is None else clean_text(value, collapse_space=True)


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    short_name = db.Column(db.String(50))
    customer_type = db.Column(db.String(50))
    level = db.Column(db.String(50))
    region = db.Column(db.String(100))
    address = db.Column(db.String(300))
    website = db.Column(db.String(300))
    registration_capital = db.Column(db.String(50))
    operation_years = db.Column(db.String(50))
    social_security_count = db.Column(db.Integer)
    business_scope = db.Column(db.Text)
    intellectual_property = db.Column(db.Text)
    department = db.Column(db.String(200))
    source = db.Column(db.String(100))
    remark = db.Column(db.Text)
    is_archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    contacts = db.relationship('Contact', backref='customer', lazy=True)
    news_items = db.relationship('CustomerNews', backref='customer', lazy=True)

    # 客户名出现在所有下拉框、列表和弹窗标题里，采集带进来的控制字符
    # （例如 0x1E）必须在这里拦掉。只补路由会漏掉将来的新写入口，
    # 所以放在模型层：POST / PUT / _find_or_create_customer 全都过这里。
    @validates('name', 'short_name', 'customer_type', 'level', 'region', 'address',
               'website', 'registration_capital', 'operation_years', 'department',
               'source', 'business_scope', 'intellectual_property', 'remark')
    def _clean_fields(self, key, value):
        return _clean(value)

class CustomerNews(db.Model):
    __tablename__ = 'customer_news'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    url = db.Column(db.String(1000))
    source_name = db.Column(db.String(200), default='')
    change_type = db.Column(db.String(20))
    publish_date = db.Column(db.DateTime)
    event_time = db.Column(db.DateTime)
    crawled_at = db.Column(db.DateTime, default=datetime.now)

class ContactNews(db.Model):
    """联系人动态信息：官网/媒体新闻中出现联系人姓名/职务时自动关联。"""
    __tablename__ = 'contact_news'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    url = db.Column(db.String(1000))
    source_name = db.Column(db.String(200), default='')
    change_type = db.Column(db.String(20), default='')
    publish_date = db.Column(db.DateTime)
    event_time = db.Column(db.DateTime)
    summary = db.Column(db.Text)
    crawled_at = db.Column(db.DateTime, default=datetime.now)
    contact = db.relationship('Contact', backref='news_items')

class CrawlLog(db.Model):
    """采集任务日志。"""
    __tablename__ = 'crawl_logs'
    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(50))
    sources = db.Column(db.String(500), default='')
    status = db.Column(db.String(20), default='success')  # success/partial/failed
    items_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    message = db.Column(db.Text)
    started_at = db.Column(db.DateTime, default=datetime.now)
    finished_at = db.Column(db.DateTime)

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    bid_number = db.Column(db.String(100))
    title = db.Column(db.String(500), nullable=False)
    budget = db.Column(db.String(50))
    deadline = db.Column(db.DateTime)
    region = db.Column(db.String(100))
    purchaser = db.Column(db.String(200))
    service_content = db.Column(db.Text)
    match_keywords = db.Column(db.Text)
    match_level = db.Column(db.String(20))
    match_score = db.Column(db.Integer, default=0)
    match_reason = db.Column(db.Text)
    contact_name = db.Column(db.String(100), default='')
    contact_phone = db.Column(db.String(100), default='')
    address = db.Column(db.String(300), default='')
    assignee = db.Column(db.String(50), default='')
    source_url = db.Column(db.String(1000))
    source_platform = db.Column(db.String(100))
    bid_type = db.Column(db.String(50), default='')
    winner = db.Column(db.String(200), default='')
    related_customer_ids = db.Column(db.String(500), default='')  # 关联的其他客户ID（逗号分隔）
    serial_no = db.Column(db.String(20), default='')  # 流水编号：年1位+月1位+日2位+流水2位
    full_text = db.Column(db.Text)  # 公告全文（用于详情弹窗查看）
    reason = db.Column(db.String(300), default='')  # 释放/删除原因
    status = db.Column(db.String(20), default='active')
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    opportunities = db.relationship('Opportunity', backref='lead', lazy=True)
    customer = db.relationship('Customer', backref='leads')

    # 这些字段来自公告采集（正则/AI 抽取），是 0x1E 之类字符的第一入口；
    # 而且 purchaser / winner 会被 _find_or_create_customer 拿去建客户，
    # 不在这里拦就会把脏字符传染给客户库。
    @validates('title', 'bid_number', 'region', 'purchaser', 'contact_name',
               'contact_phone', 'address', 'winner', 'source_platform', 'bid_type',
               'assignee', 'match_level', 'match_reason', 'match_keywords', 'reason',
               'service_content')
    def _clean_fields(self, key, value):
        return _clean(value)

class Opportunity(db.Model):
    __tablename__ = 'opportunities'
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    title = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.String(50))
    source_url = db.Column(db.String(1000))
    current_stage = db.Column(db.String(100))
    probability = db.Column(db.Integer, default=20)
    expected_close = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    customer = db.relationship('Customer', backref='opportunities')
    contact = db.relationship('Contact', backref='opportunities')
    stage_records = db.relationship('StageRecord', backref='opportunity', lazy=True, order_by='StageRecord.created_at')

class OpportunityStage(db.Model):
    __tablename__ = 'opportunity_stages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

class StageRecord(db.Model):
    __tablename__ = 'stage_records'
    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunities.id'))
    stage_name = db.Column(db.String(100))
    content = db.Column(db.Text)
    deadline = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    add_to_kanban = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(50))
    title = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    wechat = db.Column(db.String(50))
    role = db.Column(db.String(50), default='')
    tags = db.Column(db.Text, default='')
    avatar = db.Column(db.String(10), default='')
    business_scope = db.Column(db.Text)
    importance = db.Column(db.String(20))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    activities = db.relationship('Activity', backref='contact', lazy=True)


class Activity(db.Model):
    __tablename__ = 'activities'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunities.id'))
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'))
    method = db.Column(db.String(50))
    content = db.Column(db.Text)
    activity_time = db.Column(db.DateTime)
    next_followup_time = db.Column(db.DateTime)
    next_followup_content = db.Column(db.Text)
    add_to_kanban = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    customer = db.relationship('Customer', backref='activities')
    opportunity = db.relationship('Opportunity', backref='activities')
    lead = db.relationship('Lead', backref='activities')


class KanbanBoard(db.Model):
    __tablename__ = 'kanban_boards'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    columns = db.relationship('KanbanColumn', backref='board', lazy=True, order_by='KanbanColumn.sort_order', cascade='all, delete-orphan')

class KanbanColumn(db.Model):
    __tablename__ = 'kanban_columns'
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('kanban_boards.id'))
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    cards = db.relationship('KanbanCard', backref='column', lazy=True, order_by='KanbanCard.sort_order', cascade='all, delete-orphan')

class KanbanCard(db.Model):
    __tablename__ = 'kanban_cards'
    id = db.Column(db.Integer, primary_key=True)
    column_id = db.Column(db.Integer, db.ForeignKey('kanban_columns.id'))
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    label_color = db.Column(db.String(20))
    deadline = db.Column(db.DateTime)
    sort_order = db.Column(db.Integer, default=0)
    source_type = db.Column(db.String(50))
    source_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(300))
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(10))
    is_builtin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    config_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
