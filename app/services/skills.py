import os
from app import db
from app.models import SystemConfig

class SkillRegistry:
    _skills = {}
    @classmethod
    def register(cls, mod):
        cls._skills[mod.name] = mod
    @classmethod
    def get_all(cls):
        return [{"name": s.name, "description": s.description} for s in cls._skills.values()]
    @classmethod
    def exists(cls, name):
        return name in cls._skills
    @classmethod
    def execute(cls, name, **kw):
        """执行技能。异常交给路由层翻译状态码，这里不再吞成 200 + {"error"}。"""
        if name not in cls._skills:
            raise KeyError(name)
        return cls._skills[name].execute(**kw)

# 技能快照的行数上限：AI 分析用得到的是样本与总量，不是把整库塞进一次响应
SNAPSHOT_LIMIT = 200

def _read_db(limit=SNAPSHOT_LIMIT):
    from app.models import Customer, Lead, Opportunity, Contact, Activity
    return {
        "customers": [{"id": c.id, "name": c.name} for c in Customer.query.filter_by(is_archived=False).order_by(Customer.id).limit(limit)],
        "leads": [{"id": l.id, "title": l.title, "level": l.match_level, "status": l.status} for l in Lead.query.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit)],
        "opportunities": [{"id": o.id, "title": o.title, "stage": o.current_stage} for o in Opportunity.query.order_by(Opportunity.created_at.desc(), Opportunity.id.desc()).limit(limit)],
        "contacts": [{"id": ct.id, "name": ct.name, "title": ct.title} for ct in Contact.query.order_by(Contact.id).limit(limit)],
        "activities": [{"id": a.id, "method": a.method, "content": a.content[:100]} for a in Activity.query.order_by(Activity.activity_time.desc()).limit(20).all()],
    }

def _table_counts():
    """真实总量：快照被截断后，len(快照) 会把「有 5000 条」报成「有 200 条」。"""
    from sqlalchemy import func
    from app.models import Activity, Contact, Customer, Lead, Opportunity
    models = {'customers': Customer, 'leads': Lead, 'opportunities': Opportunity,
              'contacts': Contact, 'activities': Activity}
    return {name: db.session.query(func.count(m.id)).scalar() or 0
            for name, m in models.items()}

class RDSkill:
    name = "read_database"
    description = "读取CRM全部数据"
    def execute(self, **kw): return _read_db()

class ADSkill:
    name = "analyze_data"
    description = "分析CRM数据"
    def execute(self, **kw):
        data = kw.get("data")
        summary = ({k: len(v) for k, v in data.items() if isinstance(v, list)}
                   if isinstance(data, dict) else _table_counts())
        return {"summary": summary, "suggestions": ["数据已分析"]}

class CrawlSkill:
    name = "crawl_leads"
    description = "爬取最新招标线索"
    def execute(self, **kw):
        from app.services.crawler import run_crawl
        n, errors = run_crawl()
        result = {"message": f"新增 {n} 条线索"}
        if errors:
            result["errors"] = errors
        return result

class GetCfg:
    name = "get_config"
    description = "读取系统配置"
    def execute(self, **kw):
        # 技能这条路径不能成为 /config 脱敏视图的绕道：凭据一律打码
        return {c.key: c.masked_value for c in SystemConfig.query.all()}

class UpCfg:
    name = "update_config"
    description = "更新系统配置"
    def execute(self, **kw):
        blocked = [k for k in kw if k != 'data' and SystemConfig.is_secret(k)]
        if blocked:
            raise ValueError(f"凭据类配置不能通过技能修改: {', '.join(sorted(blocked))}")
        for k, v in kw.items():
            if k == "data": continue
            cfg = SystemConfig.query.filter_by(key=k).first()
            if cfg: cfg.value = str(v)
            else:
                cfg = SystemConfig(key=k, value=str(v))
                db.session.add(cfg)
        db.session.commit()
        return {"message": "已更新"}

SkillRegistry.register(RDSkill())
SkillRegistry.register(ADSkill())
SkillRegistry.register(CrawlSkill())
SkillRegistry.register(GetCfg())
SkillRegistry.register(UpCfg())
