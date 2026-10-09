"""定时任务（P0-3）回归。

这里的核心不是业务，而是「任务在 APScheduler 的工作线程里跑」这一事实：
线程内没有 Flask 应用上下文，任务一碰 Model.query / current_app 就会抛
RuntimeError，而异常被调度器吞掉后，外部只表现为"定时任务从没执行过"。
所以每个用例都在**无上下文**状态下直接调用任务函数。
"""
from datetime import datetime, timedelta

import pytest

from app.services import scheduler
from crm_test_utils import set_config

# 固定在中午触发，避开"配置时刻跨天"带来的偶发失败
NOON = datetime(2026, 10, 9, 12, 0, 0)


class _FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOON


@pytest.fixture()
def worker(app, monkeypatch):
    """模拟调度线程：已登记 app，但调用时没有应用上下文。"""
    from flask import has_app_context
    monkeypatch.setattr(scheduler, '_app', app)
    monkeypatch.setattr(scheduler, '_last_triggered_crawl_date', None)
    monkeypatch.setattr(scheduler, 'datetime', _FrozenDateTime)
    assert not has_app_context(), '用例前提：任务必须在没有应用上下文时被调用'
    return app


@pytest.fixture()
def started(app, monkeypatch):
    """拦截真正的采集启动，只记录调用。"""
    from app.services import crawler
    calls = []
    monkeypatch.setattr(crawler, 'start_crawl_background', lambda a: calls.append(a) or True)
    return calls


class TestJobApplicationContext:
    def test_backup_job_writes_file_without_context(self, worker, tmp_path):
        name = scheduler.scheduled_backup_job()
        assert name and name.startswith('crm_auto_') and name.endswith('.db')
        assert (tmp_path / 'backups' / name).is_file()

    def test_backup_job_reports_missing_db(self, worker):
        with worker.app_context():
            worker.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////nonexistent/crm.db'
        assert scheduler.scheduled_backup_job() is None

    def test_crawl_job_can_read_config(self, worker, started):
        """采集任务第一步就查 SystemConfig：没有上下文会直接 RuntimeError。"""
        set_config(worker, crawl_enabled='true', crawl_time='09:00')
        scheduler.scheduled_crawl_job()
        assert started == [worker]


class TestCrawlTiming:
    def test_not_fired_before_configured_time(self, worker, started):
        set_config(worker, crawl_enabled='true', crawl_time='18:00')
        scheduler.scheduled_crawl_job()
        assert started == []

    def test_fires_once_per_day(self, worker, started):
        set_config(worker, crawl_enabled='true', crawl_time='12:00')
        scheduler.scheduled_crawl_job()
        scheduler.scheduled_crawl_job()
        assert len(started) == 1

    def test_disabled_config_never_fires(self, worker, started):
        set_config(worker, crawl_enabled='false', crawl_time='00:00')
        scheduler.scheduled_crawl_job()
        assert started == []

    def test_invalid_time_falls_back_to_default(self, worker):
        set_config(worker, crawl_enabled='true', crawl_time='not-a-time')
        with worker.app_context():
            assert scheduler._crawl_config()[:2] == (True, 8)

    def test_out_of_range_time_falls_back_to_default(self, worker):
        set_config(worker, crawl_enabled='true', crawl_time='25:70')
        with worker.app_context():
            assert scheduler._crawl_config()[:2] == (True, 8)


class TestNextCrawlRun:
    def test_none_when_disabled(self, worker):
        set_config(worker, crawl_enabled='false', crawl_time='08:00')
        with worker.app_context():
            assert scheduler.next_crawl_run() is None

    def test_future_time_shows_today(self, worker):
        set_config(worker, crawl_enabled='true', crawl_time='18:30')
        with worker.app_context():
            nxt = scheduler.next_crawl_run()
        assert (nxt.hour, nxt.minute) == (18, 30)
        assert nxt.date() == NOON.date()

    def test_passed_time_shows_next_watch_tick(self, worker):
        set_config(worker, crawl_enabled='true', crawl_time='08:00')
        with worker.app_context():
            nxt = scheduler.next_crawl_run()
        assert NOON < nxt <= NOON + timedelta(minutes=scheduler.WATCH_INTERVAL_MINUTES)

    def test_after_run_shows_tomorrow(self, worker, monkeypatch):
        set_config(worker, crawl_enabled='true', crawl_time='08:00')
        monkeypatch.setattr(scheduler, '_last_triggered_crawl_date',
                            NOON.strftime('%Y-%m-%d'))
        with worker.app_context():
            nxt = scheduler.next_crawl_run()
        assert nxt.date() == NOON.date() + timedelta(days=1)
        assert (nxt.hour, nxt.minute) == (8, 0)


class TestSchedulerWiring:
    def test_init_registers_jobs_and_thread_can_run_them(self, app, monkeypatch, started):
        """真起一次调度器：任务由调度线程触发时也必须能拿到上下文。"""
        monkeypatch.setattr(scheduler, '_scheduler', None)
        monkeypatch.setattr(scheduler, '_app', None)
        monkeypatch.delenv('CRM_DISABLE_SCHEDULER', raising=False)
        monkeypatch.setattr(scheduler, 'datetime', _FrozenDateTime)
        set_config(app, crawl_enabled='true', crawl_time='09:00')

        sched = scheduler.init_scheduler(app)
        try:
            assert {'scheduled_crawl', 'scheduled_backup'} <= {j.id for j in sched.get_jobs()}
            sched.get_job('scheduled_crawl').func()
            assert started == [app]
        finally:
            sched.shutdown(wait=False)

    def test_skipped_when_disabled(self, app, monkeypatch):
        monkeypatch.setattr(scheduler, '_scheduler', None)
        monkeypatch.setenv('CRM_DISABLE_SCHEDULER', '1')
        assert scheduler.init_scheduler(app) is None
        assert scheduler.get_scheduler() is None
