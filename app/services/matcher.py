HIGH_MATCH_KEYWORDS = ["无人机飞行检查","无人机林区巡检","航拍核查","林区审计","AI病虫害算法识别","无人机巡检"]
LOW_MATCH_KEYWORDS = ["林木砍伐","清运","消杀施工"]
ALL_KEYWORDS = ["松材线虫病防治","林业病虫害监测","无人机巡检","无人机飞行检查","林业航拍核查","林区审计巡检","无人机","林业","病虫害","巡检","航拍","林区","森林","防治","监测"]

def match_lead(lead):
    content = f"{lead.title} {lead.service_content or ''}"
    matched = [kw for kw in ALL_KEYWORDS if kw in content]
    high = [kw for kw in HIGH_MATCH_KEYWORDS if kw in content]
    low = [kw for kw in LOW_MATCH_KEYWORDS if kw in content]
    lead.match_keywords = ",".join(matched) if matched else ""
    if high and not low:
        lead.match_level = "高匹配"
        lead.match_score = min(95, 70 + len(high) * 8 + len(matched) * 3)
        lead.match_reason = f"包含高匹配关键词: {', '.join(high)}"
    elif low and not high:
        lead.match_level = "低匹配"
        lead.match_score = max(15, 30 - len(low) * 5)
        lead.match_reason = f"仅含低匹配关键词: {', '.join(low)}"
    elif matched:
        lead.match_level = "中匹配"
        lead.match_score = min(75, 40 + len(matched) * 7)
        lead.match_reason = f"匹配关键词: {', '.join(matched)}"
    else:
        lead.match_level = "低匹配"
        lead.match_score = 10
        lead.match_reason = "未匹配到业务关键词"
