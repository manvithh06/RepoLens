import asyncio
from pathlib import Path

import pytest

from app.schemas.repository import RepositoryInfo, RepositoryScan
from app.services.acquisition import repository as repository_module
from app.services.acquisition.repository import acquired_repository, summarize_scan
from app.services.acquisition.url_validator import RepoRef

REF = RepoRef(owner="octocat", name="hello-world")
INFO = RepositoryInfo(
    owner="octocat",
    name="hello-world",
    full_name="octocat/hello-world",
    html_url="https://github.com/octocat/hello-world",
    default_branch="trunk",
    size_kb=10,
)


async def _fake_clone(url: str, branch: str, destination: Path, **kwargs: object) -> None:
    (destination / "src").mkdir(parents=True)
    (destination / "src" / "app.py").write_text("print('hi')\n")
    (destination / "README.md").write_text("# demo\n")
    (destination / "node_modules").mkdir()
    (destination / "node_modules" / "dep.js").write_text("x")


def test_clones_the_validated_url_and_branch_then_filters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    async def recording_clone(url: str, branch: str, destination: Path) -> None:
        calls.append((url, branch))
        await _fake_clone(url, branch, destination)

    monkeypatch.setattr(repository_module, "shallow_clone", recording_clone)

    async def scenario() -> list[str]:
        async with acquired_repository(REF, INFO, tmp_path) as repo:
            return [kept.path for kept in repo.filtered.files]

    paths = asyncio.run(scenario())

    assert calls == [("https://github.com/octocat/hello-world.git", "trunk")]
    assert paths == ["README.md", "src/app.py"]


def test_workspace_is_deleted_when_the_body_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repository_module, "shallow_clone", _fake_clone)
    roots: list[Path] = []

    async def scenario() -> None:
        async with acquired_repository(REF, INFO, tmp_path) as repo:
            roots.append(repo.root)
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        asyncio.run(scenario())

    assert not roots[0].exists()
    assert list(tmp_path.iterdir()) == []


def test_summary_counts_files_bytes_and_extensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repository_module, "shallow_clone", _fake_clone)

    async def scenario() -> RepositoryScan:
        async with acquired_repository(REF, INFO, tmp_path) as repo:
            return summarize_scan(repo)

    scan = asyncio.run(scenario())

    assert scan.file_count == 2
    assert scan.extensions == {".md": 1, ".py": 1}
    assert scan.skipped == {"excluded_directory": 1}
    assert scan.sample_paths == ["README.md", "src/app.py"]