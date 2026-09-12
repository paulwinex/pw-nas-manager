from fastapi import APIRouter

from app.modules.auth.routes import router as auth_router
from app.modules.users.routes import router as users_router

api_router = APIRouter()


@api_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


api_router.include_router(auth_router)
api_router.include_router(users_router)
