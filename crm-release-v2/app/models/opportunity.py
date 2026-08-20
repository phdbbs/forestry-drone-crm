from app import db
from datetime import datetime

class Opportunity(db.Model):
    __tablename__ = 'opportunities'
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    title = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.String(50))
    current_stage = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer = db.relationship('Customer', backref='opportunities')
    contact = db.relationship('Contact', backref='opportunities')
    stage_records = db.relationship('StageRecord', backref='opportunity', lazy=True, order_by='StageRecord.created_at')

class OpportunityStage(db.Model):
    __tablename__ = 'opportunity_stages'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class StageRecord(db.Model):
    __tablename__ = 'stage_records'
    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunities.id'))
    stage_name = db.Column(db.String(100))
    content = db.Column(db.Text)
    deadline = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    add_to_kanban = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
