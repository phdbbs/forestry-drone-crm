import os
import sys
from logging.config import fileConfig

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db
# 导入全部模型，确保 autogenerate 能感知到表结构
from app.models import (
    Customer, CustomerNews, Lead, Opportunity, OpportunityStage,
    StageRecord, Contact, Activity, KanbanBoard, KanbanColumn,
    KanbanCard, SystemConfig, Skill, FollowUp,
)
from app.models.user import User

config = context.config
if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = db.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    from sqlalchemy import create_engine
    import re as _re
    url = config.get_main_option("sqlalchemy.url")
    # 确保 sqlite 数据库所在目录存在（避免相对路径下无法创建文件）
    _m = _re.match(r'sqlite:///(.+)$', url)
    if _m:
        _db_file = _m.group(1)
        _d = os.path.dirname(_db_file)
        if _d and not os.path.isabs(_d):
            _d = os.path.join(os.getcwd(), _d)
        if _d:
            os.makedirs(_d, exist_ok=True)
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
