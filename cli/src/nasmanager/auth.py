from __future__ import annotations

from nasmanager.api import ApiClient, ApiError
from nasmanager.config import Config


def login_or_refresh(config: Config, api: ApiClient) -> str:
    """Вернуть валидный access_token. Если access_token протух — refresh, если refresh тоже — login (выбрасывает ApiError 401)."""
    if config.access_token:
        try:
            api.list_shares(config.access_token)
            return config.access_token
        except ApiError as e:
            if e.status != 401:
                raise

    if config.refresh_token:
        try:
            tokens = api.refresh(config.refresh_token)
            config.access_token = tokens["access_token"]
            config.refresh_token = tokens["refresh_token"]
            config.save()
            return config.access_token
        except ApiError:
            pass

    raise ApiError(401, "Need interactive login")