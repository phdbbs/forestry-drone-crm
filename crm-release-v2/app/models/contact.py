from app import db
from datetime import datetime

class Contact(db.Model):
    __tablename__ = 'contacts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(50))
    title = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    wechat = db.Column(db.String(50))
    business_scope = db.Column(db.Text)
    importance = db.Column(db.String(20))
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    activities = db.relationship('Activity', backref='contact', lazy=True)
