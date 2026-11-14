import asyncio
import os
import subprocess
from pathlib import Path

import pytest

from app.core.limits import MAX_CONCURRENT_CLONES
from app.services.acquisition.exceptions import CloneFailed, CloneTimeout, ServerBusy
from app.services.acquisition.git_clone import _clone_slots, shallow_clone


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def source_repo(tmp_path: Path) -> Path:
    """A tiny local repository, so these tests never touch the internet."""
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    (repo / "README.md").write_text("hello\n")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print('hi')\n")

    if os.name != "nt":
        outside = tmp_path / "outside-secret.txt"
        outside.write_text("TOP SECRET")
        (repo / "link.txt").symlink_to(outside)

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")
    return repo


def _clone(source: Path, destination: Path, timeout: float = 120.0) -> None:
    asyncio.run(
        shallow_clone(
            source.as_uri(),
            "main",
            destination,
            allowed_protocols="file",
            timeout=timeout,
        )
    )


def test_clone_copies_files_and_removes_git_folder(
    source_repo: Path, tmp_path: Path
) -> None:
    destination = tmp_path / "dest"

    _clone(source_repo, destination)

    assert (destination / "README.md").read_text() == "hello\n"
    assert (destination / "src" / "app.py").exists()
    assert not (destination / ".git").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlinks need special rights on Windows")
def test_symlinks_are_not_materialized(source_repo: Path, tmp_path: Path) -> None:
    destination = tmp_path / "dest"

    _clone(source_repo, destination)

    link = destination / "link.txt"
    assert link.is_file()
    assert not link.is_symlink()
    assert "TOP SECRET" not in link.read_text()


def test_disallowed_protocol_is_refused(source_repo: Path, tmp_path: Path) -> None:
    with pytest.raises(CloneFailed):
        asyncio.run(shallow_clone(source_repo.as_uri(), "main", tmp_path / "dest"))


def test_unknown_branch_fails_cleanly(source_repo: Path, tmp_path: Path) -> None:
    with pytest.raises(CloneFailed):
        asyncio.run(
            shallow_clone(
                source_repo.as_uri(),
                "no-such-branch",
                tmp_path / "dest",
                allowed_protocols="file",
            )
        )


@pytest.mark.parametrize(
    "branch",
    ["", "--upload-pack=evil", "-x", "a..b", "bad name", "semi;colon", "x" * 300],
)
def test_unsafe_branch_names_are_rejected_before_running_git(
    branch: str, tmp_path: Path
) -> None:
    with pytest.raises(CloneFailed):
        asyncio.run(
            shallow_clone("https://github.com/o/r.git", branch, tmp_path / "dest")
        )


def test_slow_clone_times_out(source_repo: Path, tmp_path: Path) -> None:
    with pytest.raises(CloneTimeout):
        _clone(source_repo, tmp_path / "dest", timeout=0.001)


def test_rejects_new_clones_when_all_slots_are_busy(tmp_path: Path) -> None:
    async def scenario() -> None:
        for _ in range(MAX_CONCURRENT_CLONES):
            await _clone_slots.acquire()
        try:
            await shallow_clone("https://github.com/o/r.git", "main", tmp_path / "dest")
        finally:
            for _ in range(MAX_CONCURRENT_CLONES):
                _clone_slots.release()

    with pytest.raises(ServerBusy):
        asyncio.run(scenario())
