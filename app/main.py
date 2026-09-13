from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.v1.router import api_router
from app.core.database import SessionLocal, init_db
from app.core.exceptions import register_exception_handlers
from app.core.settings import get_settings
from app.db.models import User
from app.core.security import hash_password
from app.core.scheduler import start_scheduler, stop_scheduler
from app.modules.samba import os_manager


async def seed_admin() -> None:
    settings = get_settings()
    async with SessionLocal() as session:
        has_admin = await session.scalar(
            select(User.id).where(User.is_admin.is_(True)).limit(1)
        )
        if has_admin is not None:
            return
        session.add(
            User(
                username=settings.admin_username,
                password_hash=await hash_password(settings.admin_password),
                is_admin=True,
            )
        )
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_admin()
    try:
        await os_manager.reconcile_samba_users()
    except Exception:
        logging.getLogger("app.startup").exception(
            "samba user reconciliation failed, continuing"
        )
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(title="NAS Manager", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    dist_dir = Path(get_settings().ui_dist_dir)
    if dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="ui")
    return app


app = create_app()
