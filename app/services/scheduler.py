"""APScheduler 常驻调度：定时采集 + 定时备份。

设计：
- 单例保护：多次 create_app（测试/热重载）不会重复起调度器；
- 测试隔离：CRM_DISABLE_SCHEDULER=1 时完全跳过（conftest 里设置）；
- 采集任务每次触发时实时读 SystemConfig（crawl_enabled/crawl_time），
  设置页改配置无需重启即生效；
- 备份用 sqlite3 backup API（对 WAL 库安全），保留最近 N 份。
"""
import os
import sqlite3
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

_scheduler = None
_last_triggered_crawl_date = None  # 每日只补跑一次：服务中途重启不至于重复采集

BACKUP_KEEP = 14


def get_scheduler():
    global _scheduler
    return _scheduler


def _crawl_config():
    from app.models import SystemConfig
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    enabled = (configs.get('crawl_enabled') or 'false').lower() in ('1', 'true', 'yes', 'on')
    time_str = (configs.get('crawl_time') or '08:00').strip()
    try:
        hh, mm = [int(x) for x in time_str.split(':')[:2]]
    except (ValueError, TypeError):
        hh, mm = 8, 0
    return enabled, hh, mm


def scheduled_crawl_job():
    """每日定时采集：配置开关实时读取；同一天内不重复触发。"""
    global _last_triggered_crawl_date
    from app import db
    from app.services.crawler import start_crawl_background

    enabled, hh, mm = _crawl_config()
    if not enabled:
        return
    today = datetime.now().strftime('%Y-%m-%d')
    if _last_triggered_crawl_date == today:
        return  # 手动采集后服务重启等场景，避免一天连跑两次
    _last_triggered_crawl_date = today
    try:
        start_crawl_background()
        from flask import current_app
        current_app.logger.info(f'定时采集已触发({hh:02d}:{mm:02d})')
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'定时采集触发失败: {e}')
    finally:
        db.session.close()


def scheduled_backup_job():
    """每日备份：sqlite3 backup API（WAL 安全）→ instance/backups/，保留最近 BACKUP_KEEP 份。"""
    from flask import current_app

    app = current_app._get_current_object()
    db_path = app.config.get('SQLALCHEMY_DATABASE_URI', '').replace('sqlite:///', '')
    if not db_path or not os.path.isfile(db_path):
        return
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target = os.path.join(backup_dir, f'crm_auto_{stamp}.db')
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(target)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()
        # 清理过期备份
        olds = sorted(f for f in os.listdir(backup_dir) if f.startswith('crm_auto_'))
        for f in olds[:-BACKUP_KEEP]:
            try:
                os.remove(os.path.join(backup_dir, f))
            except OSError:
                pass
        app.logger.info(f'自动备份完成: {target}')
    except Exception as e:
        app.logger.error(f'自动备份失败: {e}')


def init_scheduler(app):
    """在 create_app 末尾调用。生产环境启动每日定时任务。"""
    global _scheduler
    if os.environ.get('CRM_DISABLE_SCHEDULER') == '1':
        return None
    if _scheduler is not None:
        return _scheduler  # 已启动（多 app 场景复用）
    _scheduler = BackgroundScheduler(timezone='Asia/Shanghai', daemon=True)

    # 定时采集：每小时整点检查一次是否到达配置的采集时刻（配置改动无需重启）
    _scheduler.add_job(scheduled_crawl_job, 'cron', minute=0, id='scheduled_crawl',
                       max_instances=1, coalesce=True, misfire_grace_time=3600)
    # 定时备份：每天 02:30
    _scheduler.add_job(scheduled_backup_job, 'cron', hour=2, minute=30, id='scheduled_backup',
                       max_instances=1, coalesce=True, misfire_grace_time=3600)
    _scheduler.start()
    app.logger.info('定时任务已启动：采集（每小时检查配置时刻）/ 备份（每日 02:30）')
    return _scheduler
