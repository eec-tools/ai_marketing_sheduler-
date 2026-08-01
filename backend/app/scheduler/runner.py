from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler():
    from app.scheduler.jobs import check_and_publish_due_posts

    scheduler.add_job(
        check_and_publish_due_posts,
        trigger=IntervalTrigger(seconds=settings.SCHEDULER_INTERVAL_SECONDS),
        id="check_due_posts",
        name="Check and publish due posts",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping runs
    )
    scheduler.start()
    logger.info(f"[Scheduler] Started. Running every {settings.SCHEDULER_INTERVAL_SECONDS}s")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("[Scheduler] Stopped")
