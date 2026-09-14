from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.models import User

bearer_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token", auto_error=False
)


async def get_current_admin(
    token: str | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if token is None:
        raise Unauthorized("Authentication required")
    subject = decode_access_token(token)
    user = await session.get(User, subject)
    if user is None:
        raise Unauthorized("User no longer exists")
    if not user.is_admin:
        raise Forbidden("Admin privileges required")
    return user


async def get_current_user(
    token: str | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if token is None:
        raise Unauthorized("Authentication required")
    subject = decode_access_token(token)
    user = await session.get(User, subject)
    if user is None:
        raise Unauthorized("User no longer exists")
    return user
