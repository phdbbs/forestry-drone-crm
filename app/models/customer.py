from app import db
from datetime import datetime

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    contacts = db.relationship('Contact', backref='customer', lazy=True)
    news_items = db.relationship('CustomerNews', backref='customer', lazy=True)

class CustomerNews(db.Model):
    __tablename__ = 'customer_news'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    url = db.Column(db.String(1000))
    change_type = db.Column(db.String(20))  # new_bid/updated/news
    publish_date = db.Column(db.DateTime)
    crawled_at = db.Column(db.DateTime, default=datetime.utcnow)
