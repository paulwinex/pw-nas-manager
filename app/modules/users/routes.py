from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.modules.auth.dependencies import get_current_admin
from app.modules.users import services
from app.modules.users.schemas import (
    MountScriptResponse,
    PasswordChange,
    UserCreate,
    UserOut,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_session)) -> list[UserOut]:
    users = await services.list_users(session)
    return [UserOut.model_validate(u) for u in users]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate, session: AsyncSession = Depends(get_session)
) -> UserOut:
    user = await services.create_user(session, body)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: str, session: AsyncSession = Depends(get_session)
) -> UserOut:
    user = await services.get_user(session, user_id)
    return UserOut.model_validate(user)


@router.post("/{user_id}/password", response_model=UserOut)
async def change_password(
    body: PasswordChange,
    user_id: str,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    user = await services.change_password(session, user_id, body.new_password)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    await services.delete_user(session, user_id)


@router.get("/{username}/mount-script", response_model=MountScriptResponse)
async def mount_script(
    username: str,
    session: AsyncSession = Depends(get_session),
) -> MountScriptResponse:
    data = await services.build_mount_script(session, username)
    return MountScriptResponse.model_validate(data)
