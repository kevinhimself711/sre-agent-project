from pathlib import Path

import pytest
from prepare_eval_workspace import ensure_managed_symlink


def test_managed_runtime_symlink_can_be_reused(tmp_path: Path):
    target = tmp_path / "cache-bin"
    target.mkdir()
    link = tmp_path / "bin"

    ensure_managed_symlink(link, target, target_is_directory=True)
    ensure_managed_symlink(link, target, target_is_directory=True)

    assert link.is_symlink()
    assert link.resolve() == target.resolve()


def test_managed_runtime_symlink_rejects_an_unexpected_target(tmp_path: Path):
    expected = tmp_path / "expected"
    unexpected = tmp_path / "unexpected"
    expected.mkdir()
    unexpected.mkdir()
    link = tmp_path / "bin"
    link.symlink_to(unexpected, target_is_directory=True)

    with pytest.raises(RuntimeError, match="outside the runtime cache"):
        ensure_managed_symlink(link, expected, target_is_directory=True)


def test_managed_runtime_path_rejects_a_real_directory(tmp_path: Path):
    target = tmp_path / "cache-bin"
    target.mkdir()
    path = tmp_path / "bin"
    path.mkdir()

    with pytest.raises(RuntimeError, match="not a symlink"):
        ensure_managed_symlink(path, target, target_is_directory=True)
