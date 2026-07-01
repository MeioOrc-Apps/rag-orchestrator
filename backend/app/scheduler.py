import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def create_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(job_defaults={"coalesce": True, "max_instances": 1})


def add_interval_job(
    scheduler: BackgroundScheduler,
    func: Callable,
    interval_minutes: int,
    job_id: str,
) -> None:
    scheduler.add_job(
        func,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=job_id,
        replace_existing=True,
    )
