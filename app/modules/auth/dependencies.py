from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.models import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None or not credentials.credentials:
        raise Unauthorized("Authentication required")
    subject = decode_access_token(credentials.credentials)
    user = await session.get(User, subject)
    if user is None:
        raise Unauthorized("User no longer exists")
    if not user.is_admin:
        raise Forbidden("Admin privileges required")
    return user
