from app import db
from app.models import Lead, Opportunity, FollowUp, StageRecord
from datetime import datetime, timedelta, date

def generate_suggestions():
    suggestions = []
    today = date.today()

    # Suggest follow-ups for leads with approaching deadlines
    leads = Lead.query.filter_by(status='active').all()
    for lead in leads:
        if lead.deadline:
            days_left = (lead.deadline.date() - today).days
            if 0 < days_left <= 7:
                suggestions.append({
                    'type': 'lead_deadline',
                    'title': f'线索即将截止: {lead.title[:50]}',
                    'content': f'距离报名截止还有 {days_left} 天，建议尽快跟进',
                    'priority': 'high' if days_left <= 3 else 'medium',
                    'date': lead.deadline.strftime('%Y-%m-%d')
                })
            elif days_left <= 0:
                suggestions.append({
                    'type': 'lead_deadline',
                    'title': f'线索已截止: {lead.title[:50]}',
                    'content': '报名已截止，建议标记废弃或转为商机',
                    'priority': 'low',
                    'date': lead.deadline.strftime('%Y-%m-%d')
                })

    # Suggest follow-ups for opportunities with approaching stage deadlines
    records = StageRecord.query.filter(
        StageRecord.deadline.isnot(None),
        StageRecord.status != 'completed'
    ).all()
    for record in records:
        if record.opportunity and record.deadline:
            days_left = (record.deadline.date() - today).days
            if 0 < days_left <= 5:
                suggestions.append({
                    'type': 'opportunity_deadline',
                    'title': f'商机阶段即将到期: {record.opportunity.title[:50]}',
                    'content': f'阶段 [{record.stage_name}] 还有 {days_left} 天到期',
                    'priority': 'high' if days_left <= 2 else 'medium',
                    'date': record.deadline.strftime('%Y-%m-%d')
                })

    # Suggest follow-ups for contacts without recent contact
    from app.models import Contact
    stale_contacts = Contact.query.all()
    for contact in stale_contacts:
        last_followup = FollowUp.query.filter_by(
            contact_id=contact.id
        ).order_by(FollowUp.plan_date.desc()).first()

        if last_followup and last_followup.plan_date:
            days_since = (today - last_followup.plan_date.date()).days
            if days_since >= 14:
                suggestions.append({
                    'type': 'stale_contact',
                    'title': f'联系人久未联络: {contact.name}',
                    'content': f'上次联络已过去 {days_since} 天，建议安排跟进',
                    'priority': 'medium',
                    'date': (today + timedelta(days=1)).strftime('%Y-%m-%d')
                })
        elif not last_followup:
            suggestions.append({
                'type': 'new_contact',
                'title': f'新联系人待联络: {contact.name}',
                'content': '该联系人尚未有过联络记录',
                'priority': 'low',
                'date': (today + timedelta(days=3)).strftime('%Y-%m-%d')
            })

    # Sort by priority and date
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    suggestions.sort(key=lambda x: (priority_order.get(x['priority'], 3), x['date']))

    return suggestions
