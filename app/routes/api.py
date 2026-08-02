from flask import Blueprint, request, jsonify, abort
from flask import current_app
from app import db
from app.models import (
    Customer, CustomerNews, Lead, Opportunity, OpportunityStage,
    StageRecord, Contact, Activity, KanbanBoard, KanbanColumn,
    KanbanCard, SystemConfig, Skill, FollowUp, ContactNews, CrawlLog
)
from app.services.matcher import match_lead
from app.services.skills import SkillRegistry
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
import requests as http_requests
import json

api = Blueprint('api', __name__)

def _require_fields(d, *fields):
    missing = [f for f in fields if not d.get(f)]
    if missing:
        abort(400, description=f"缺少必填字段: {', '.join(missing)}")

def _parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"日期格式不正确: {text}")

def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"时间格式不正确: {text}")

def _first_board_column():
    board = KanbanBoard.query.order_by(KanbanBoard.id).first()
    if not board:
        return None
    if board.columns:
        return board.columns[0]
    col = KanbanColumn(board_id=board.id, name='待处理', sort_order=0)
    db.session.add(col)
    db.session.flush()
    return col

def _add_kanban_card(title, description='', deadline=None, color='blue',
                     source_type='', source_id=None):
    col = _first_board_column()
    if not col:
        return None
    card = KanbanCard(column_id=col.id, title=title, description=description,
                      deadline=deadline, label_color=color,
                      source_type=source_type, source_id=source_id)
    db.session.add(card)
    return card

@api.route('/skills', methods=['GET'])
def list_skills():
    skills = Skill.query.order_by(Skill.is_builtin.desc(), Skill.created_at).all()
    builtin = SkillRegistry.get_all()
    db_skills = [{"id": s.id, "name": s.name, "description": s.description, "icon": s.icon or "🔧", "is_builtin": s.is_builtin, "is_active": s.is_active, "config_json": s.config_json} for s in skills]
    return jsonify({"builtin": builtin, "custom": db_skills})

@api.route('/skills', methods=['POST'])
def create_skill():
    d = request.get_json()
    if Skill.query.filter_by(name=d['name']).first():
        return jsonify({"error": "技能名称已存在"}), 400
    s = Skill(name=d['name'], description=d.get('description',''), icon=d.get('icon','🔧'), is_builtin=False, is_active=True, config_json=d.get('config_json'))
    db.session.add(s)
    db.session.commit()
    return jsonify({"id": s.id, "name": s.name, "message": "创建成功"})

@api.route('/skills/<int:id>', methods=['PUT'])
def update_skill(id):
    s = Skill.query.get_or_404(id)
    if s.is_builtin:
        return jsonify({"error": "内置技能不可编辑"}), 400
    d = request.get_json()
    if 'name' in d: s.name = d['name']
    if 'description' in d: s.description = d['description']
    if 'icon' in d: s.icon = d['icon']
    if 'config_json' in d: s.config_json = d['config_json']
    db.session.commit()
    return jsonify({"id": s.id, "message": "更新成功"})

@api.route('/skills/<int:id>/toggle', methods=['POST'])
def toggle_skill(id):
    s = Skill.query.get_or_404(id)
    if s.is_builtin:
        return jsonify({"error": "内置技能不可禁用"}), 400
    s.is_active = not s.is_active
    db.session.commit()
    return jsonify({"id": s.id, "is_active": s.is_active, "message": "已" + ("启用" if s.is_active else "禁用")})

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
    leads = Lead.query.options(joinedload(Lead.customer)).filter_by(status='active').all()
    level_score = {'高匹配': 300, '中匹配': 200, '低匹配': 100}
    leads.sort(key=lambda l: -(level_score.get(l.match_level, 0)))
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    today_activities = Activity.query.options(
        joinedload(Activity.contact), joinedload(Activity.customer)
    ).filter(db.func.date(Activity.activity_time) == today).all()
    today_followups = FollowUp.query.options(
        joinedload(FollowUp.contact)
    ).filter(db.func.date(FollowUp.plan_date) == today).all()
    urgent_leads = [l for l in leads if l.deadline and 0 < (l.deadline - now).days <= 3]
    opportunities = Opportunity.query.options(
        joinedload(Opportunity.customer)
    ).order_by(Opportunity.created_at.desc()).all()
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
    customers = Customer.query.options(
        joinedload(Customer.contacts), joinedload(Customer.news_items)
    ).filter_by(is_archived=False)
    if q: customers = customers.filter(Customer.name.contains(q))
    return jsonify([{"id": c.id, "name": c.name, "short_name": c.short_name, "type": c.customer_type, "level": c.level, "region": c.region, "source": c.source, "contact_count": len(c.contacts), "news_count": len(c.news_items)} for c in customers.all()])

@api.route('/customers', methods=['POST'])
def create_customer():
    d = request.get_json() or {}
    _require_fields(d, 'name')
    c = Customer(name=d['name'], short_name=d.get('short_name',''), customer_type=d.get('type',''), level=d.get('level',''), region=d.get('region',''), address=d.get('address',''), website=d.get('website',''), registration_capital=d.get('capital',''), operation_years=d.get('years',''), social_security_count=d.get('social_count'), business_scope=d.get('scope',''), intellectual_property=d.get('ip',''), department=d.get('dept',''), source=d.get('source',''), remark=d.get('remark',''))
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id, "message": "创建成功"})

