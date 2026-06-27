from flask import Blueprint, request, jsonify
from app import db
from app.models import (
    Customer, CustomerNews, Lead, Opportunity, OpportunityStage,
    StageRecord, Contact, Activity, KanbanBoard, KanbanColumn,
    KanbanCard, SystemConfig, Skill, FollowUp
)
from app.services.matcher import match_lead
from app.services.skills import SkillRegistry
from datetime import datetime, timedelta

api = Blueprint('api', __name__)

@api.route('/skills', methods=['GET'])
def list_skills():
    skills = Skill.query.filter_by(is_active=True).all()
    builtin = SkillRegistry.get_all()
    db_skills = [{"name": s.name, "description": s.description, "icon": s.icon or "🔧"} for s in skills]
    return jsonify(builtin + db_skills)

@api.route('/skills', methods=['POST'])
def create_skill():
    d = request.get_json()
    s = Skill(name=d['name'], description=d.get('description',''), icon=d.get('icon','🔧'), is_builtin=False)
    db.session.add(s)
    db.session.commit()
    return jsonify({"id": s.id, "name": s.name})

@api.route('/skills/<int:id>', methods=['DELETE'])
def delete_skill(id):
    s = Skill.query.get_or_404(id)
    if s.is_builtin:
        return jsonify({"error": "内置技能不可删除"}), 400
    db.session.delete(s)
    db.session.commit()
    return jsonify({"ok": True})

@api.route('/skills/<name>/execute', methods=['POST'])
def execute_skill(name):
    data = request.get_json() or {}
    result = SkillRegistry.execute(name, **data)
    return jsonify(result)

@api.route('/dashboard', methods=['GET'])
def dashboard():
    leads = Lead.query.filter_by(status='active').all()
    level_score = {'高匹配': 300, '中匹配': 200, '低匹配': 100}
    leads.sort(key=lambda l: -(level_score.get(l.match_level, 0)))
    today = datetime.now().strftime('%Y-%m-%d')
    today_activities = Activity.query.filter(db.func.date(Activity.activity_time) == today).all()
    today_followups = FollowUp.query.filter(db.func.date(FollowUp.plan_date) == today).all()
    urgent_leads = [l for l in leads if l.deadline and 0 < (l.deadline - datetime.now()).days <= 3]
    opportunities = Opportunity.query.all()
    kanban_cards = KanbanCard.query.filter(KanbanCard.deadline.isnot(None)).order_by(KanbanCard.deadline).limit(10).all()
    return jsonify({
        "stats": {"active_leads": len(leads), "opportunities": len(opportunities), "today_activities": len(today_activities), "urgent_leads": len(urgent_leads), "today_followups": len(today_followups)},
        "urgent_leads": [{"id": l.id, "title": l.title[:60], "level": l.match_level, "deadline": str(l.deadline.date()) if l.deadline else None, "match_keywords": l.match_keywords, "customer_name": l.customer.name if l.customer else None} for l in urgent_leads[:5]],
        "opportunities": [{"id": o.id, "title": o.title[:60], "stage": o.current_stage, "amount": o.amount, "customer_name": o.customer.name if o.customer else None} for o in opportunities],
        "today_activities": [{"id": a.id, "method": a.method, "content": a.content[:80], "time": str(a.activity_time), "contact_name": a.contact.name if a.contact else None, "customer_name": a.customer.name if a.customer else None} for a in today_activities],
        "today_followups": [{"id": f.id, "content": f.content[:60], "contact_name": f.contact.name if f.contact else None, "plan_date": str(f.plan_date)} for f in today_followups],
        "kanban_cards": [{"id": c.id, "title": c.title, "deadline": str(c.deadline.date()) if c.deadline else None, "color": c.label_color} for c in kanban_cards],
    })

