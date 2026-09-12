import asyncio

from app.core.exceptions import SambaCommandError
from app.modules.samba import registry_manager


def test_list_shares_returns_names(fake_runner):
    fake_runner.set_response("net conf listshares", 0, "photos\ndocs\n")
    assert asyncio.run(registry_manager.list_shares()) == ["photos", "docs"]


def test_show_share_parses_iniish_output(fake_runner):
    fake_runner.set_response(
        "net conf showshare photos",
        0,
        "[photos]\n"
        "\tpath = /mnt/share/photos\n"
        "\tcomment = comment=NAS Manager\n"
        "\tvalid users = alice bob\n",
    )
    params = asyncio.run(registry_manager.show_share("photos"))
    assert params == {
        "path": "/mnt/share/photos",
        "comment": "comment=NAS Manager",
        "valid users": "alice bob",
    }


def test_add_share_command_shape(fake_runner):
    asyncio.run(registry_manager.add_share("photos", "/mnt/share/photos"))
    call = fake_runner.calls[0]
    assert call["args"] == [
        "net",
        "conf",
        "addshare",
        "photos",
        "/mnt/share/photos",
        "writeable=no",
        "guest_ok=no",
    ]


def test_del_share_command_shape(fake_runner):
    asyncio.run(registry_manager.del_share("ghost"))
    assert fake_runner.calls[0]["args"] == ["net", "conf", "delshare", "ghost"]


def test_set_parm_and_get_parm(fake_runner):
    asyncio.run(registry_manager.set_parm("photos", "valid users", "alice bob"))
    assert fake_runner.calls[-1]["args"] == [
        "net",
        "conf",
        "setparm",
        "photos",
        "valid users",
        "alice bob",
    ]

    fake_runner.set_response("net conf showshare photos", 0, "[photos]\n\tbrowseable = yes\n")
    assert asyncio.run(registry_manager.get_parm("photos", "browseable")) == "yes"
    assert asyncio.run(registry_manager.get_parm("photos", "missing")) is None


def test_failed_net_conf_raises(fake_runner):
    fake_runner.set_response("net conf delshare ghost", 1, "", "no such share")
    try:
        asyncio.run(registry_manager.del_share("ghost"))
        raise AssertionError("expected SambaCommandError")
    except SambaCommandError as exc:
        assert "no such share" in str(exc)
