from app import db
from datetime import datetime

class FollowUp(db.Model):
    __tablename__ = 'followups'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contacts.id'))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    plan_date = db.Column(db.DateTime)
    content = db.Column(db.Text)
    ai_suggested_content = db.Column(db.Text)
    actual_date = db.Column(db.DateTime)
    actual_content = db.Column(db.Text)
    add_to_kanban = db.Column(db.Boolean, default=False)
    kanban_card_id = db.Column(db.Integer, db.ForeignKey('kanban_cards.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    contact = db.relationship('Contact', backref='followups')
    customer = db.relationship('Customer', backref='followups')
