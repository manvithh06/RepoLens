import os
import time
from pathlib import Path

import pytest

from app.services.acquisition.workspace import (
    WORKSPACE_PREFIX,
    cleanup_stale_workspaces,
    remove_tree,
    temporary_workspace,
)


def test_workspace_is_created_and_removed(tmp_path: Path) -> None:
    with temporary_workspace(tmp_path) as workspace:
        assert workspace.is_dir()
        assert workspace.name.startswith(WORKSPACE_PREFIX)
        (workspace / "file.txt").write_text("data")

    assert not workspace.exists()


def test_workspace_is_removed_even_when_the_work_fails(tmp_path: Path) -> None:
    created: list[Path] = []

    with pytest.raises(RuntimeError), temporary_workspace(tmp_path) as workspace:
        created.append(workspace)
        raise RuntimeError("boom")

    assert not created[0].exists()


def test_two_workspaces_never_share_a_folder(tmp_path: Path) -> None:
    with (
        temporary_workspace(tmp_path) as first,
        temporary_workspace(tmp_path) as second,
    ):
        assert first != second


def test_remove_tree_deletes_read_only_files(tmp_path: Path) -> None:
    target = tmp_path / "tree"
    (target / "sub").mkdir(parents=True)
    locked = target / "sub" / "locked.pack"
    locked.write_text("data")
    locked.chmod(0o444)

    remove_tree(target)

    assert not target.exists()


def test_cleanup_removes_only_old_repolens_workspaces(tmp_path: Path) -> None:
    old = tmp_path / f"{WORKSPACE_PREFIX}old"
    fresh = tmp_path / f"{WORKSPACE_PREFIX}fresh"
    unrelated = tmp_path / "keep-me"
    for folder in (old, fresh, unrelated):
        folder.mkdir()

    two_hours_ago = time.time() - 7200
    os.utime(old, (two_hours_ago, two_hours_ago))
    os.utime(unrelated, (two_hours_ago, two_hours_ago))

    removed = cleanup_stale_workspaces(tmp_path, max_age_seconds=3600)

    assert removed == 1
    assert not old.exists()
    assert fresh.exists()
    assert unrelated.exists()


def test_cleanup_handles_a_missing_base_folder(tmp_path: Path) -> None:
    assert cleanup_stale_workspaces(tmp_path / "does-not-exist", 3600) == 0
