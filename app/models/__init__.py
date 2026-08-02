from app import db
from datetime import datetime
from app.models.followup import FollowUp

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

class CustomerNews(db.Model):
    __tablename__ = 'customer_news'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    url = db.Column(db.String(1000))
    change_type = db.Column(db.String(20))
    publish_date = db.Column(db.DateTime)
    crawled_at = db.Column(db.DateTime, default=datetime.now)

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
    status = db.Column(db.String(20), default='active')
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    opportunities = db.relationship('Opportunity', backref='lead', lazy=True)
    customer = db.relationship('Customer', backref='leads')

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
