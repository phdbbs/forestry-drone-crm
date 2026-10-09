"""APScheduler 常驻调度：定时采集 + 定时备份。

设计：
- 单例保护：多次 create_app（测试/热重载）不会重复起调度器；
- 测试隔离：CRM_DISABLE_SCHEDULER=1 时完全跳过（conftest 里设置）；
- 采集任务每次触发时实时读 SystemConfig（crawl_enabled/crawl_time），
  设置页改配置无需重启即生效；
- 备份用 sqlite3 backup API（对 WAL 库安全），保留最近 N 份。

重要：APScheduler 的工作线程没有任何 Flask 上下文，而任务体要用
Model.query 和 current_app.logger，所以所有任务都必须经 @_job 包一层
app context——否则一触发就 RuntimeError，而且异常被调度器吞掉，
表面上只看得到"定时任务没跑"。
"""
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = None
_app = None
_last_triggered_crawl_date = None  # 每日只跑一次：服务中途重启不至于重复采集

BACKUP_KEEP = 14
# 采集用「每 10 分钟看一次」而不是直接按 crawl_time 排程：
# 服务在采集时刻之后才重启时当天仍能补跑一次，同时配置改动无需重新排程。
WATCH_INTERVAL_MINUTES = 10


def get_scheduler():
    return _scheduler


def _job(fn):
    """把任务包成带 app context 的可调用对象。

    已在上下文里（例如设置页「立即备份」由请求线程直接调用）就直接执行，
    避免重复 push 以及测试环境（禁用调度器、没有 _app）下变成静默空跑。
    """
    @wraps(fn)
    def wrapper():
        from flask import current_app, has_app_context
        if has_app_context():
            return fn()
        if _app is None:
            # 既没有上下文也没有已登记的 app：此时连日志都要走 stdlib，
            # 用 current_app 会再抛一次 RuntimeError 把真实原因盖掉
            logging.getLogger('crm.scheduler').error(
                '定时任务 %s 无法执行：调度器未初始化' % fn.__name__)
            return None
        with _app.app_context():
            try:
                return fn()
            finally:
                # 工作线程是复用的：不回收会话会把这条线程的连接一直挂在库上
                from app import db
                db.session.remove()
    return wrapper


def _crawl_config():
    from app.models import SystemConfig
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    enabled = (configs.get('crawl_enabled') or 'false').lower() in ('1', 'true', 'yes', 'on')
    time_str = (configs.get('crawl_time') or '08:00').strip()
    try:
        hh, mm = [int(x) for x in time_str.split(':')[:2]]
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError
    except (ValueError, TypeError):
        hh, mm = 8, 0
    return enabled, hh, mm


def _crawl_target(now, hh, mm):
    """今天应该执行采集的时刻（配置只给到时分）。"""
    return now.replace(hour=hh, minute=mm, second=0, microsecond=0)


def _next_watch_tick(now):
    """下一个「每 10 分钟」观察点。"""
    step = WATCH_INTERVAL_MINUTES - (now.minute % WATCH_INTERVAL_MINUTES)
    tick = (now + timedelta(minutes=step)).replace(second=0, microsecond=0)
    return tick


def next_crawl_run():
    """下一次采集的实际时刻，供设置页显示。

    job.next_run_time 只会是观察点（每 10 分钟一个），拿来当"下次采集时间"会误导，
    所以这里按配置算：今天还没到点就显示今天，到点未跑就是下个观察点，
    今天已跑过则是明天同一时刻。
    """
    enabled, hh, mm = _crawl_config()
    if not enabled:
        return None
    now = datetime.now()
    target = _crawl_target(now, hh, mm)
    if _last_triggered_crawl_date == now.strftime('%Y-%m-%d'):
        return target + timedelta(days=1)
    if target > now:
        return target
    return _next_watch_tick(now)


@_job
def scheduled_crawl_job():
    """观察点任务：到点且当天未跑则触发采集。"""
    global _last_triggered_crawl_date
    from app.services.crawler import start_crawl_background
    from flask import current_app

    enabled, hh, mm = _crawl_config()
    if not enabled:
        return None
    now = datetime.now()
    if now < _crawl_target(now, hh, mm):
        return None  # 还没到配置时刻
    today = now.strftime('%Y-%m-%d')
    if _last_triggered_crawl_date == today:
        return None  # 当天已跑过（含手动采集后重启等场景）
    _last_triggered_crawl_date = today
    if start_crawl_background(current_app._get_current_object()):
        current_app.logger.info(f'定时采集已触发（计划时刻 {hh:02d}:{mm:02d}）')
    else:
        current_app.logger.info('定时采集跳过：已有采集任务在跑')
    return None


@_job
def scheduled_backup_job():
    """每日备份：sqlite3 backup API（WAL 安全）→ instance/backups/，保留最近 BACKUP_KEEP 份。

    返回备份文件名；未执行（找不到库等）返回 None，便于「立即备份」如实回报结果。
    """
    from flask import current_app

    app = current_app._get_current_object()
    db_path = app.config.get('SQLALCHEMY_DATABASE_URI', '').replace('sqlite:///', '')
    if not db_path or not os.path.isfile(db_path):
        app.logger.warning(f'自动备份跳过：数据库文件不存在（{db_path or "未配置"}）')
        return None
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = f'crm_auto_{stamp}.db'
    target = os.path.join(backup_dir, name)
    try:
        src = sqlite3.connect(db_path)
        try:
            dst = sqlite3.connect(target)
            with dst:
                src.backup(dst)
            dst.close()
        finally:
            src.close()
        olds = sorted(f for f in os.listdir(backup_dir) if f.startswith('crm_auto_'))
        for f in olds[:-BACKUP_KEEP]:
            try:
                os.remove(os.path.join(backup_dir, f))
            except OSError:
                pass
        app.logger.info(f'自动备份完成: {target}')
        return name
    except Exception as e:
        app.logger.error(f'自动备份失败: {e}')
        try:
            os.remove(target)  # 失败常常只留下半个文件
        except OSError:
            pass
        return None


def init_scheduler(app):
    """在 create_app 末尾调用。生产环境启动每日定时任务。"""
    global _scheduler, _app
    if os.environ.get('CRM_DISABLE_SCHEDULER') == '1':
        return None
    if _scheduler is not None:
        return _scheduler  # 已启动（多 app 场景复用）
    _app = app
    _scheduler = BackgroundScheduler(timezone='Asia/Shanghai', daemon=True)

    _scheduler.add_job(scheduled_crawl_job, 'interval', minutes=WATCH_INTERVAL_MINUTES,
                       id='scheduled_crawl', max_instances=1, coalesce=True,
                       misfire_grace_time=WATCH_INTERVAL_MINUTES * 60)
    _scheduler.add_job(scheduled_backup_job, 'cron', hour=2, minute=30, id='scheduled_backup',
                       max_instances=1, coalesce=True, misfire_grace_time=3600)
    _scheduler.start()
    app.logger.info(
        f'定时任务已启动：采集（每 {WATCH_INTERVAL_MINUTES} 分钟检查一次配置时刻）'
        '/ 备份（每日 02:30）')
    return _scheduler
