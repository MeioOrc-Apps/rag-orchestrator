import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def create_and_configure_scheduler(
    interval_minutes: int,
    job_func: Callable,
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(
        job_defaults={"coalesce": True, "max_instances": 1}
    )
    scheduler.add_job(
        job_func,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="sync_pipeline",
        replace_existing=True,
    )
    return scheduler
