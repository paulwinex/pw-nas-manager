from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    code = "app_error"
    status_code = 500

    def __init__(self, detail: str = "") -> None:
        self.detail = detail or self.__class__.__doc__ or ""
        super().__init__(self.detail)


class NotFound(AppError):
    """Resource not found."""

    code = "not_found"
    status_code = 404


class Conflict(AppError):
    """Operation conflicts with existing state."""

    code = "conflict"
    status_code = 409


class Unauthorized(AppError):
    """Authentication required or failed."""

    code = "unauthorized"
    status_code = 401


class Forbidden(AppError):
    """Not enough permissions."""

    code = "forbidden"
    status_code = 403


class SambaCommandError(AppError):
    """Samba/OS command failed."""

    code = "samba_command_failed"
    status_code = 502

    def __init__(self, detail: str = "", cmd: str = "") -> None:
        super().__init__(f"{cmd}: {detail}" if cmd else detail)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "detail": exc.detail},
        )
