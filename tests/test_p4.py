import asyncio
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select


def _query(db_path: str, sql: str) -> list:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(sql).fetchall()
    conn.close()
    return rows


def _make_team(client, auth):
    alice = client.post(
        "/api/v1/users", json={"username": "alice", "password": "secret123"}, headers=auth
    ).json()
    bob = client.post(
        "/api/v1/users", json={"username": "bob", "password": "secret123"}, headers=auth
    ).json()
    group = client.post("/api/v1/groups", json={"name": "team"}, headers=auth).json()
    (Path(os.environ["SHARE_MOUNT_PATH"]) / "photos").mkdir(exist_ok=True)
    share = client.post("/api/v1/shares", json={"name": "photos"}, headers=auth).json()
    client.post(
        f"/api/v1/groups/{group['id']}/shares",
        json={"share_id": share["id"]},
        headers=auth,
    )
    return alice, bob, group, share


def test_member_expiration_swept_by_api(client, auth, fake_runner, db_path):
    alice, bob, group, _ = _make_team(client, auth)
    expired = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={
            "user_id": alice["id"],
            "access_level": "ro",
            "expires_at": "2020-01-01T00:00:00Z",
        },
        headers=auth,
    )
    assert expired.status_code == 201, expired.text
    running = client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"user_id": bob["id"], "access_level": "ro"},
        headers=auth,
    )
    assert running.status_code == 201, running.text

    members = client.get(f"/api/v1/groups/{group['id']}/members", headers=auth).json()
    by_name = {m["username"]: m for m in members}
    assert by_name["alice"]["expires_at"] is not None
    assert by_name["bob"]["expires_at"] is None

    sweep = client.post("/api/v1/expirations/sweep", headers=auth)
    assert sweep.status_code == 200, sweep.text
    assert sweep.json()["processed"] == 1

    remaining = client.get(f"/api/v1/groups/{group['id']}/members", headers=auth).json()
    assert [m["username"] for m in remaining] == ["bob"]
    membership_rows = _query(
        db_path,
        f"SELECT user_id FROM user_groups WHERE group_id = '{group['id']}'",
    )
    assert [row[0] for row in membership_rows] == [bob["id"]]
    assert _query(db_path, "SELECT is_active FROM user_group_expirations") == [(0,)]

    second = client.post("/api/v1/expirations/sweep", headers=auth)
    assert second.json()["processed"] == 0


def test_sweep_keeps_personal_memberships(client, auth, fake_runner):
    user = client.post(
        "/api/v1/users", json={"username": "carol", "password": "secret123"}, headers=auth
    ).json()

    async def scenario():
        from app.core.database import SessionLocal
        from app.db.models import Group, UserGroup, UserGroupExpiration
        from app.modules.groups.services import sweep_expired_memberships

        async with SessionLocal() as session:
            personal = await session.scalar(
                select(Group).where(
                    Group.name == "carol", Group.is_personal.is_(True)
                )
            )
            session.add(
                UserGroupExpiration(
                    user_id=user["id"],
                    group_id=personal.id,
                    expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                    is_active=True,
                )
            )
            await session.commit()

        async with SessionLocal() as session:
            processed = await sweep_expired_memberships(session)

        async with SessionLocal() as session:
            personal = await session.scalar(
                select(Group).where(
                    Group.name == "carol", Group.is_personal.is_(True)
                )
            )
            still = await session.scalar(
                select(UserGroup).where(
                    UserGroup.user_id == user["id"],
                    UserGroup.group_id == personal.id,
                )
            )
            expiration = await session.scalar(select(UserGroupExpiration))
            return processed, still is not None, expiration.is_active

    processed, still_member, expiration_active = asyncio.run(scenario())
    assert processed == 1
    assert still_member is True
    assert expiration_active is False


def test_mount_script_access_and_scripts(client, auth, fake_runner):
    alice, bob, group, _ = _make_team(client, auth)
    client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"user_id": bob["id"], "access_level": "rw"},
        headers=auth,
    )
    client.post(
        f"/api/v1/groups/{group['id']}/members",
        json={"user_id": alice["id"], "access_level": "ro"},
        headers=auth,
    )

    host = os.environ.get("NAS_HOST", "nas")
    port = int(os.environ.get("NAS_PORT", "1445"))

    rw = client.get("/api/v1/users/bob/mount-script", headers=auth)
    assert rw.status_code == 200, rw.text
    data = rw.json()
    assert data["username"] == "bob"
    assert data["host"] == host
    assert data["port"] == port
    assert data["shares"] == [
        {"name": "photos", "path": rf"\\{host}\photos", "access": "RW"}
    ]
    mount_path = f"\\\\{host}\\photos" if port == 445 else "\\\\127.0.0.1\\photos"
    assert f"net use * {mount_path} /user:bob" in data["windows_script"]
    linux = data["linux_script"]
    assert 'if [ -n "${MOUNT_ROOT:-}" ]; then' in linux
    assert 'read -r -p "Mount root path (e.g. /mnt): " MOUNT_ROOT' in linux
    assert 'sudo mkdir -p "${MOUNT_ROOT}"' in linux
    assert 'TARGET_DIR="${MOUNT_ROOT}/photos"' in linux
    assert (
        f'sudo mount -t cifs //{host}/photos "${{TARGET_DIR}}" '
        f"-o username=bob,password=${{PASWD}},port={port}"
        ",uid=$(id -u),gid=$(id -g),dir_mode=0755,file_mode=0644"
        in linux
    )
    assert f'echo "Mounted //{host}/photos at ${{TARGET_DIR}}"' in linux

    ro = client.get("/api/v1/users/alice/mount-script", headers=auth)
    assert ro.status_code == 200, ro.text
    assert ro.json()["shares"] == [
        {"name": "photos", "path": rf"\\{host}\photos", "access": "RO"}
    ]

    missing = client.get("/api/v1/users/ghost/mount-script", headers=auth)
    assert missing.status_code == 404, missing.text