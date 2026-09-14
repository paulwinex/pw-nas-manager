import httpx
import pytest

from nasmanager.api import ApiClient, ApiError


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/v1/auth/token" and request.method == "POST":
        return httpx.Response(200, json={"access_token": "tok", "refresh_token": "ref", "token_type": "bearer"})
    if request.url.path == "/api/v1/users/me/shares" and request.method == "GET":
        auth = request.headers.get("authorization", "")
        if "Bearer tok" in auth:
            return httpx.Response(200, json=[{"name": "photos", "host": "nas", "port": 1445, "access": "RO"}])
        return httpx.Response(401, json={"detail": "Unauthorized"})
    if request.url.path == "/api/v1/auth/refresh" and request.method == "POST":
        return httpx.Response(200, json={"access_token": "newtok", "refresh_token": "newref", "token_type": "bearer"})
    return httpx.Response(404)


def _make_api():
    api = ApiClient(base_url="http://test")
    api.client = httpx.Client(transport=httpx.MockTransport(_mock_handler), base_url="http://test")
    return api


def test_login():
    api = _make_api()
    result = api.login("alice", "pass")
    assert result["access_token"] == "tok"


def test_list_shares_ok():
    api = _make_api()
    shares = api.list_shares("tok")
    assert shares[0]["name"] == "photos"


def test_list_shares_401():
    api = _make_api()
    with pytest.raises(ApiError) as exc:
        api.list_shares("badtoken")
    assert exc.value.status == 401


def test_refresh():
    api = _make_api()
    tokens = api.refresh("oldref")
    assert tokens["access_token"] == "newtok"