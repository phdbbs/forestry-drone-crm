"""使用账号：多用户各自口令，角色区分管理员与销售。

数据共享，不做 per-owner 隔离，因此权限只用来划分「谁能改系统配置和账号」，
而不是过滤业务数据。username 的唯一性用部分索引实现（见 __table_args__），
这样账号逻辑删除后用户名还能复用，而活跃账号之间仍保持唯一。
"""
from app import db
from datetime import datetime


class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('ux_users_username', 'username', unique=True,
                 sqlite_where=db.text('is_deleted = 0')),
    )
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, index=True)
    display_name = db.Column(db.String(50), default='')
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='sales', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False, server_default='1')
    last_login_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, server_default='0')

    @property
    def name(self):
        return self.display_name or self.username

    def to_dict(self):
        """对外只暴露标识与状态，password_hash 永不离开模型层。"""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or '',
            "role": self.role,
            "is_active": bool(self.is_active),
            "last_login_at": self.last_login_at.strftime('%Y-%m-%d %H:%M') if self.last_login_at else '',
            "created_at": self.created_at.strftime('%Y-%m-%d') if self.created_at else '',
        }

    @classmethod
    def find(cls, username):
        """按用户名取未删除的账号（大小写不敏感，登录与重名校验共用）。"""
        from sqlalchemy import func
        return cls.query.filter(
            func.lower(cls.username) == (username or '').strip().lower()
        ).first()
