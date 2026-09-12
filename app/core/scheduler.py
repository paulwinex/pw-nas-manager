from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler()


async def expiry_sweep_job() -> None:
    from app.core.database import SessionLocal
    from app.core.settings import get_settings
    from app.modules.groups.services import sweep_expired_memberships
    from app.modules.samba.sync_engine import sync

    settings = get_settings()
    async with SessionLocal() as session:
        processed = await sweep_expired_memberships(session)
        if processed:
            await sync(session)


def start_scheduler() -> None:
    from app.core.settings import get_settings

    settings = get_settings()
    if not scheduler.running:
        scheduler.add_job(
            expiry_sweep_job,
            trigger=IntervalTrigger(
                seconds=settings.expiry_check_interval_seconds
            ),
            id="expiry_sweep",
            replace_existing=True,
        )
        scheduler.start()
        return
    scheduler.reschedule_job(
        "expiry_sweep",
        trigger=IntervalTrigger(seconds=settings.expiry_check_interval_seconds),
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)