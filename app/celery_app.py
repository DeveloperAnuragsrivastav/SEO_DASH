from __future__ import annotations
"""Celery application — infrastructure only, no tasks defined yet."""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "ez_rankings",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.rankings", "app.tasks.ai_visibility", "app.tasks.cost_guardrail", "app.tasks.links"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="timezone.utc",
    enable_utc=True,
    beat_schedule={
        "dummy-task-every-minute": {
            "task": "test_celery_task",
            "schedule": crontab(minute="*"),
        },
        "reconcile-sync-runs-hourly": {
            "task": "reconcile_sync_runs",
            "schedule": crontab(minute="0"),
        },
        "aggregate-daily-cost-eod": {
            "task": "aggregate_daily_cost",
            "schedule": crontab(minute="55", hour="23"),
        },
        "check-links-monthly": {
            "task": "check_all_links_liveness",
            "schedule": crontab(day_of_month="1", hour="0", minute="0"),
        },
    },
)
