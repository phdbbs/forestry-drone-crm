"""逻辑删除的读取侧：全局屏蔽打了删除标记的行。

规则是「删除只置 is_deleted=True，行永不从库里消失」（见 app/models）。
读取统一在这里注入过滤条件，而不是让每个查询自己写 where —— 这个项目有
170 多处查询，靠人工加条件必然漏，漏一处的结果就是已删数据继续满屏出现。

两类查询必须「看见已删行」，要显式豁免：
    some_query.execution_options(include_deleted=True)
- 流水号分配：编号一旦复用会撞 leads.serial_no 唯一索引；
- 采集/新闻去重：看不见已删公告就会把同一条公告重复采回来。
"""
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

_installed = False

# 只建一个 lambda：SQLAlchemy 按 code 对象缓存 lambda 的解析结果，
# 每个模型各自新建 lambda 会让每条 SQL 都重新解析一遍。
_criteria = lambda cls: cls.is_deleted.is_(False)  # noqa: E731


def _entities():
    from app import db
    import app.models  # noqa: F401  确保全部模型已完成映射注册
    return [m.class_ for m in db.Model.registry.mappers
            if hasattr(m.class_, 'is_deleted')]


def install():
    """注册全局过滤。挂的是 Session 类级监听，因此测试里新建的会话同样生效。"""
    global _installed
    if _installed:
        return
    _installed = True
    options = tuple(
        with_loader_criteria(entity, _criteria, include_aliases=True)
        for entity in _entities()
    )
    if not options:
        raise RuntimeError('未发现任何带 is_deleted 的模型，软删过滤器无法安装')

    @event.listens_for(Session, 'do_orm_execute')
    def _hide_deleted_rows(execute_state):
        if not execute_state.is_select:
            return
        if execute_state.is_column_load or execute_state.is_relationship_load:
            return
        if execute_state.execution_options.get('include_deleted'):
            return
        execute_state.statement = execute_state.statement.options(*options)


def alive(model):
    """给批量 UPDATE 用的过滤条件。

    上面的全局钩子只作用于 SELECT；Query.update() 走的是 UPDATE 语句，
    不加这个条件就会顺手改到已删除的行，把墓碑数据也一起改掉。
    """
    return model.is_deleted.is_(False)