@api.route('/customers', methods=['GET'])
def list_customers():
    q = request.args.get('search', '')
    customers = Customer.query.filter_by(is_archived=False)
    if q: customers = customers.filter(Customer.name.contains(q))
    return jsonify([{"id": c.id, "name": c.name, "short_name": c.short_name, "type": c.customer_type, "level": c.level, "region": c.region, "source": c.source, "contact_count": len(c.contacts), "news_count": len(c.news_items)} for c in customers.all()])

@api.route('/customers', methods=['POST'])
def create_customer():
    d = request.get_json()
    c = Customer(name=d['name'], short_name=d.get('short_name',''), customer_type=d.get('type',''), level=d.get('level',''), region=d.get('region',''), address=d.get('address',''), website=d.get('website',''), registration_capital=d.get('capital',''), operation_years=d.get('years',''), social_security_count=d.get('social_count'), business_scope=d.get('scope',''), intellectual_property=d.get('ip',''), department=d.get('dept',''), source=d.get('source',''), remark=d.get('remark',''))
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id, "message": "创建成功"})

@api.route('/customers/<int:id>', methods=['GET'])
def get_customer(id):
    c = Customer.query.get_or_404(id)
    return jsonify({"id": c.id, "name": c.name, "short_name": c.short_name, "type": c.customer_type, "level": c.level, "region": c.region, "address": c.address, "website": c.website, "capital": c.registration_capital, "years": c.operation_years, "social_count": c.social_security_count, "scope": c.business_scope, "ip": c.intellectual_property, "dept": c.department, "source": c.source, "remark": c.remark, "contacts": [{"id": ct.id, "name": ct.name, "title": ct.title, "phone": ct.phone, "importance": ct.importance} for ct in c.contacts], "news": [{"id": n.id, "title": n.title, "date": str(n.publish_date.date()) if n.publish_date else None, "type": n.change_type, "url": n.url} for n in c.news_items]})

@api.route('/customers/<int:id>', methods=['PUT'])
def update_customer(id):
    c = Customer.query.get_or_404(id)
    d = request.get_json()
    for key in ['name','short_name','customer_type','level','region','address','website','registration_capital','operation_years','business_scope','intellectual_property','department','source','remark']:
        if key in d: setattr(c, key, d[key])
    if 'social_count' in d: c.social_security_count = d['social_count']
    db.session.commit()
    return jsonify({"id": c.id, "message": "更新成功"})

@api.route('/customers/<int:id>', methods=['DELETE'])
def delete_customer(id):
    c = Customer.query.get_or_404(id)
    c.is_archived = True
    db.session.commit()
    return jsonify({"message": "已归档"})

@api.route('/leads', methods=['GET'])
def list_leads():
    q = request.args.get('search', '')
    status = request.args.get('status', '')
    level = request.args.get('level', '')
    query = Lead.query
    if q: query = query.filter(Lead.title.contains(q))
    if status: query = query.filter_by(status=status)
    if level: query = query.filter_by(match_level=level)
    leads = query.order_by(Lead.created_at.desc()).all()
    return jsonify([{"id": l.id, "title": l.title, "bid_number": l.bid_number, "budget": l.budget, "deadline": str(l.deadline.date()) if l.deadline else None, "region": l.region, "purchaser": l.purchaser, "service_content": l.service_content, "match_keywords": l.match_keywords, "match_level": l.match_level, "match_reason": l.match_reason, "source_platform": l.source_platform, "source_url": l.source_url, "status": l.status, "customer_id": l.customer_id, "customer_name": l.customer.name if l.customer else None} for l in leads])

@api.route('/leads', methods=['POST'])
def create_lead():
    d = request.get_json()
    l = Lead(bid_number=d.get('bid_number',''), title=d['title'], budget=d.get('budget',''), deadline=datetime.strptime(d['deadline'],'%Y-%m-%d') if d.get('deadline') else None, region=d.get('region',''), purchaser=d.get('purchaser',''), service_content=d.get('service_content',''), source_url=d.get('source_url',''), source_platform=d.get('source_platform',''), customer_id=d.get('customer_id'))
    match_lead(l)
    db.session.add(l)
    db.session.commit()
    return jsonify({"id": l.id, "message": "创建成功"})

