import json
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
    response = client.post(
        "/api/repositories/scan", json={"url": "https://evil.com/a/b"}
    )

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


def test_analyze_returns_the_full_analysis_and_cleans_up(
    client: TestClient, workspace: Path
) -> None:
    response = client.post(
        "/api/repositories/analyze",
        json={"url": "https://github.com/octocat/hello-world"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["analysis_id"]) == 32
    assert body["scan"]["file_count"] == 2
    assert body["languages"]["primary"] == "Python"
    assert body["tree"]["name"] == "hello-world"
    assert [n["id"] for n in body["graph"]["nodes"]] == ["src/app.py"]
    assert body["architecture"]["modules"][0]["id"] == "src"
    assert list(workspace.iterdir()) == []


def test_analyze_stream_reports_real_stages_then_the_result(
    client: TestClient, workspace: Path
) -> None:
    response = client.post(
        "/api/repositories/analyze/stream",
        json={"url": "https://github.com/octocat/hello-world"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    lines = [json.loads(line) for line in response.text.splitlines()]
    assert [line.get("stage") for line in lines[:3]] == [
        "checking",
        "cloning",
        "analysing",
    ]
    assert lines[3]["result"]["scan"]["file_count"] == 2
    assert list(workspace.iterdir()) == []


def test_analyze_stream_sends_errors_as_a_line(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_clone(url: str, branch: str, destination: Path) -> None:
        raise CloneFailed("Could not download the repository.")

    monkeypatch.setattr(repository_module, "shallow_clone", failing_clone)
    response = client.post(
        "/api/repositories/analyze/stream",
        json={"url": "https://github.com/octocat/hello-world"},
    )

    lines = [json.loads(line) for line in response.text.splitlines()]
    assert lines[-1] == {
        "error": {
            "code": "clone_failed",
            "message": "Could not download the repository.",
        }
    }


def test_analyze_stream_rejects_bad_urls_before_streaming(client: TestClient) -> None:
    response = client.post(
        "/api/repositories/analyze/stream", json={"url": "https://evil.com/a/b"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_repository_url"


def test_expensive_endpoints_are_rate_limited_per_ip(client: TestClient) -> None:
    url = {"url": "https://github.com/octocat/hello-world"}
    codes = [
        client.post("/api/repositories/analyze", json=url).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [200] * 10
    assert codes[10] == 429
    blocked = client.post("/api/repositories/analyze/stream", json=url)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert "Try again in" in blocked.json()["error"]["message"]
