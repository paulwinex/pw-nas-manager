from __future__ import annotations

import httpx


class ApiError(Exception):
    def __init__(self, status: int, detail: str = ""):
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status}: {detail}")


class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=10)

    def login(self, username: str, password: str) -> dict:
        resp = self.client.post(
            "/api/v1/auth/token",
            data={"username": username, "password": password},
        )
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def refresh(self, refresh_token: str) -> dict:
        resp = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        if resp.status_code != 200:
            raise ApiError(resp.status_code, resp.text)
        return resp.json()

    def list_shares(self, access_token: str) -> list[dict]:
        resp = self.client.get(
            "/api/v1/users/me/shares",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code == 401:
            raise ApiError(401)
        resp.raise_for_status()
        return resp.json()