@api.route('/customers/<int:id>', methods=['GET'])
def get_customer(id):
    c = Customer.query.get_or_404(id)
    return jsonify({"id": c.id, "name": c.name, "short_name": c.short_name, "type": c.customer_type, "level": c.level, "region": c.region, "address": c.address, "website": c.website, "capital": c.registration_capital, "years": c.operation_years, "social_count": c.social_security_count, "scope": c.business_scope, "ip": c.intellectual_property, "dept": c.department, "source": c.source, "remark": c.remark, "contacts": [{"id": ct.id, "name": ct.name, "title": ct.title, "phone": ct.phone, "importance": ct.importance} for ct in c.contacts], "opportunities": [{"id": o.id, "title": o.title, "amount": o.amount, "current_stage": o.current_stage, "probability": o.probability or 20, "expected_close": str(o.expected_close.date()) if o.expected_close else None} for o in c.opportunities], "news": [{"id": n.id, "title": n.title, "date": str(n.publish_date.date()) if n.publish_date else None, "type": n.change_type, "url": n.url, "source_name": n.source_name or '', "event_time": str(n.event_time.date()) if n.event_time else None, "content": (n.content or '')[:300]} for n in c.news_items]})

@api.route('/customers/<int:id>', methods=['PUT'])
def update_customer(id):
    c = Customer.query.get_or_404(id)
    d = request.get_json() or {}
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
    region = request.args.get('region', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    query = Lead.query.options(joinedload(Lead.customer))
    if q: query = query.filter(Lead.title.contains(q))
    if status: query = query.filter_by(status=status)
    if level: query = query.filter_by(match_level=level)
    if region: query = query.filter(Lead.region.contains(region))
    if date_from:
        d = _parse_date(date_from)
        if d: query = query.filter(Lead.created_at >= d)
    if date_to:
        d = _parse_date(date_to)
        if d: query = query.filter(Lead.created_at < d + timedelta(days=1))
    leads = query.order_by(Lead.created_at.desc()).all()
    result = []
    for l in leads:
        days_left = (l.deadline - datetime.now()).days if l.deadline else None
        result.append({"id": l.id, "title": l.title, "bid_number": l.bid_number, "budget": l.budget, "deadline": str(l.deadline.date()) if l.deadline else None, "days_left": days_left, "region": l.region, "purchaser": l.purchaser, "contact_name": l.contact_name or '', "contact_phone": l.contact_phone or '', "address": l.address or '', "service_content": l.service_content, "match_keywords": l.match_keywords, "match_level": l.match_level, "match_score": l.match_score or 0, "match_reason": l.match_reason, "assignee": l.assignee or '', "source_platform": l.source_platform, "source_url": l.source_url, "status": l.status, "customer_id": l.customer_id, "customer_name": l.customer.name if l.customer else None, "created_at": str(l.created_at.date()) if l.created_at else None})
    return jsonify(result)

@api.route('/leads', methods=['POST'])
def create_lead():
    d = request.get_json() or {}
    _require_fields(d, 'title')
    l = Lead(bid_number=d.get('bid_number',''), title=d['title'], budget=d.get('budget',''), deadline=_parse_date(d.get('deadline')), region=d.get('region',''), purchaser=d.get('purchaser',''), contact_name=(d.get('contact_name') or '')[:100], contact_phone=(d.get('contact_phone') or '')[:100], address=(d.get('address') or '')[:300], service_content=d.get('service_content',''), source_url=d.get('source_url',''), source_platform=d.get('source_platform',''), customer_id=d.get('customer_id'))
    match_lead(l)
    db.session.add(l)
    db.session.commit()
    return jsonify({"id": l.id, "message": "创建成功"})

@api.route('/leads/<int:id>', methods=['GET'])
def get_lead(id):
    l = Lead.query.get_or_404(id)
    return jsonify({"id": l.id, "title": l.title, "bid_number": l.bid_number, "budget": l.budget, "deadline": str(l.deadline.date()) if l.deadline else None, "region": l.region, "purchaser": l.purchaser, "contact_name": l.contact_name or '', "contact_phone": l.contact_phone or '', "address": l.address or '', "service_content": l.service_content, "match_keywords": l.match_keywords, "match_level": l.match_level, "match_reason": l.match_reason, "source_platform": l.source_platform, "source_url": l.source_url, "status": l.status, "customer_id": l.customer_id, "customer_name": l.customer.name if l.customer else None})

@api.route('/leads/<int:id>', methods=['PUT'])
def update_lead(id):
    l = Lead.query.get_or_404(id)
    if l.status == 'converted':
        return jsonify({"error": "已转化线索不可修改"}), 400
    d = request.get_json() or {}
    if 'status' in d and d['status'] not in ('active', 'abandoned'):
        return jsonify({"error": "状态无效"}), 400
    for key in ['title','bid_number','budget','region','purchaser','contact_name','contact_phone','address','service_content','match_keywords','match_level','match_score','match_reason','assignee','source_platform','source_url','status','customer_id']:
        if key in d: setattr(l, key, d[key])
    if 'deadline' in d: l.deadline = _parse_date(d.get('deadline'))
    db.session.commit()
    return jsonify({"id": l.id, "message": "更新成功"})

@api.route('/leads/<int:id>/convert', methods=['POST'])
def convert_lead(id):
    l = Lead.query.get_or_404(id)
    if l.status != 'active': return jsonify({"error": "仅待转化线索可转化"}), 400
    d = request.get_json() or {}
    customer_id = d.get('customer_id', l.customer_id)
    # 未选择客户时，自动按线索采购方创建客户
    if not customer_id:
        customer_name = (d.get('customer_name') or l.purchaser or '').strip()
        if customer_name:
            customer = Customer.query.filter_by(name=customer_name, is_archived=False).first()
            if not customer:
                customer = Customer(name=customer_name[:200], source='线索转化自动创建',
                                    remark=f"由线索[{l.title[:60]}]转化时自动创建")
                db.session.add(customer)
                db.session.flush()
            customer_id = customer.id
    contact_id = d.get('contact_id')
    # 未选择联系人时，按线索抽取的联系人自动创建
    contact_name = (d.get('contact_name') or l.contact_name or '').strip()
    if not contact_id and contact_name and customer_id:
        contact = Contact(
            name=contact_name[:100],
            phone=(d.get('contact_phone') or l.contact_phone or '')[:100],
            customer_id=customer_id,
            notes=f"由线索[{l.title[:60]}]转化自动创建",
        )
        db.session.add(contact)
        db.session.flush()
        contact_id = contact.id
    o = Opportunity(lead_id=l.id, customer_id=customer_id, contact_id=contact_id,
                    title=d.get('title', l.title), amount=d.get('amount', l.budget),
                    current_stage=d.get('stage', '初步接触'),
                    source_url=l.source_url or '')
    db.session.add(o)
    l.status = 'converted'
    db.session.commit()
    return jsonify({"id": o.id, "message": "已转为商机"})

@api.route('/leads/<int:id>/abandon', methods=['POST'])
def abandon_lead(id):
    l = Lead.query.get_or_404(id)
    l.status = 'abandoned'
    db.session.commit()
    return jsonify({"message": "已删除，可在已删除中恢复"})

@api.route('/opportunities', methods=['GET'])
def list_opportunities():
    ops = Opportunity.query.options(
        joinedload(Opportunity.customer),
        joinedload(Opportunity.contact),
        joinedload(Opportunity.stage_records),
    ).order_by(Opportunity.created_at.desc()).all()
    return jsonify([{"id": o.id, "title": o.title, "amount": o.amount, "source_url": o.source_url or '', "current_stage": o.current_stage, "probability": o.probability or 20, "expected_close": str(o.expected_close.date()) if o.expected_close else None, "customer_id": o.customer_id, "customer_name": o.customer.name if o.customer else None, "contact_id": o.contact_id, "contact_name": o.contact.name if o.contact else None, "lead_id": o.lead_id, "created_at": str(o.created_at.date()) if o.created_at else None, "stages": [{"stage": s.stage_name, "content": s.content, "deadline": str(s.deadline.date()) if s.deadline else None, "status": s.status, "created_at": str(s.created_at.date()) if s.created_at else None} for s in o.stage_records]} for o in ops])

@api.route('/opportunities/<int:id>', methods=['GET'])
def get_opportunity(id):
    o = Opportunity.query.options(
        joinedload(Opportunity.stage_records),
        joinedload(Opportunity.activities).joinedload(Activity.contact),
        joinedload(Opportunity.customer),
        joinedload(Opportunity.contact),
    ).get_or_404(id)
    lead = Lead.query.get(o.lead_id) if o.lead_id else None
    return jsonify({"id": o.id, "title": o.title, "amount": o.amount, "source_url": o.source_url or (lead.source_url if lead else '') or '', "current_stage": o.current_stage, "probability": o.probability or 20, "expected_close": str(o.expected_close.date()) if o.expected_close else None, "customer_id": o.customer_id, "customer_name": o.customer.name if o.customer else None, "contact_id": o.contact_id, "contact_name": o.contact.name if o.contact else None, "lead_id": o.lead_id, "lead_title": lead.title if lead else None, "stages": [{"id": s.id, "stage": s.stage_name, "content": s.content, "deadline": str(s.deadline.date()) if s.deadline else None, "status": s.status, "add_to_kanban": s.add_to_kanban} for s in o.stage_records], "activities": [{"id": a.id, "time": str(a.activity_time.date()) if a.activity_time else None, "method": a.method, "content": a.content, "contact_name": a.contact.name if a.contact else None, "next_followup_time": str(a.next_followup_time.date()) if a.next_followup_time else None, "next_followup_content": a.next_followup_content} for a in sorted(o.activities, key=lambda x: x.activity_time or datetime.min)]})

@api.route('/opportunities/<int:id>/stages', methods=['POST'])
def add_stage_record(id):
    o = Opportunity.query.get_or_404(id)
    d = request.get_json() or {}
    record = StageRecord(opportunity_id=o.id, stage_name=d.get('stage_name',''), content=d.get('content',''), status='pending', add_to_kanban=d.get('add_to_kanban', False))
    record.deadline = _parse_date(d.get('deadline'))
    if d.get('status'): record.status = d['status']
    o.current_stage = record.stage_name
    db.session.add(record)
    if record.add_to_kanban:
        db.session.flush()
        _add_kanban_card(
            title=record.stage_name and f"[{record.stage_name}] {o.title[:50]}" or o.title,
            description=record.content,
            deadline=record.deadline,
            source_type='stage',
            source_id=record.id,
        )
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
    customer_id = request.args.get('customer_id', '')
    query = Contact.query.options(joinedload(Contact.customer))
    if q: query = query.filter(Contact.name.contains(q))
    if customer_id: query = query.filter_by(customer_id=int(customer_id))
    return jsonify([{"id": c.id, "name": c.name, "title": c.title, "phone": c.phone, "email": c.email, "wechat": c.wechat, "role": c.role or '', "tags": c.tags or '', "avatar": c.avatar or c.name[0] if c.name else '', "importance": c.importance, "customer_id": c.customer_id, "customer_name": c.customer.name if c.customer else None, "business_scope": c.business_scope, "notes": c.notes} for c in query.all()])

@api.route('/contacts', methods=['POST'])
def create_contact():
    d = request.get_json() or {}
    _require_fields(d, 'name')
    c = Contact(name=d['name'], title=d.get('title',''), phone=d.get('phone',''), email=d.get('email',''), wechat=d.get('wechat',''), role=d.get('role',''), tags=d.get('tags',''), avatar=d.get('avatar','') or (d['name'][0] if d.get('name') else ''), importance=d.get('importance',''), customer_id=d.get('customer_id'), business_scope=d.get('business_scope',''), notes=d.get('notes',''))
    db.session.add(c)
    db.session.commit()
    return jsonify({"id": c.id, "message": "创建成功"})

@api.route('/contacts/<int:id>', methods=['GET'])
def get_contact(id):
    c = Contact.query.get_or_404(id)
    customer = c.customer
    news = [{"id": n.id, "title": n.title, "date": str(n.publish_date.date()) if n.publish_date else None, "url": n.url} for n in customer.news_items] if customer else []
    contact_news = [{"id": n.id, "title": n.title, "url": n.url, "source_name": n.source_name or '', "date": str(n.publish_date.date()) if n.publish_date else None, "event_time": str(n.event_time.date()) if n.event_time else None, "summary": n.summary or '', "crawled_at": str(n.crawled_at) if n.crawled_at else None} for n in c.news_items]
    return jsonify({"id": c.id, "name": c.name, "title": c.title, "phone": c.phone, "email": c.email, "wechat": c.wechat, "importance": c.importance, "customer_id": c.customer_id, "customer_name": customer.name if customer else None, "business_scope": c.business_scope, "notes": c.notes, "news": news, "contact_news": contact_news})

@api.route('/contacts/<int:id>', methods=['PUT'])
def update_contact(id):
    c = Contact.query.get_or_404(id)
    d = request.get_json() or {}
    for key in ['name','title','phone','email','wechat','role','tags','avatar','importance','customer_id','business_scope','notes']:
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
    customer_id = request.args.get('customer_id', '')
    opportunity_id = request.args.get('opportunity_id', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    query = Activity.query.options(
        joinedload(Activity.customer), joinedload(Activity.contact),
        joinedload(Activity.opportunity), joinedload(Activity.lead),
    )
    if q: query = query.filter(Activity.content.contains(q))
    if method: query = query.filter_by(method=method)
    if customer_id:
        try: query = query.filter_by(customer_id=int(customer_id))
        except ValueError: pass
    if opportunity_id:
        try: query = query.filter_by(opportunity_id=int(opportunity_id))
        except ValueError: pass
    if date_from:
        d = _parse_date(date_from)
        if d: query = query.filter(Activity.activity_time >= d)
    if date_to:
        d = _parse_date(date_to)
        if d: query = query.filter(Activity.activity_time < d + timedelta(days=1))
    acts = query.order_by(Activity.activity_time.desc()).all()
    return jsonify([{"id": a.id, "title": a.title, "method": a.method, "content": a.content, "activity_time": str(a.activity_time) if a.activity_time else None, "next_followup_time": str(a.next_followup_time.date()) if a.next_followup_time else None, "next_followup_content": a.next_followup_content, "customer_id": a.customer_id, "customer_name": a.customer.name if a.customer else None, "contact_id": a.contact_id, "contact_name": a.contact.name if a.contact else None, "opportunity_id": a.opportunity_id, "opportunity_title": a.opportunity.title if a.opportunity else None, "lead_id": a.lead_id} for a in acts])

@api.route('/activities', methods=['POST'])
def create_activity():
    d = request.get_json() or {}
    a = Activity(title=d.get('title',''), customer_id=d.get('customer_id'), contact_id=d.get('contact_id'), opportunity_id=d.get('opportunity_id'), lead_id=d.get('lead_id'), method=d.get('method',''), content=d.get('content',''), activity_time=_parse_datetime(d.get('time')) or datetime.now(), next_followup_time=_parse_date(d.get('next_time')), next_followup_content=d.get('next_content',''), add_to_kanban=d.get('add_to_kanban', False))
    db.session.add(a)
    if a.add_to_kanban:
        db.session.flush()
        _add_kanban_card(
            title=d.get('content','')[:60] or d.get('title','') or '活动跟进',
            description=f"活动: {d.get('method','')} | 客户: {a.customer.name if a.customer else '-'}",
            deadline=a.next_followup_time,
            source_type='activity',
            source_id=a.id,
        )
    db.session.commit()
    # Auto-create follow-up with source activity info
    if d.get('next_time'):
        fu_content = d.get('next_content', '') or f"跟进: {d.get('content', '')[:80]}"
        ai_suggested = f"来源于活动记录 [{(d.get('method','') or '活动')}] 客户: {a.customer.name if a.customer else '-'} | 内容: {d.get('content','')[:100]}"
        fu = FollowUp(
            contact_id=d.get('contact_id'),
            customer_id=d.get('customer_id'),
            opportunity_id=d.get('opportunity_id'),
            plan_date=_parse_date(d.get('next_time')),
            content=fu_content,
            ai_suggested_content=ai_suggested,
            source_activity_id=a.id,
            add_to_kanban=d.get('add_to_kanban', False)
        )
        db.session.add(fu)
        if fu.add_to_kanban:
            db.session.flush()
            _add_kanban_card(
                title=fu_content[:60],
                description=ai_suggested[:100],
                deadline=fu.plan_date,
                source_type='followup',
                source_id=fu.id,
            )
        db.session.commit()
    return jsonify({"id": a.id, "message": "创建成功"})

@api.route('/activities/<int:id>', methods=['GET'])
def get_activity(id):
    a = Activity.query.get_or_404(id)
    return jsonify({"id": a.id, "title": a.title, "method": a.method, "content": a.content, "activity_time": str(a.activity_time) if a.activity_time else None, "next_followup_time": str(a.next_followup_time.date()) if a.next_followup_time else None, "next_followup_content": a.next_followup_content, "customer_id": a.customer_id, "customer_name": a.customer.name if a.customer else None, "contact_id": a.contact_id, "contact_name": a.contact.name if a.contact else None, "opportunity_id": a.opportunity_id, "opportunity_title": a.opportunity.title if a.opportunity else None, "lead_id": a.lead_id})

@api.route('/activities/<int:id>', methods=['PUT'])
def update_activity(id):
    a = Activity.query.get_or_404(id)
    d = request.get_json() or {}
    for key in ['title','method','content','next_followup_content','customer_id','contact_id','opportunity_id','lead_id']:
        if key in d: setattr(a, key, d[key])
    if 'time' in d: a.activity_time = _parse_datetime(d.get('time')) or a.activity_time
    if 'next_time' in d:
        a.next_followup_time = _parse_date(d.get('next_time'))
        fu = FollowUp.query.filter_by(source_activity_id=a.id).first()
        if fu and a.next_followup_time:
            fu.plan_date = a.next_followup_time
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
    customer_id = request.args.get('customer_id', '')
    contact_id = request.args.get('contact_id', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    query = FollowUp.query.options(
        joinedload(FollowUp.customer), joinedload(FollowUp.contact),
        joinedload(FollowUp.opportunity), joinedload(FollowUp.lead),
        joinedload(FollowUp.source_activity),
    )
    if q: query = query.filter(FollowUp.content.contains(q))
    if customer_id:
        try: query = query.filter_by(customer_id=int(customer_id))
        except ValueError: pass
    if contact_id:
        try: query = query.filter_by(contact_id=int(contact_id))
        except ValueError: pass
    if status == 'pending': query = query.filter(FollowUp.actual_date.is_(None))
    elif status == 'done': query = query.filter(FollowUp.actual_date.isnot(None))
    if date_from:
        d = _parse_date(date_from)
        if d: query = query.filter(FollowUp.plan_date >= d)
    if date_to:
        d = _parse_date(date_to)
        if d: query = query.filter(FollowUp.plan_date < d + timedelta(days=1))
    items = query.order_by(FollowUp.plan_date).all()
    return jsonify([{
        "id": f.id, "contact_id": f.contact_id, "opportunity_id": f.opportunity_id, "lead_id": f.lead_id,
        "contact_name": f.contact.name if f.contact else None,
        "customer_id": f.customer_id,
        "customer_name": f.customer.name if f.customer else None,
        "opportunity_title": f.opportunity.title if f.opportunity else None,
        "plan_date": str(f.plan_date) if f.plan_date else None,
        "content": f.content, "ai_suggested_content": f.ai_suggested_content,
        "actual_date": str(f.actual_date) if f.actual_date else None,
        "actual_content": f.actual_content, "source_activity_id": f.source_activity_id,
        "add_to_kanban": f.add_to_kanban,
        "source_activity_content": f.source_activity.content[:100] if f.source_activity else None,
        "source_activity_method": f.source_activity.method if f.source_activity else None,
        "source_activity_time": str(f.source_activity.activity_time) if f.source_activity else None
    } for f in items])

@api.route('/followups', methods=['POST'])
def create_followup():
    d = request.get_json() or {}
    f = FollowUp(
        contact_id=d.get('contact_id'), customer_id=d.get('customer_id'),
        opportunity_id=d.get('opportunity_id'),
        plan_date=_parse_date(d.get('plan_date')),
        content=d.get('content',''), ai_suggested_content=d.get('ai_content',''),
        add_to_kanban=d.get('add_to_kanban', False)
    )
    db.session.add(f)
    if f.add_to_kanban:
        db.session.flush()
        _add_kanban_card(
            title=f.content[:60] or '跟进计划',
            description=f.ai_suggested_content[:100] if f.ai_suggested_content else '',
            deadline=f.plan_date,
            source_type='followup',
            source_id=f.id,
        )
    db.session.commit()
    return jsonify({"id": f.id, "message": "创建成功"})

@api.route('/followups/<int:id>', methods=['GET'])
def get_followup(id):
    f = FollowUp.query.options(
        joinedload(FollowUp.customer), joinedload(FollowUp.contact),
        joinedload(FollowUp.opportunity), joinedload(FollowUp.lead),
    ).get_or_404(id)
    # 该客户/联系人此前的联系记录（供"详情"展示历史）
    history = Activity.query.options(
        joinedload(Activity.contact)
    ).filter(Activity.customer_id == f.customer_id)
    if f.contact_id:
        history = history.filter(Activity.contact_id == f.contact_id)
    history = history.order_by(Activity.activity_time.desc()).limit(20).all()
    return jsonify({
        "id": f.id, "contact_id": f.contact_id, "opportunity_id": f.opportunity_id, "lead_id": f.lead_id,
        "contact_name": f.contact.name if f.contact else None,
        "customer_id": f.customer_id,
        "customer_name": f.customer.name if f.customer else None,
        "opportunity_title": f.opportunity.title if f.opportunity else None,
        "plan_date": str(f.plan_date.date()) if f.plan_date else None,
        "content": f.content, "ai_suggested_content": f.ai_suggested_content,
        "actual_date": str(f.actual_date.date()) if f.actual_date else None,
        "actual_content": f.actual_content, "source_activity_id": f.source_activity_id,
        "history": [{"id": a.id, "time": str(a.activity_time.date()) if a.activity_time else None,
                     "method": a.method, "content": a.content,
                     "contact_name": a.contact.name if a.contact else None,
                     "next_followup_time": str(a.next_followup_time.date()) if a.next_followup_time else None}
                    for a in history],
    })

@api.route('/followups/<int:id>/execute', methods=['POST'])
def execute_followup(id):
    """执行联络计划：标记完成，并把本次联系内容写入日常联络记录。"""
    f = FollowUp.query.get_or_404(id)
    if f.actual_date:
        return jsonify({"error": "该计划已完成，不能重复执行"}), 400
    d = request.get_json() or {}
    content = (d.get('actual_content') or '').strip()
    if not content:
        return jsonify({"error": "请填写本次联系内容"}), 400
    now = datetime.now()
    f.actual_date = now
    f.actual_content = content
    a = Activity(
        customer_id=f.customer_id, contact_id=f.contact_id, opportunity_id=f.opportunity_id,
        lead_id=f.lead_id, method=d.get('method', '电话') or '电话',
        content=content,
        activity_time=now,
        next_followup_time=_parse_date(d.get('next_time')),
        next_followup_content=d.get('next_content', ''),
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({"id": f.id, "activity_id": a.id, "message": "已记录本次联络，并在日常联络中可见"})

@api.route('/followups/<int:id>', methods=['PUT'])
def update_followup(id):
    f = FollowUp.query.get_or_404(id)
    d = request.get_json() or {}
    for key in ['content', 'ai_suggested_content', 'actual_content', 'add_to_kanban', 'contact_id', 'customer_id', 'opportunity_id']:
        if key in d: setattr(f, key, d[key])
    if 'plan_date' in d: f.plan_date = _parse_date(d.get('plan_date'))
    if 'actual_date' in d: f.actual_date = _parse_date(d.get('actual_date'))
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

@api.route('/customers/<int:id>/collect-news', methods=['POST'])
def collect_customer_news_api(id):
    from app.services.news_collector import collect_customer_news
    try:
        r = collect_customer_news(id)
        return jsonify({"ok": True, **r})
    except Exception as e:
        return jsonify({"ok": False, "error": f"采集失败: {str(e)[:200]}"}), 200

@api.route('/contacts/<int:id>/collect-news', methods=['POST'])
def collect_contact_news_api(id):
    from app.services.news_collector import collect_contact_news
    try:
        r = collect_contact_news(id)
        return jsonify({"ok": True, **r})
    except Exception as e:
        return jsonify({"ok": False, "error": f"采集失败: {str(e)[:200]}"}), 200

@api.route('/news/collect-all', methods=['POST'])
def collect_all_news_api():
    from app.services.news_collector import collect_all
    d = request.get_json() or {}
    kind = d.get('type', 'all')
    try:
        r = collect_all(kind)
        return jsonify({"ok": True, "message": f"批量采集完成，新增 {r['count']} 条", **r})
    except Exception as e:
        return jsonify({"ok": False, "error": f"批量采集失败: {str(e)[:200]}"}), 200

@api.route('/news/logs', methods=['GET'])
def news_logs():
    logs = CrawlLog.query.order_by(CrawlLog.started_at.desc()).limit(50).all()
    return jsonify([{
        "id": l.id, "task_type": l.task_type, "sources": l.sources,
        "status": l.status, "items_count": l.items_count, "error_count": l.error_count,
        "message": l.message,
        "started_at": str(l.started_at) if l.started_at else None,
        "finished_at": str(l.finished_at) if l.finished_at else None,
    } for l in logs])

@api.route('/news/customer/<int:id>', methods=['DELETE'])
def delete_customer_news(id):
    n = CustomerNews.query.get_or_404(id)
    db.session.delete(n)
    db.session.commit()
    return jsonify({"message": "已删除"})

@api.route('/news/contact/<int:id>', methods=['DELETE'])
def delete_contact_news(id):
    n = ContactNews.query.get_or_404(id)
    db.session.delete(n)
    db.session.commit()
    return jsonify({"message": "已删除"})

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
    q = request.args.get('search', '')
    query = KanbanBoard.query
    if q:
        query = query.filter(KanbanBoard.name.contains(q))
    boards = query.all()
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

@api.route('/kanban/cards/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    card = KanbanCard.query.get_or_404(card_id)
    db.session.delete(card)
    db.session.commit()
    return jsonify({"ok": True})

@api.route('/kanban/import', methods=['POST'])
def import_to_kanban():
    d = request.get_json() or {}
    board_id = d.get('board_id')
    items = d.get('items', [])
    if not items:
        abort(400, description="items 不能为空")
    board = KanbanBoard.query.get_or_404(board_id)
    target_col = board.columns[0] if board.columns else None
    if not target_col:
        target_col = KanbanColumn(board_id=board_id, name='待处理', sort_order=0)
        db.session.add(target_col)
        db.session.flush()
    for item in items:
        card = KanbanCard(column_id=target_col.id, title=item.get('title',''), description=item.get('description',''), label_color=item.get('color','blue'), deadline=_parse_date(item.get('deadline')), source_type=item.get('source_type',''), source_id=item.get('source_id'))
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

@api.route('/config/test-ai', methods=['POST'])
def test_ai_connection():
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    api_key = configs.get('ai_api_key', '')
    endpoint = configs.get('ai_api_endpoint', 'https://api.openai.com/v1')
    model = configs.get('ai_model', 'gpt-4o')
    if not api_key:
        return jsonify({"ok": False, "error": "请先配置 API Key"}), 400
    try:
        resp = http_requests.post(
            endpoint.rstrip('/') + '/chat/completions',
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "hello"}], "max_tokens": 10},
            timeout=180
        )
        if resp.status_code == 200:
            return jsonify({"ok": True, "message": f"连接成功！模型 {model} 响应正常", "model": model})
        else:
            return jsonify({"ok": False, "error": f"连接失败 (HTTP {resp.status_code}): {resp.text[:200]}"}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": f"连接异常: {str(e)}"}), 200

@api.route('/config/crawl-targets', methods=['GET'])
def get_crawl_targets():
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    targets = configs.get('crawl_targets', '')
    if targets:
        try:
            return jsonify(json.loads(targets))
        except:
            pass
    return jsonify([
        {"name": "中国政府采购网", "url": "http://search.ccgp.gov.cn/bxsearch", "enabled": True, "keywords": "无人机,林业,病虫害,巡检"},
        {"name": "中国采购与招标网", "url": "https://www.chinabidding.com", "enabled": False, "keywords": "无人机,林业"},
    ])

@api.route('/config/crawl-targets', methods=['PUT'])
def save_crawl_targets():
    d = request.get_json()
    config = SystemConfig.query.filter_by(key='crawl_targets').first()
    val = json.dumps(d, ensure_ascii=False)
    if config: config.value = val
    else:
        config = SystemConfig(key='crawl_targets', value=val, description='爬取目标站点配置')
        db.session.add(config)
    db.session.commit()
    return jsonify({"message": "爬取站点已保存"})

@api.route('/crawl', methods=['POST'])
def trigger_crawl():
    from app.services.crawler import start_crawl_background
    started = start_crawl_background(current_app._get_current_object())
    if started:
        return jsonify({"ok": True, "running": True, "message": "采集已启动，正在抓取并 AI 分析..."})
    return jsonify({"ok": False, "running": True, "error": "采集已在运行中，请稍候"}), 200

@api.route('/crawl/status', methods=['GET'])
def crawl_status():
    from app.services.crawler import get_crawl_status
    return jsonify(get_crawl_status())

@api.route('/ai/urgent-tasks', methods=['GET'])
def get_urgent_tasks():
    """AI 分析联系记录与项目数据，生成当日跟进方案（带 30 分钟缓存）。"""
    from app.services.ai_client import generate_daily_plan
    now = datetime.now()
    cached = SystemConfig.query.filter_by(key='ai_urgent_tasks').first()
    cached_at = SystemConfig.query.filter_by(key='ai_urgent_tasks_at').first()
    ts = None
    if cached_at and cached_at.value:
        try:
            ts = datetime.strptime(cached_at.value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            ts = None
    if cached and cached.value and ts and (now - ts).total_seconds() < 1800:
        try:
            return jsonify({"ok": True, "source": "cache", "generated_at": cached_at.value,
                            **json.loads(cached.value)})
        except (json.JSONDecodeError, TypeError):
            pass
    try:
        plan = generate_daily_plan()
        store = SystemConfig.query.filter_by(key='ai_urgent_tasks').first()
        if store:
            store.value = json.dumps(plan, ensure_ascii=False)
        else:
            store = SystemConfig(key='ai_urgent_tasks', value=json.dumps(plan, ensure_ascii=False),
                                 description='AI 每日跟进方案')
            db.session.add(store)
        at = SystemConfig.query.filter_by(key='ai_urgent_tasks_at').first()
        ts_str = now.strftime('%Y-%m-%d %H:%M:%S')
        if at:
            at.value = ts_str
        else:
            at = SystemConfig(key='ai_urgent_tasks_at', value=ts_str, description='AI 方案生成时间')
            db.session.add(at)
        db.session.commit()
        return jsonify({"ok": True, "source": "ai", "generated_at": ts_str, **plan})
    except Exception as e:
        return jsonify({"ok": False, "error": f"AI 分析失败: {str(e)[:200]}"}), 200

@api.route('/ai/urgent-tasks/refresh', methods=['POST'])
def refresh_urgent_tasks():
    SystemConfig.query.filter_by(key='ai_urgent_tasks_at').delete()
    db.session.commit()
    return get_urgent_tasks()

@api.route('/leads/<int:id>', methods=['DELETE'])
def delete_lead(id):
    l = Lead.query.get_or_404(id)
    db.session.delete(l)
    db.session.commit()
    return jsonify({"message": "已删除"})

@api.route('/opportunities', methods=['POST'])
def create_opportunity():
    d = request.get_json() or {}
    _require_fields(d, 'title')
    o = Opportunity(title=d['title'], customer_id=d.get('customer_id'), contact_id=d.get('contact_id'), amount=d.get('amount',''), source_url=d.get('source_url','') or '', current_stage=d.get('current_stage','初步接触'), probability=d.get('probability', 20), expected_close=_parse_date(d.get('expected_close')))
    db.session.add(o)
    db.session.commit()
    return jsonify({"id": o.id, "message": "创建成功"})

@api.route('/opportunities/<int:id>', methods=['PUT'])
def update_opportunity(id):
    o = Opportunity.query.get_or_404(id)
    d = request.get_json() or {}
    for key in ['title','amount','current_stage','customer_id','contact_id','probability','source_url']:
        if key in d: setattr(o, key, d[key])
    if 'expected_close' in d:
        o.expected_close = _parse_date(d.get('expected_close'))
    db.session.commit()
    return jsonify({"id": o.id, "message": "更新成功"})

@api.route('/opportunities/<int:id>', methods=['DELETE'])
def delete_opportunity(id):
    o = Opportunity.query.get_or_404(id)
    db.session.delete(o)
    db.session.commit()
    return jsonify({"message": "已删除"})

@api.route('/options', methods=['GET'])
def get_options():
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    def parse_list(key, default):
        val = configs.get(key, '')
        if val:
            try:
                return json.loads(val)
            except:
                return [v.strip() for v in val.split(',') if v.strip()]
        return default
    return jsonify({
        "customer_types": parse_list('opt_customer_types', ['政府部门', '事业单位', '国有企业', '民营企业', '科研院所', '其他']),
        "customer_levels": parse_list('opt_customer_levels', ['A-重点客户', 'B-重要客户', 'C-一般客户', 'D-潜在客户']),
        "regions": parse_list('opt_regions', ['北京','上海','重庆','天津','河北','山西','辽宁','吉林','黑龙江','江苏','浙江','安徽','福建','江西','山东','河南','湖北','湖南','广东','海南','四川','贵州','云南','陕西','甘肃','青海','内蒙古','广西','西藏','宁夏','新疆']),
    })

@api.route('/leads/<int:id>/claim', methods=['POST'])
def claim_lead(id):
    l = Lead.query.get_or_404(id)
    if l.status != 'pool':
        return jsonify({"error": "仅公海池线索可领取"}), 400
    d = request.get_json() or {}
    l.status = 'active'
    l.assignee = d.get('assignee', '李明')
    db.session.commit()
    return jsonify({"id": l.id, "message": f"已领取线索: {l.title[:30]}"})

@api.route('/leads/<int:id>/release', methods=['POST'])
def release_lead(id):
    l = Lead.query.get_or_404(id)
    l.status = 'pool'
    l.assignee = ''
    db.session.commit()
    return jsonify({"message": "已释放至公海池"})

@api.route('/analytics', methods=['GET'])
def analytics():
    from sqlalchemy import func as sa_func
    import re as _re
    def safe_amount(val):
        if not val: return 0.0
        m = _re.search(r'[\d.]+', str(val))
        return float(m.group()) if m else 0.0
    leads = Lead.query.all()
    opportunities = Opportunity.query.all()
    activities = Activity.query.all()
    # Monthly leads trend (last 6 months)
    monthly = []
    now = datetime.now()
    for i in range(5, -1, -1):
        d = now - timedelta(days=30*i)
        month_str = d.strftime('%Y-%m')
        month_leads = [l for l in leads if l.created_at and l.created_at.strftime('%Y-%m') == month_str]
        converted = [l for l in month_leads if l.status == 'converted']
        monthly.append({"month": d.strftime('%m月'), "leads": len(month_leads), "converted": len(converted)})
    # Funnel by stage: 优先使用配置阶段，并补充数据中出现的其他阶段
    configured = [s.name for s in OpportunityStage.query.order_by(OpportunityStage.sort_order).all()]
    seen = [o.current_stage for o in opportunities if o.current_stage]
    stages_list = configured + [s for s in seen if s not in configured]
    funnel = []
    for s in stages_list:
        stage_opps = [o for o in opportunities if o.current_stage == s]
        total_amount = sum(safe_amount(o.amount) for o in stage_opps)
        funnel.append({"stage": s, "count": len(stage_opps), "amount": total_amount})
    # Win/loss
    won = len([o for o in opportunities if o.current_stage in ('合同签订', '合同签约')])
    lost = len([o for o in opportunities if o.current_stage == '已丢单'])
    active = len(opportunities) - won - lost
    win_loss = [{"name": "赢单", "value": won}, {"name": "进行中", "value": active}, {"name": "丢单", "value": lost}]
    # Summary stats
    total_amount = sum(safe_amount(o.amount) for o in opportunities)
    won_amount = sum(safe_amount(o.amount) for o in opportunities if o.current_stage == '合同签订')
    conversion_rate = round(len([l for l in leads if l.status == 'converted']) / max(len(leads), 1) * 100, 1)
    return jsonify({
        "summary": {"total_leads": len(leads), "total_opportunities": len(opportunities), "total_amount": total_amount, "won_amount": won_amount, "conversion_rate": conversion_rate, "total_activities": len(activities)},
        "monthly_leads": monthly,
        "funnel": funnel,
        "win_loss": win_loss
    })
