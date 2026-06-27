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
    def execute(cls, name, **kw):
        if name not in cls._skills:
            return {"error": "Skill not found"}
        try:
            return cls._skills[name].execute(**kw)
        except Exception as e:
            return {"error": str(e)}

def _read_db():
    from app.models import Customer, Lead, Opportunity, Contact, Activity
    return {
        "customers": [{"id": c.id, "name": c.name} for c in Customer.query.filter_by(is_archived=False).all()],
        "leads": [{"id": l.id, "title": l.title, "level": l.match_level, "status": l.status} for l in Lead.query.all()],
        "opportunities": [{"id": o.id, "title": o.title, "stage": o.current_stage} for o in Opportunity.query.all()],
        "contacts": [{"id": ct.id, "name": ct.name, "title": ct.title} for ct in Contact.query.all()],
        "activities": [{"id": a.id, "method": a.method, "content": a.content[:100]} for a in Activity.query.order_by(Activity.activity_time.desc()).limit(20).all()],
    }

class RDSkill:
    name = "read_database"
    description = "读取CRM全部数据"
    def execute(self, **kw): return _read_db()

class ADSkill:
    name = "analyze_data"
    description = "分析CRM数据"
    def execute(self, **kw):
        d = kw.get("data") or _read_db()
        return {"summary": {k: len(v) for k, v in d.items()}, "suggestions": ["数据已分析"]}

class CrawlSkill:
    name = "crawl_leads"
    description = "爬取最新招标线索"
    def execute(self, **kw):
        from app.services.crawler import run_crawl
        n = run_crawl()
        return {"message": f"新增 {n} 条线索"}

class GetCfg:
    name = "get_config"
    description = "读取系统配置"
    def execute(self, **kw):
        return {c.key: c.value for c in SystemConfig.query.all()}

class UpCfg:
    name = "update_config"
    description = "更新系统配置"
    def execute(self, **kw):
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
