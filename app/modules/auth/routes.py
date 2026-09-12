from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import Forbidden, Unauthorized
from app.db.models import User
from app.core.security import create_access_token, verify_password
from app.modules.auth.dependencies import get_current_admin
from app.modules.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    user = await session.scalar(select(User).where(User.username == body.username))
    if user is None or not await verify_password(body.password, user.password_hash):
        raise Unauthorized("Invalid credentials")
    if not user.is_admin:
        raise Forbidden("Admin privileges required")
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/token", response_model=TokenResponse)
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Form-based login used by the Swagger UI 'Authorize' button."""
    user = await session.scalar(select(User).where(User.username == form.username))
    if user is None or not await verify_password(form.password, user.password_hash):
        raise Unauthorized("Invalid credentials")
    if not user.is_admin:
        raise Forbidden("Admin privileges required")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(current: User = Depends(get_current_admin)) -> UserOut:
    return UserOut.model_validate(current)