@api.route('/leads/<int:id>', methods=['GET'])
def get_lead(id):
    l = Lead.query.get_or_404(id)
    return jsonify({"id": l.id, "title": l.title, "bid_number": l.bid_number, "budget": l.budget, "deadline": str(l.deadline.date()) if l.deadline else None, "region": l.region, "purchaser": l.purchaser, "service_content": l.service_content, "match_keywords": l.match_keywords, "match_level": l.match_level, "match_reason": l.match_reason, "source_platform": l.source_platform, "source_url": l.source_url, "status": l.status, "customer_id": l.customer_id, "customer_name": l.customer.name if l.customer else None})

@api.route('/leads/<int:id>', methods=['PUT'])
def update_lead(id):
    l = Lead.query.get_or_404(id)
    d = request.get_json()
    for key in ['title','bid_number','budget','region','purchaser','service_content','match_keywords','match_level','match_reason','source_platform','source_url','status','customer_id']:
        if key in d: setattr(l, key, d[key])
    if 'deadline' in d and d['deadline']: l.deadline = datetime.strptime(d['deadline'], '%Y-%m-%d')
    db.session.commit()
    return jsonify({"id": l.id, "message": "更新成功"})

@api.route('/leads/<int:id>/convert', methods=['POST'])
def convert_lead(id):
    l = Lead.query.get_or_404(id)
    if l.status != 'active': return jsonify({"error": "仅活跃线索可转化"}), 400
    d = request.get_json() or {}
    o = Opportunity(lead_id=l.id, customer_id=d.get('customer_id', l.customer_id), contact_id=d.get('contact_id'), title=d.get('title', l.title), amount=d.get('amount', l.budget), current_stage=d.get('stage', '初步接触'))
    db.session.add(o)
    l.status = 'converted'
    db.session.commit()
    return jsonify({"id": o.id, "message": "已转为商机"})

@api.route('/leads/<int:id>/abandon', methods=['POST'])
def abandon_lead(id):
    l = Lead.query.get_or_404(id)
    l.status = 'abandoned'
    db.session.commit()
    return jsonify({"message": "已废弃"})

@api.route('/opportunities', methods=['GET'])
def list_opportunities():
    ops = Opportunity.query.order_by(Opportunity.created_at.desc()).all()
    return jsonify([{"id": o.id, "title": o.title, "amount": o.amount, "current_stage": o.current_stage, "customer_id": o.customer_id, "customer_name": o.customer.name if o.customer else None, "contact_id": o.contact_id, "contact_name": o.contact.name if o.contact else None, "lead_id": o.lead_id, "stages": [{"stage": s.stage_name, "content": s.content, "deadline": str(s.deadline.date()) if s.deadline else None, "status": s.status} for s in o.stage_records]} for o in ops])

@api.route('/opportunities/<int:id>', methods=['GET'])
def get_opportunity(id):
    o = Opportunity.query.get_or_404(id)
    lead = Lead.query.get(o.lead_id) if o.lead_id else None
    return jsonify({"id": o.id, "title": o.title, "amount": o.amount, "current_stage": o.current_stage, "customer_id": o.customer_id, "customer_name": o.customer.name if o.customer else None, "contact_id": o.contact_id, "contact_name": o.contact.name if o.contact else None, "lead_id": o.lead_id, "lead_title": lead.title if lead else None, "stages": [{"id": s.id, "stage": s.stage_name, "content": s.content, "deadline": str(s.deadline.date()) if s.deadline else None, "status": s.status, "add_to_kanban": s.add_to_kanban} for s in o.stage_records]})

