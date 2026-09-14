from nasmanager.config import MountEntry
from nasmanager.diff import compute_diff, ShareStatus


def test_new_share():
    api = [{"name": "photos", "host": "nas", "port": 1445, "access": "RO"}]
    mounts = []
    diff = compute_diff(api, mounts, lambda t: False)
    assert len(diff) == 1
    assert diff[0].status == ShareStatus.NEW


def test_mounted_share():
    api = [{"name": "photos", "host": "nas", "port": 1445, "access": "RO"}]
    mounts = [MountEntry(share="photos", source_uri="//nas/photos", target="/mnt/nas/photos")]
    diff = compute_diff(api, mounts, lambda t: True)
    assert diff[0].status == ShareStatus.MOUNTED


def test_revoked_share():
    api = []
    mounts = [MountEntry(share="photos", source_uri="//nas/photos", target="/mnt/nas/photos")]
    diff = compute_diff(api, mounts, lambda t: True)
    assert diff[0].status == ShareStatus.REVOKED


def test_mounted_not_real():
    api = [{"name": "photos", "host": "nas", "port": 1445, "access": "RO"}]
    mounts = [MountEntry(share="photos", source_uri="//nas/photos", target="/mnt/nas/photos")]
    diff = compute_diff(api, mounts, lambda t: False)
    assert diff[0].status == ShareStatus.MOUNTED_NOT_REAL