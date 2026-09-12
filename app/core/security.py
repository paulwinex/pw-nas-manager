from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi.concurrency import run_in_threadpool

from app.core.exceptions import Unauthorized
from app.core.settings import get_settings


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_hash_password, password)


async def verify_password(password: str, password_hash: str) -> bool:
    return await run_in_threadpool(_verify_password, password, password_hash)


def create_access_token(subject: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        raise Unauthorized("Invalid or expired token")
    return payload["sub"]