@api.route('/opportunities/<int:id>/stages', methods=['POST'])
def add_stage_record(id):
    o = Opportunity.query.get_or_404(id)
    d = request.get_json()
    record = StageRecord(opportunity_id=o.id, stage_name=d.get('stage_name',''), content=d.get('content',''), status='pending', add_to_kanban=d.get('add_to_kanban', False))
    if d.get('deadline'): record.deadline = datetime.strptime(d['deadline'], '%Y-%m-%d')
    if d.get('status'): record.status = d['status']
    o.current_stage = record.stage_name
    db.session.add(record)
    db.session.commit()
    return jsonify({"id": record.id, "message": "阶段记录已添加"})

@api.route('/stages', methods=['GET'])
def list_stages():
    stages = OpportunityStage.query.order_by(OpportunityStage.sort_order).all()
    return jsonify([{"id": s.id, "name": s.name, "sort_order": s.sort_order} for s in stages])

@api.route('/stages', methods=['POST'])
def create_stage():
    d = request.get_json()
    s = OpportunityStage(name=d['name'], sort_order=d.get('sort_order', OpportunityStage.query.count()))
    db.session.add(s)
    db.session.commit()
    return jsonify({"id": s.id})

@api.route('/stages/<int:id>', methods=['PUT'])
def update_stage(id):
    s = OpportunityStage.query.get_or_404(id)
    d = request.get_json()
    if 'name' in d: s.name = d['name']
    if 'sort_order' in d: s.sort_order = d['sort_order']
    db.session.commit()
    return jsonify({"ok": True})

@api.route('/stages/<int:id>', methods=['DELETE'])
def delete_stage(id):
    s = OpportunityStage.query.get_or_404(id)
    db.session.delete(s)
    db.session.commit()
    return jsonify({"ok": True})

@api.route('/contacts', methods=['GET'])
def list_contacts():
    q = request.args.get('search', '')
    query = Contact.query
    if q: query = query.filter(Contact.name.contains(q))
    return jsonify([{"id": c.id, "name": c.name, "title": c.title, "phone": c.phone, "email": c.email, "wechat": c.wechat, "importance": c.importance, "customer_id": c.customer_id, "customer_name": c.customer.name if c.customer else None, "business_scope": c.business_scope, "notes": c.notes} for c in query.all()])

@api.route('/contacts', methods=['POST'])
def create_contact():
    d = request.get_json()
    c = Contact(name=d['name'], title=d.get('title',''), phone=d.get('phone',''), email=d.get('email',''), wechat=d.get('wechat',''), importance=d.get('importance',''), customer_id=d.get('customer_id'), business_scope=d.get('business_scope',''), notes=d.get('notes',''))
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id, "message": "创建成功"})

@api.route('/contacts/<int:id>', methods=['GET'])
def get_contact(id):
    c = Contact.query.get_or_404(id)
    customer = c.customer
    news = [{"id": n.id, "title": n.title, "date": str(n.publish_date.date()) if n.publish_date else None, "url": n.url} for n in customer.news_items] if customer else []
    return jsonify({"id": c.id, "name": c.name, "title": c.title, "phone": c.phone, "email": c.email, "wechat": c.wechat, "importance": c.importance, "customer_id": c.customer_id, "customer_name": customer.name if customer else None, "business_scope": c.business_scope, "notes": c.notes, "news": news})

@api.route('/contacts/<int:id>', methods=['PUT'])
def update_contact(id):
    c = Contact.query.get_or_404(id)
    d = request.get_json()
    for key in ['name','title','phone','email','wechat','importance','customer_id','business_scope','notes']:
        if key in d: setattr(c, key, d[key])
    db.session.commit()
    return jsonify({"id": c.id, "message": "更新成功"})

@api.route('/contacts/<int:id>', methods=['DELETE'])
def delete_contact(id):
    c = Contact.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "已删除"})

