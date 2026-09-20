from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    share_host_path: Path = Path("./share")
    share_mount_path: Path = Path("/mnt/share")

    db_path: str = "/data/app.db"
    samba_service_user: str = "service-user"
    workgroup: str = "WORKGROUP"
    nas_host: str = "nas"
    # Host SMB port for mount scripts (matches the published port in compose.yml)
    nas_port: int = 1445

    jwt_secret: str = "change-me-in-dev"
    jwt_ttl_minutes: int = 60

    admin_username: str = "admin"
    admin_password: str = "admin123"

    expiry_check_interval_seconds: int = 60
    refresh_ttl_minutes: int = 10080  # 7 days

    ui_dist_dir: Path = Path("./ui-dist")


@lru_cache
def get_settings() -> Settings:
    return Settings()
