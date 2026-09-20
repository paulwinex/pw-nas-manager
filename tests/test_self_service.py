def _create_user(client, auth, username="alice", password="pass123"):
    resp = client.post(
        "/api/v1/users",
        json={"username": username, "password": password},
        headers=auth,
    )
    assert resp.status_code == 201, resp.text


def _login_user(client, auth, username="alice", password="pass123"):
    _create_user(client, auth, username, password)
    resp = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_my_shares(client, auth, fake_runner):
    """Юзер видит свои шары через /users/me/shares."""
    token = _login_user(client, auth)
    resp = client.get("/api/v1/users/me/shares", headers=_auth(token))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_my_mount_script(client, auth, fake_runner):
    """Юзер получает свой mount-script."""
    token = _login_user(client, auth)
    resp = client.get("/api/v1/users/me/mount-script", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "alice"
    assert "linux_script" in data


def test_my_password_change(client, auth, fake_runner):
    """Юзер меняет свой пароль, старый логин не работает."""
    token = _login_user(client, auth)
    resp = client.post(
        "/api/v1/users/me/password",
        json={"new_password": "newpass"},
        headers=_auth(token),
    )
    assert resp.status_code == 204
    login_resp = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "newpass"}
    )
    assert login_resp.status_code == 200
    old_login = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "pass123"}
    )
    assert old_login.status_code == 401


def test_admin_endpoints_403_for_non_admin(client, auth, fake_runner):
    """Не-admin не может удалить юзера."""
    token = _login_user(client, auth, "alice", "pass123")
    bob = client.post(
        "/api/v1/users",
        json={"username": "bob", "password": "pass123"},
        headers=auth,
    ).json()
    resp = client.delete(f"/api/v1/users/{bob['id']}", headers=_auth(token))
    assert resp.status_code == 403


def test_mount_script_download(client, auth, fake_runner):
    """/users/me/mount-script/download отдаёт файл mount-share.py."""
    token = _login_user(client, auth)
    resp = client.get("/api/v1/users/me/mount-script/download", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.content.startswith(b"#!/usr/bin/env python3")
    assert "nasmount" in resp.text
    assert "mount-share.py" in resp.headers.get("content-disposition", "")