@api.route('/activities', methods=['GET'])
def list_activities():
    q = request.args.get('search', '')
    method = request.args.get('method', '')
    query = Activity.query
    if q: query = query.filter(Activity.content.contains(q))
    if method: query = query.filter_by(method=method)
    acts = query.order_by(Activity.activity_time.desc()).all()
    return jsonify([{"id": a.id, "title": a.title, "method": a.method, "content": a.content, "activity_time": str(a.activity_time) if a.activity_time else None, "next_followup_time": str(a.next_followup_time.date()) if a.next_followup_time else None, "next_followup_content": a.next_followup_content, "customer_id": a.customer_id, "customer_name": a.customer.name if a.customer else None, "contact_id": a.contact_id, "contact_name": a.contact.name if a.contact else None, "opportunity_id": a.opportunity_id, "opportunity_title": a.opportunity.title if a.opportunity else None, "lead_id": a.lead_id} for a in acts])

@api.route('/activities', methods=['POST'])
def create_activity():
    d = request.get_json()
    a = Activity(title=d.get('title',''), customer_id=d.get('customer_id'), contact_id=d.get('contact_id'), opportunity_id=d.get('opportunity_id'), lead_id=d.get('lead_id'), method=d.get('method',''), content=d.get('content',''), activity_time=datetime.strptime(d['time'],'%Y-%m-%d %H:%M') if d.get('time') else datetime.utcnow(), next_followup_time=datetime.strptime(d['next_time'],'%Y-%m-%d') if d.get('next_time') else None, next_followup_content=d.get('next_content',''), add_to_kanban=d.get('add_to_kanban', False))
    db.session.add(a)
    db.session.commit()
    return jsonify({"id": a.id, "message": "创建成功"})

@api.route('/activities/<int:id>', methods=['GET'])
def get_activity(id):
    a = Activity.query.get_or_404(id)
    return jsonify({"id": a.id, "title": a.title, "method": a.method, "content": a.content, "activity_time": str(a.activity_time) if a.activity_time else None, "next_followup_time": str(a.next_followup_time.date()) if a.next_followup_time else None, "next_followup_content": a.next_followup_content, "customer_id": a.customer_id, "customer_name": a.customer.name if a.customer else None, "contact_id": a.contact_id, "contact_name": a.contact.name if a.contact else None, "opportunity_id": a.opportunity_id, "opportunity_title": a.opportunity.title if a.opportunity else None, "lead_id": a.lead_id})

@api.route('/activities/<int:id>', methods=['PUT'])
def update_activity(id):
    a = Activity.query.get_or_404(id)
    d = request.get_json()
    for key in ['title','method','content','next_followup_content','customer_id','contact_id','opportunity_id','lead_id']:
        if key in d: setattr(a, key, d[key])
    if 'time' in d and d['time']: a.activity_time = datetime.strptime(d['time'], '%Y-%m-%d %H:%M')
    if 'next_time' in d and d['next_time']: a.next_followup_time = datetime.strptime(d['next_time'], '%Y-%m-%d')
    db.session.commit()
    return jsonify({"id": a.id, "message": "更新成功"})

@api.route('/activities/<int:id>', methods=['DELETE'])
def delete_activity(id):
    a = Activity.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    return jsonify({"message": "已删除"})


@api.route('/followups', methods=['GET'])
def list_followups():
    q = request.args.get('search', '')
    query = FollowUp.query
    if q: query = query.filter(FollowUp.content.contains(q))
    items = query.order_by(FollowUp.plan_date).all()
    return jsonify([{
        "id": f.id, "contact_id": f.contact_id,
        "contact_name": f.contact.name if f.contact else None,
        "customer_id": f.customer_id,
        "customer_name": f.customer.name if f.customer else None,
        "plan_date": str(f.plan_date) if f.plan_date else None,
        "content": f.content, "ai_suggested_content": f.ai_suggested_content,
        "actual_date": str(f.actual_date) if f.actual_date else None,
        "actual_content": f.actual_content,
        "add_to_kanban": f.add_to_kanban
    } for f in items])

@api.route('/followups', methods=['POST'])
def create_followup():
    d = request.get_json()
    f = FollowUp(
        contact_id=d.get('contact_id'), customer_id=d.get('customer_id'),
        plan_date=datetime.strptime(d['plan_date'], '%Y-%m-%d') if d.get('plan_date') else None,
        content=d.get('content',''), ai_suggested_content=d.get('ai_content',''),
        add_to_kanban=d.get('add_to_kanban', False)
    )
    db.session.add(f)
    db.session.commit()
    return jsonify({"id": f.id, "message": "创建成功"})

