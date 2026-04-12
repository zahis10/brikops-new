import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from contractor_ops.utils.timezone import IL_TZ
from contractor_ops import reminder_service

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _acquire_daily_lock() -> bool:
    today = datetime.now(IL_TZ).strftime("%Y-%m-%d")
    result = await reminder_service._db.scheduler_locks.update_one(
        {"_id": f"daily_reminders_{today}"},
        {"$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return result.upserted_id is not None


async def _daily_reminders_job():
    logger.info("[SCHEDULER] Starting daily reminders job")

    acquired = await _acquire_daily_lock()
    if not acquired:
        logger.info("[SCHEDULER] Skipping — another worker already ran today's job")
        return

    shabbat = reminder_service.is_shabbat()
    if shabbat:
        logger.info(f"[SCHEDULER] Skipping: {shabbat}")
        return

    try:
        digest_result = await reminder_service.send_all_pm_digests()
        logger.info(
            f"[SCHEDULER] PM digests: sent={digest_result['sent']} "
            f"skipped={digest_result['skipped']} failed={digest_result['failed']}"
        )
    except Exception as e:
        logger.error(f"[SCHEDULER] PM digest error: {e}")

    try:
        contractor_result = await reminder_service.send_all_contractor_reminders()
        logger.info(
            f"[SCHEDULER] Contractor reminders: sent={contractor_result['sent']} "
            f"skipped={contractor_result['skipped']} failed={contractor_result['failed']}"
        )
    except Exception as e:
        logger.error(f"[SCHEDULER] Contractor reminder error: {e}")

    logger.info("[SCHEDULER] Daily reminders job complete")


def start_scheduler():
    scheduler.add_job(
        _daily_reminders_job,
        trigger=CronTrigger(
            day_of_week="sun,mon,tue,wed,thu",
            hour=8,
            minute=0,
            timezone=IL_TZ,
        ),
        id="daily_reminders",
        name="Daily WhatsApp Reminders",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[SCHEDULER] APScheduler started — daily reminders at 08:00 IL (Sun-Thu)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[SCHEDULER] APScheduler stopped")
