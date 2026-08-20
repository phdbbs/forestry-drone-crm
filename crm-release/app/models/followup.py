from app import db
from datetime import datetime

class FollowUp(db.Model):
    __tablename__ = 'followups'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    opportunity_id = db.Column(db.Integer, db.ForeignKey('opportunities.id'))
    lead_id = db.Column(db.Integer, db.ForeignKey('leads.id'))
    plan_date = db.Column(db.DateTime)
    content = db.Column(db.Text)
    ai_suggested_content = db.Column(db.Text)
    actual_date = db.Column(db.DateTime)
    actual_content = db.Column(db.Text)
    add_to_kanban = db.Column(db.Boolean, default=False)
    kanban_card_id = db.Column(db.Integer, db.ForeignKey('kanban_cards.id'))
    source_activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    contact = db.relationship('Contact', backref='followups')
    customer = db.relationship('Customer', backref='followups')
    opportunity = db.relationship('Opportunity', backref='followups')
    lead = db.relationship('Lead', backref='followups')
    source_activity = db.relationship('Activity', backref='generated_followups')
