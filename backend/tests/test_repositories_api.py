from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.routes import repositories as repositories_route
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.repository import RepositoryInfo
from app.services.acquisition import repository as repository_module
from app.services.acquisition.exceptions import CloneFailed

INFO = RepositoryInfo(
    owner="octocat",
    name="hello-world",
    full_name="octocat/hello-world",
    html_url="https://github.com/octocat/hello-world",
    default_branch="main",
    size_kb=10,
)


async def _fake_fetch(ref: object, token: str = "") -> RepositoryInfo:
    return INFO


async def _fake_clone(url: str, branch: str, destination: Path) -> None:
    (destination / "src").mkdir(parents=True)
    (destination / "src" / "app.py").write_text("print('hi')\n")
    (destination / "README.md").write_text("# demo\n")
    (destination / "node_modules").mkdir()
    (destination / "node_modules" / "dep.js").write_text("x")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path / "workspaces"


@pytest.fixture
def client(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: Settings(workspace_dir=workspace)
    monkeypatch.setattr(repositories_route, "fetch_repo_info", _fake_fetch)
    monkeypatch.setattr(repository_module, "shallow_clone", _fake_clone)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_scan_returns_a_summary_and_leaves_no_files_behind(
    client: TestClient, workspace: Path
) -> None:
    response = client.post(
        "/api/repositories/scan", json={"url": "https://github.com/octocat/hello-world"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["repository"]["full_name"] == "octocat/hello-world"
    assert body["file_count"] == 2
    assert body["skipped"] == {"excluded_directory": 1}
    assert body["sample_paths"] == ["README.md", "src/app.py"]
    assert list(workspace.iterdir()) == []


def test_scan_rejects_a_bad_url_before_doing_any_work(
    client: TestClient, workspace: Path
) -> None:
    response = client.post("/api/repositories/scan", json={"url": "https://evil.com/a/b"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_repository_url"
    assert not workspace.exists()


def test_scan_reports_clone_failures_and_still_cleans_up(
    client: TestClient, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_clone(url: str, branch: str, destination: Path) -> None:
        raise CloneFailed("Could not download the repository. Try again shortly.")

    monkeypatch.setattr(repository_module, "shallow_clone", failing_clone)

    response = client.post(
        "/api/repositories/scan", json={"url": "https://github.com/octocat/hello-world"}
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "clone_failed"
    assert list(workspace.iterdir()) == []