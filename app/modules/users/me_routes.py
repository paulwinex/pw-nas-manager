from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.db.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.users import services
from app.modules.users.schemas import MountScriptResponse, PasswordChange, ShareOutMe

router = APIRouter(
    prefix="/users/me",
    tags=["self-service"],
    dependencies=[Depends(get_current_user)],
)

MOUNT_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "mount_script" / "mount-share.py"


public_router = APIRouter(prefix="/users/me", tags=["self-service"])


@router.get("/shares", response_model=list[ShareOutMe])
async def my_shares(
    current: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ShareOutMe]:
    shares = await services.list_user_shares(session, current.username)
    return [ShareOutMe(**s) for s in shares]


@router.get("/mount-script", response_model=MountScriptResponse)
async def my_mount_script(
    current: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MountScriptResponse:
    data = await services.build_mount_script(session, current.username)
    return MountScriptResponse(**data)


@router.post("/password", status_code=204)
async def change_my_password(
    body: PasswordChange,
    current: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    await services.change_password(session, current.id, body.new_password)


@public_router.get("/mount-script/download")
async def download_mount_script() -> FileResponse:
    if not MOUNT_SCRIPT_PATH.exists():
        raise HTTPException(status_code=404, detail="Mount script not found")
    return FileResponse(
        MOUNT_SCRIPT_PATH,
        filename="mount-share.py",
        media_type="text/plain; charset=utf-8",
        content_disposition_type="inline",
    )
