from app import db
from datetime import datetime

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer = db.relationship('Customer', backref='activities')
    opportunity = db.relationship('Opportunity', backref='activities')
    lead = db.relationship('Lead', backref='activities')
