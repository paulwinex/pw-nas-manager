import asyncio
import os
import sqlite3
from pathlib import Path


def _query(db_path: str, sql: str):
    conn = sqlite3.connect(db_path)
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def test_create_group_and_shares_flow(client, auth, fake_runner, share_root):
    group = client.post("/api/v1/groups", json={"name": "team"}, headers=auth)
    assert group.status_code == 201, group.text
    group_id = group.json()["id"]

    (share_root / "photos").mkdir(exist_ok=True)
    share = client.post("/api/v1/shares", json={"name": "photos"}, headers=auth)
    assert share.status_code == 201, share.text
    share_id = share.json()["id"]

    linked = client.post(
        f"/api/v1/groups/{group_id}/shares",
        json={"share_id": share_id},
        headers=auth,
    )
    assert linked.status_code == 201, linked.text

    shares_in_group = client.get(f"/api/v1/groups/{group_id}/shares", headers=auth)
    assert [s["name"] for s in shares_in_group.json()] == ["photos"]


def test_personal_group_rules(client, auth, fake_runner):
    created = client.post(
        "/api/v1/users", json={"username": "alice", "password": "secret123"}, headers=auth
    ).json()

    personal_groups = client.get("/api/v1/groups", headers=auth)
    personal = next(g for g in personal_groups.json() if g["is_personal"])
    assert personal["name"] == "alice"

    blocked = client.delete(f"/api/v1/groups/{personal['id']}", headers=auth)
    assert blocked.status_code == 409

    bob = client.post(
        "/api/v1/users", json={"username": "bob", "password": "secret123"}, headers=auth
    ).json()

    added_bob = client.post(
        f"/api/v1/groups/{personal['id']}/members",
        json={"user_id": bob["id"], "access_level": "rw"},
        headers=auth,
    )
    assert added_bob.status_code == 409

    removed = client.delete(
        f"/api/v1/groups/{personal['id']}/members/{created['id']}", headers=auth
    )
    assert removed.status_code == 409


def test_available_dirs_lists_unregistered(client, auth, fake_runner, share_root):
    (share_root / "docs").mkdir(exist_ok=True)
    (share_root / "vault").mkdir(exist_ok=True)
    (share_root / "photos").mkdir(exist_ok=True)

    registered = client.post("/api/v1/shares", json={"name": "photos"}, headers=auth)
    assert registered.status_code == 201, registered.text

    available = client.get("/api/v1/shares/available", headers=auth)
    names = available.json()
    assert str(share_root / "docs") in names
    assert str(share_root / "vault") in names
    assert str(share_root / "photos") not in names


def test_duplicate_share_conflict(client, auth, fake_runner, share_root):
    (share_root / "photos").mkdir(exist_ok=True)
    first = client.post("/api/v1/shares", json={"name": "photos"}, headers=auth)
    assert first.status_code == 201, first.text
    second = client.post("/api/v1/shares", json={"name": "photos"}, headers=auth)
    assert second.status_code == 409, second.text


def test_members_rw_and_ro(client, auth, fake_runner, share_root):
    alice = client.post(
        "/api/v1/users", json={"username": "alice", "password": "secret123"}, headers=auth
    ).json()
    bob = client.post(
        "/api/v1/users", json={"username": "bob", "password": "secret123"}, headers=auth
    ).json()
    group = client.post("/api/v1/groups", json={"name": "team"}, headers=auth).json()
    (share_root / "photos").mkdir(exist_ok=True)
    share = client.post("/api/v1/shares", json={"name": "photos"}, headers=auth).json()

    client.post(
        f"/api/v1/groups/{group['id']}/shares",
        json={"share_id": share["id"]},
        headers=auth,
    )

    rw = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"user_id": bob["id"], "access_level": "rw"},
        headers=auth,
    )
    assert rw.status_code == 201, rw.text
    ro = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"user_id": alice["id"], "access_level": "ro"},
        headers=auth,
    )
    assert ro.status_code == 201, ro.text

    from app.modules.samba.sync_engine import compute_target

    async def target():
        from app.core.database import SessionLocal

        async with SessionLocal() as session:
            return await compute_target(session)

    target_state = asyncio.run(target())
    photos = target_state["photos"]
    assert photos.write_list == ["bob"]
    assert photos.read_list == ["alice"]


def test_delete_share_removes_from_registry_on_sync(client, auth, fake_runner, db_path, share_root):
    (share_root / "photos").mkdir(exist_ok=True)
    share = client.post("/api/v1/shares", json={"name": "photos"}, headers=auth).json()
    user = client.post(
        "/api/v1/users", json={"username": "alice", "password": "secret123"}, headers=auth
    ).json()
    group = client.post("/api/v1/groups", json={"name": "team"}, headers=auth).json()
    client.post(
        f"/api/v1/groups/{group['id']}/shares",
        json={"share_id": share["id"]},
        headers=auth,
    )
    client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"user_id": user["id"], "access_level": "rw"},
        headers=auth,
    )

    run = client.post("/api/v1/sync", headers=auth)
    assert run.status_code == 200, run.text
    assert run.json()["added"] == ["photos"]

    fake_runner.set_response("net conf listshares", 0, "photos\n")
    deleted = client.delete(f"/api/v1/shares/{share['id']}", headers=auth)
    assert deleted.status_code == 204, deleted.text

    assert fake_runner.find("net", "conf", "delshare", "photos")
    assert _query(db_path, "SELECT * FROM shares") == []