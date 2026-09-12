from tests.conftest import login


def test_login_success_returns_bearer_token(client):
    response = login(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_401(client):
    response = login(client, password="nope")
    assert response.status_code == 401


def test_login_unknown_user_401(client):
    response = login(client, username="ghost", password="whatever")
    assert response.status_code == 401


def test_non_admin_cannot_login(client, auth, fake_runner):
    created = client.post(
        "/api/v1/users",
        json={"username": "bob", "password": "secret123"},
        headers=auth,
    )
    assert created.status_code == 201, created.text

    response = login(client, username="bob", password="secret123")
    assert response.status_code == 403

    token_form = client.post(
        "/api/v1/auth/token",
        data={"username": "bob", "password": "secret123"},
    )
    assert token_form.status_code == 403


def test_token_form_endpoint_for_swagger_authorize(client, fake_runner):
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    wrong = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "nope"},
    )
    assert wrong.status_code == 401

    missing = client.post(
        "/api/v1/auth/token",
        data={"username": "ghost", "password": "x"},
    )
    assert missing.status_code == 401

    admin_token = body["access_token"]
    users = client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert users.status_code == 200, users.text


def test_users_endpoints_require_auth(client):
    assert client.get("/api/v1/users").status_code == 401
    bad = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/api/v1/users", headers=bad).status_code == 401
