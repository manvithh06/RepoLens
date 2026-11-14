import asyncio

import httpx
import pytest

from app.core.limits import MAX_REPO_SIZE_KB
from app.services.acquisition.exceptions import (
    GitHubRateLimited,
    GitHubUnavailable,
    RepositoryNotFound,
    RepositoryTooLarge,
)
from app.services.acquisition.github_client import fetch_repo_info
from app.services.acquisition.url_validator import RepoRef

REF = RepoRef(owner="octocat", name="hello-world")


def _payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "hello-world",
        "owner": {"login": "octocat"},
        "full_name": "octocat/hello-world",
        "html_url": "https://github.com/octocat/hello-world",
        "description": "A demo repository",
        "default_branch": "main",
        "language": "Python",
        "size": 120,
        "private": False,
    }
    data.update(overrides)
    return data


def _transport(
    status: int,
    body: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status, json=body if body is not None else {}, headers=headers
        )

    return httpx.MockTransport(handler)


def test_returns_repository_info_and_calls_the_expected_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=_payload())

    info = asyncio.run(fetch_repo_info(REF, transport=httpx.MockTransport(handler)))

    assert seen == ["https://api.github.com/repos/octocat/hello-world"]
    assert info.full_name == "octocat/hello-world"
    assert info.default_branch == "main"
    assert info.primary_language == "Python"
    assert info.size_kb == 120


@pytest.mark.parametrize(
    ("status", "headers", "expected"),
    [
        (404, {}, RepositoryNotFound),
        (451, {}, RepositoryNotFound),
        (301, {}, RepositoryNotFound),
        (403, {"x-ratelimit-remaining": "0"}, GitHubRateLimited),
        (429, {}, GitHubRateLimited),
        (500, {}, GitHubUnavailable),
        (502, {}, GitHubUnavailable),
    ],
)
def test_error_statuses_map_to_app_errors(
    status: int, headers: dict[str, str], expected: type[Exception]
) -> None:
    with pytest.raises(expected):
        asyncio.run(fetch_repo_info(REF, transport=_transport(status, headers=headers)))


def test_private_repository_is_rejected() -> None:
    with pytest.raises(RepositoryNotFound):
        asyncio.run(
            fetch_repo_info(REF, transport=_transport(200, _payload(private=True)))
        )


def test_oversized_repository_is_rejected() -> None:
    body = _payload(size=MAX_REPO_SIZE_KB + 1)
    with pytest.raises(RepositoryTooLarge):
        asyncio.run(fetch_repo_info(REF, transport=_transport(200, body)))


def test_unreadable_response_is_reported_as_unavailable() -> None:
    with pytest.raises(GitHubUnavailable):
        asyncio.run(
            fetch_repo_info(REF, transport=_transport(200, {"unexpected": True}))
        )


def test_timeout_becomes_github_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    with pytest.raises(GitHubUnavailable):
        asyncio.run(fetch_repo_info(REF, transport=httpx.MockTransport(handler)))


def test_token_is_sent_only_when_provided() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_payload())

    transport = httpx.MockTransport(handler)
    asyncio.run(fetch_repo_info(REF, "secret", transport=transport))
    assert seen["auth"] == "Bearer secret"

    asyncio.run(fetch_repo_info(REF, transport=transport))
    assert seen["auth"] is None
