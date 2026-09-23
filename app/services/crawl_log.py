"""采集日志记录器：统一「开始 → 逐条记错 → 收尾」的落库流程。

设计要点：
1. **先落库、再采集**：任务一开始就写入一条 status='running' 的记录，
   即使线程随后崩溃、进程被回收，也能在日志里看到「这次采集发生过、未收尾」。
2. **收尾绝不反噬采集**：所有 commit 都包在 try/except 里。曾经正是
   「日志写入失败把采集事务一起拖垮」导致连接池污染，这里不再重演。
3. **报错即分类**：调用方只需提供 {stage, target, raw}，分类交给
   error_classifier，落库时同时存明细与按类型汇总。
"""
import json
from datetime import datetime, timedelta

from app import db
from app.models import CrawlLog
from app.services.error_classifier import classify_record, summarize

# 明细上限：单条 raw 已截断到 600 字符，这里再兜一层总长度，避免日志行过大
_MAX_DETAIL_CHARS = 60000
# 启动时超过这个时长仍在 running 的记录，视为进程中断
_STALE_MINUTES = 10


def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def loads(text, default):
    """安全解析 JSON 文本列，坏数据一律回退默认值。"""
    if not text:
        return default
    try:
        val = json.loads(text)
        return val if isinstance(val, type(default)) else default
    except (ValueError, TypeError):
        return default


def start_log(task_type, sources='', keywords='', range_start='', range_end=''):
    """创建一条 running 状态日志并立即提交，返回 CrawlLog 实例（可能为 None）。"""
    try:
        log = CrawlLog(
            task_type=(task_type or '采集')[:50],
            sources=(sources or '')[:500],
            keywords=(keywords or '')[:500],
            range_start=str(range_start or '')[:30],
            range_end=str(range_end or '')[:30],
            status='running',
            items_count=0,
            error_count=0,
            started_at=datetime.now(),
        )
        db.session.add(log)
        db.session.commit()
        return log
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def finish_log(log, items_count=0, errors=None, status=None, message=''):
    """收尾：分类报错、写汇总、计算耗时。返回写入的统计信息 dict。

    status 为空时按「有错则 partial / 全错则 failed」自动判定。
    """
    records = [classify_record(e) for e in (errors or [])]
    summary = summarize(records)

    if status is None:
        if not records:
            status = 'success'
        elif items_count > 0:
            status = 'partial'
        else:
            status = 'failed'

    result = {
        'status': status, 'items_count': items_count,
        'error_count': len(records), 'error_types': summary,
    }
    if log is None:
        return result

    try:
        log.items_count = int(items_count or 0)
        log.error_count = len(records)
        log.status = status
        log.message = (message or '')[:2000]
        if records:
            detail_text = _dumps(records)
            log.error_detail = detail_text[:_MAX_DETAIL_CHARS]
        else:
            log.error_detail = ''
        log.error_types = _dumps(summary) if summary else ''
        if log.started_at:
            log.duration_ms = max(0, int((datetime.now() - log.started_at).total_seconds() * 1000))
        log.finished_at = datetime.now()
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
    return result


def mark_stale_logs(minutes=_STALE_MINUTES):
    """启动时把上次进程遗留的 running 记录标记为 interrupted。"""
    cutoff = datetime.now() - timedelta(minutes=minutes)
    rows = CrawlLog.query.filter(CrawlLog.status == 'running').all()
    changed = 0
    for log in rows:
        if log.started_at and log.started_at > cutoff:
            continue  # 可能是另一个进程正在跑，别误伤
        log.status = 'interrupted'
        log.finished_at = log.finished_at or datetime.now()
        suffix = '（进程中断，未正常收尾）'
        log.message = ((log.message or '') + suffix)[:2000]
        changed += 1
    if changed:
        db.session.commit()
    return changed
