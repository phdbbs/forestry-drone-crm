from app import db
from datetime import datetime

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
    match_reason = db.Column(db.Text)
    source_url = db.Column(db.String(1000))
    source_platform = db.Column(db.String(100))
    status = db.Column(db.String(20), default='active')
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    opportunities = db.relationship('Opportunity', backref='lead', lazy=True)
    customer = db.relationship('Customer', backref='leads')