@api.route('/followups/<int:id>', methods=['PUT'])
def update_followup(id):
    f = FollowUp.query.get_or_404(id)
    d = request.get_json()
    for key in ['content', 'ai_suggested_content', 'actual_content', 'add_to_kanban', 'contact_id', 'customer_id']:
        if key in d: setattr(f, key, d[key])
    if 'plan_date' in d and d['plan_date']: f.plan_date = datetime.strptime(d['plan_date'], '%Y-%m-%d')
    if 'actual_date' in d and d['actual_date']: f.actual_date = datetime.strptime(d['actual_date'], '%Y-%m-%d')
    db.session.commit()
    return jsonify({"id": f.id, "message": "更新成功"})

@api.route('/followups/<int:id>', methods=['DELETE'])
def delete_followup(id):
    f = FollowUp.query.get_or_404(id)
    db.session.delete(f)
    db.session.commit()
    return jsonify({"message": "已删除"})

@api.route('/suggestions', methods=['GET'])
def get_suggestions():
    from app.services.suggestion_engine import generate_suggestions
    suggestions = generate_suggestions()
    return jsonify(suggestions)

@api.route('/customers/<int:id>/news', methods=['GET'])
def customer_news(id):
    news = CustomerNews.query.filter_by(customer_id=id).order_by(CustomerNews.crawled_at.desc()).all()
    return jsonify([{
        "id": n.id, "title": n.title, "content": n.content,
        "url": n.url, "change_type": n.change_type,
        "publish_date": str(n.publish_date) if n.publish_date else None,
        "crawled_at": str(n.crawled_at) if n.crawled_at else None
    } for n in news])

@api.route('/daily-brief', methods=['GET'])
def daily_brief():
    today = datetime.now().strftime('%Y-%m-%d')
    today_acts = Activity.query.filter(db.func.date(Activity.activity_time) == today).all()
    today_followups = FollowUp.query.filter(db.func.date(FollowUp.plan_date) == today).all()
    pending_followups = FollowUp.query.filter(FollowUp.actual_date.is_(None), FollowUp.plan_date <= datetime.now()).all()
    week_from_now = datetime.now() + timedelta(days=7)
    upcoming_deadlines = Lead.query.filter(Lead.deadline.between(datetime.now(), week_from_now), Lead.status == 'active').all()
    return jsonify({
        "today_activities": [{"title": a.title or a.method, "method": a.method, "contact_name": a.contact.name if a.contact else None, "customer_name": a.customer.name if a.customer else None} for a in today_acts],
        "today_followups": [{"content": f.content, "contact_name": f.contact.name if f.contact else None, "plan_date": str(f.plan_date)} for f in today_followups],
        "overdue_followups": [{"content": f.content, "contact_name": f.contact.name if f.contact else None, "plan_date": str(f.plan_date)} for f in pending_followups],
        "upcoming_deadlines": [{"title": l.title, "level": l.match_level, "deadline": str(l.deadline.date())} for l in upcoming_deadlines]
    })

@api.route('/kanban/boards', methods=['GET'])
def list_boards():
    boards = KanbanBoard.query.all()
    result = []
    for b in boards:
        cols = []
        for col in b.columns:
            cards = [{"id": c.id, "title": c.title, "description": c.description, "color": c.label_color, "deadline": str(c.deadline.date()) if c.deadline else None, "source_type": c.source_type, "source_id": c.source_id} for c in col.cards]
            cols.append({"id": col.id, "name": col.name, "sort_order": col.sort_order, "cards": cards})
        result.append({"id": b.id, "name": b.name, "columns": cols})
    return jsonify(result)

