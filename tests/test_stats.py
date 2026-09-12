from datetime import datetime, timedelta, timezone


def test_stats_requires_auth(client):
    assert client.get("/api/v1/stats").status_code == 401


def test_stats_counts_and_expiring(client, auth, fake_runner):
    user = client.post(
        "/api/v1/users", headers=auth, json={"username": "zuser", "password": "secret123"}
    )
    assert user.status_code == 201, user.text
    group = client.post("/api/v1/groups", headers=auth, json={"name": "zteam"})
    assert group.status_code == 201, group.text
    share = client.post("/api/v1/shares", headers=auth, json={"name": "zdata"})
    assert share.status_code == 201, share.text

    expires = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    member = client.post(
        f"/api/v1/groups/{group.json()['id']}/members",
        headers=auth,
        json={"user_id": user.json()["id"], "access_level": "rw", "expires_at": expires},
    )
    assert member.status_code == 201, member.text

    stats = client.get("/api/v1/stats", headers=auth)
    assert stats.status_code == 200
    body = stats.json()
    assert body["users_count"] == 2  # admin + zuser
    assert body["admins_count"] == 1
    assert body["groups_count"] == 1
    assert body["shares_count"] == 1
    assert body["memberships_count"] == 1
    assert body["registry_shares_count"] == 0
    assert len(body["expiring_memberships"]) == 1
    exp = body["expiring_memberships"][0]
    assert exp["username"] == "zuser"
    assert exp["group_name"] == "zteam"
    assert exp["access_level"] == "rw"


def test_stats_excludes_far_expiry(client, auth, fake_runner):
    user = client.post(
        "/api/v1/users", headers=auth, json={"username": "zuser2", "password": "secret123"}
    ).json()
    group = client.post("/api/v1/groups", headers=auth, json={"name": "zteam2"}).json()
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    client.post(
        f"/api/v1/groups/{group['id']}/members",
        headers=auth,
        json={"user_id": user["id"], "access_level": "ro", "expires_at": expires},
    )
    body = client.get("/api/v1/stats", headers=auth).json()
    assert body["expiring_memberships"] == []
