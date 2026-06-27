from app import db
from datetime import datetime

class KanbanBoard(db.Model):
    __tablename__ = 'kanban_boards'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    columns = db.relationship('KanbanColumn', backref='board', lazy=True, order_by='KanbanColumn.sort_order', cascade='all, delete-orphan')

class KanbanColumn(db.Model):
    __tablename__ = 'kanban_columns'
    id = db.Column(db.Integer, primary_key=True)
    board_id = db.Column(db.Integer, db.ForeignKey('kanban_boards.id'))
    name = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
