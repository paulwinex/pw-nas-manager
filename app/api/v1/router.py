from pydantic import BaseModel

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.settings import get_settings
from app.modules.auth.dependencies import get_current_admin
from app.modules.auth.routes import router as auth_router
from app.modules.groups.routes import router as groups_router
from app.modules.groups.services import sweep_expired_memberships
from app.modules.samba.sync_engine import SyncReport, registry_state, sync
from app.modules.shares.routes import router as shares_router
from app.modules.stats.routes import router as stats_router
from app.modules.users.routes import router as users_router

api_router = APIRouter()


class SweepResponse(BaseModel):
    processed: int
    sync: SyncReport | None


class ConfigResponse(BaseModel):
    nas_host: str


@api_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@api_router.get(
    "/config",
    response_model=ConfigResponse,
    dependencies=[Depends(get_current_admin)],
)
def get_config() -> ConfigResponse:
    return ConfigResponse(nas_host=get_settings().nas_host)


@api_router.post(
    "/sync",
    response_model=SyncReport,
    dependencies=[Depends(get_current_admin)],
)
async def run_sync(session: AsyncSession = Depends(get_session)) -> SyncReport:
    return await sync(session)


@api_router.post(
    "/expirations/sweep",
    response_model=SweepResponse,
    dependencies=[Depends(get_current_admin)],
)
async def run_expiry_sweep(
    session: AsyncSession = Depends(get_session),
) -> SweepResponse:
    processed = await sweep_expired_memberships(session)
    report = await sync(session) if processed else None
    return SweepResponse(processed=processed, sync=report)


@api_router.get(
    "/registry/shares",
    dependencies=[Depends(get_current_admin)],
)
async def get_registry_state() -> dict[str, dict[str, str]]:
    return await registry_state()


api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(groups_router)
api_router.include_router(shares_router)
api_router.include_router(stats_router)