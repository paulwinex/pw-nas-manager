from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token_expiry,
    create_refresh_token_value,
    hash_token,
    verify_password,
)
from app.db.models import RefreshToken, User
from app.modules.auth.dependencies import get_current_user
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_session)
) -> LoginResponse:
    user = await session.scalar(select(User).where(User.username == body.username))
    if user is None or not await verify_password(body.password, user.password_hash):
        raise Unauthorized("Invalid credentials")
    # Убрана проверка is_admin — доступны любые учётные записи

    access = create_access_token(user.id)

    refresh_value = create_refresh_token_value()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_value),
        expires_at=create_refresh_token_expiry(),
    )
    session.add(rt)
    await session.commit()

    return LoginResponse(access_token=access, refresh_token=refresh_value)


@router.post("/token", response_model=LoginResponse)
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    """Form-based login used by the Swagger UI 'Authorize' button."""
    user = await session.scalar(select(User).where(User.username == form.username))
    if user is None or not await verify_password(form.password, user.password_hash):
        raise Unauthorized("Invalid credentials")
    # Убрана проверка is_admin

    access = create_access_token(user.id)

    refresh_value = create_refresh_token_value()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_value),
        expires_at=create_refresh_token_expiry(),
    )
    session.add(rt)
    await session.commit()

    return LoginResponse(access_token=access, refresh_token=refresh_value)


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current)


@router.post("/refresh", response_model=LoginResponse)
async def refresh(
    body: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> LoginResponse:
    token_hash = hash_token(body.refresh_token)
    rt = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    if rt is None:
        raise Unauthorized("Invalid refresh token")

    now = datetime.now(timezone.utc)
    expires_at = rt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        await session.delete(rt)
        await session.commit()
        raise Unauthorized("Refresh token expired")

    # Rotation: удалить старый, создать новый
    await session.delete(rt)
    await session.flush()

    user = await session.get(User, rt.user_id)
    if user is None:
        raise Unauthorized("User no longer exists")

    access = create_access_token(user.id)
    refresh_value = create_refresh_token_value()
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_value),
        expires_at=create_refresh_token_expiry(),
    )
    session.add(new_rt)
    await session.commit()

    return LoginResponse(access_token=access, refresh_token=refresh_value)
