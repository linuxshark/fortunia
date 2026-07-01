import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage import disk_available, require_disk, DiskUnavailable  # noqa: E402

SENTINEL = ".fortunia-backup-volume"


def test_available_when_sentinel_present(tmp_path):
    (tmp_path / SENTINEL).touch()
    assert disk_available(tmp_path, SENTINEL) is True


def test_unavailable_when_sentinel_missing(tmp_path):
    assert disk_available(tmp_path, SENTINEL) is False


def test_unavailable_when_dir_missing(tmp_path):
    assert disk_available(tmp_path / "nope", SENTINEL) is False


def test_require_disk_raises_when_missing(tmp_path):
    with pytest.raises(DiskUnavailable):
        require_disk(tmp_path, SENTINEL)


def test_require_disk_ok_when_present(tmp_path):
    (tmp_path / SENTINEL).touch()
    require_disk(tmp_path, SENTINEL)  # no raise