@api.route('/kanban/boards', methods=['POST'])
def create_board():
    d = request.get_json()
    b = KanbanBoard(name=d.get('name','新看板'))
    db.session.add(b)
    db.session.flush()
    for i, name in enumerate(['待处理','进行中','已完成']):
        db.session.add(KanbanColumn(board_id=b.id, name=name, sort_order=i))
    db.session.commit()
    return jsonify({"id": b.id})

@api.route('/kanban/boards/<int:id>', methods=['DELETE'])
def delete_board(id):
    b = KanbanBoard.query.get_or_404(id)
    db.session.delete(b)
    db.session.commit()
    return jsonify({"ok": True})

@api.route('/kanban/boards/<int:board_id>/columns', methods=['POST'])
def add_column(board_id):
    d = request.get_json()
    col = KanbanColumn(board_id=board_id, name=d.get('name','新列表'), sort_order=len(KanbanBoard.query.get(board_id).columns))
    db.session.add(col)
    db.session.commit()
    return jsonify({"id": col.id})

@api.route('/kanban/cards/<int:card_id>/move', methods=['POST'])
def move_card(card_id):
    card = KanbanCard.query.get_or_404(card_id)
    d = request.get_json()
    card.column_id = d['column_id']
    db.session.commit()
    return jsonify({"ok": True})

@api.route('/kanban/import', methods=['POST'])
def import_to_kanban():
    d = request.get_json()
    board_id = d.get('board_id')
    items = d.get('items', [])
    board = KanbanBoard.query.get_or_404(board_id)
    target_col = board.columns[0] if board.columns else None
    if not target_col:
        target_col = KanbanColumn(board_id=board_id, name='待处理', sort_order=0)
        db.session.add(target_col)
        db.session.flush()
    for item in items:
        card = KanbanCard(column_id=target_col.id, title=item.get('title',''), description=item.get('description',''), label_color=item.get('color','blue'), source_type=item.get('source_type',''), source_id=item.get('source_id'))
        db.session.add(card)
    db.session.commit()
    return jsonify({"message": f"已导入 {len(items)} 张卡片"})

@api.route('/config', methods=['GET'])
def get_config():
    configs = SystemConfig.query.all()
    return jsonify({c.key: {"value": c.value, "description": c.description} for c in configs})

@api.route('/config', methods=['PUT'])
def update_config():
    d = request.get_json()
    for key, value in d.items():
        config = SystemConfig.query.filter_by(key=key).first()
        if config: config.value = str(value)
        else:
            config = SystemConfig(key=key, value=str(value))
            db.session.add(config)
    db.session.commit()
    return jsonify({"message": "配置已更新"})

@api.route('/crawl', methods=['POST'])
def trigger_crawl():
    from app.services.crawler import run_crawl
    count = run_crawl()
    return jsonify({"message": f"爬取完成，新增 {count} 条线索", "count": count})

@api.route('/leads/<int:id>', methods=['DELETE'])
def delete_lead(id):
    l = Lead.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    return jsonify({"message": "已删除"})

@api.route('/opportunities', methods=['POST'])
def create_opportunity():
    d = request.get_json()
    o = Opportunity(title=d['title'], customer_id=d.get('customer_id'), contact_id=d.get('contact_id'), amount=d.get('amount',''), current_stage=d.get('current_stage','初步接触'))
    db.session.add(o)
    db.session.commit()
    return jsonify({"id": o.id, "message": "创建成功"})

@api.route('/opportunities/<int:id>', methods=['PUT'])
def update_opportunity(id):
    o = Opportunity.query.get_or_404(id)
    d = request.get_json()
    for key in ['title','amount','current_stage','customer_id','contact_id']:
        if key in d: setattr(o, key, d[key])
    db.session.commit()
    return jsonify({"id": o.id, "message": "更新成功"})

@api.route('/opportunities/<int:id>', methods=['DELETE'])
def delete_opportunity(id):
    o = Opportunity.query.get_or_404(id)
    db.session.delete(o)
    db.session.commit()
    return jsonify({"message": "已删除"})
