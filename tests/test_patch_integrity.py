import json
from pathlib import Path

import pytest
from verify_patches import verify


def test_archived_patches():
    verify()


def test_corrupt_patch_is_rejected(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "patches").mkdir()
    (tmp_path / "configs/upstreams.json").write_text(json.dumps({"repo": {"commit": "base"}}))
    (tmp_path / "patches/manifest.json").write_text(
        json.dumps({"repo": {"base_commit": "base", "patch_sha256": "wrong"}})
    )
    (tmp_path / "patches/repo.patch").write_text("corrupt")
    with pytest.raises(ValueError, match="checksum"):
        verify(Path(tmp_path))
