import logging

import httpx

from app.core.limits import GITHUB_API_TIMEOUT_SECONDS, MAX_REPO_SIZE_KB
from app.schemas.repository import RepositoryInfo
from app.services.acquisition.exceptions import (
    GitHubRateLimited,
    GitHubUnavailable,
    RepositoryNotFound,
    RepositoryTooLarge,
)
from app.services.acquisition.url_validator import RepoRef

logger = logging.getLogger(__name__)


def _is_rate_limited(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return True
    return response.status_code == 403 and (
        response.headers.get("x-ratelimit-remaining") == "0"
        or "retry-after" in response.headers
    )


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status == 200:
        return
    if _is_rate_limited(response):
        raise GitHubRateLimited("GitHub's rate limit was reached. Try again later.")
    if status in (301, 302, 307, 308):
        raise RepositoryNotFound(
            "This repository has moved or been renamed. Use its current URL."
        )
    if status in (403, 404, 451):
        raise RepositoryNotFound("Repository not found, or it is not public.")
    logger.warning("Unexpected GitHub API status: %s", status)
    raise GitHubUnavailable(
        "GitHub returned an unexpected response. Try again shortly."
    )


def _parse_repo_info(response: httpx.Response) -> tuple[RepositoryInfo, bool]:
    try:
        data = response.json()
        info = RepositoryInfo(
            owner=data["owner"]["login"],
            name=data["name"],
            full_name=data["full_name"],
            html_url=data["html_url"],
            description=data.get("description"),
            default_branch=data["default_branch"],
            primary_language=data.get("language"),
            size_kb=int(data.get("size", 0)),
        )
        is_private = bool(data.get("private", False))
    except (ValueError, KeyError, TypeError) as exc:
        raise GitHubUnavailable("GitHub returned data we could not read.") from exc
    return info, is_private


async def fetch_repo_info(
    ref: RepoRef,
    token: str = "",
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> RepositoryInfo:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "RepoLens",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(
            timeout=GITHUB_API_TIMEOUT_SECONDS,
            follow_redirects=False,
            transport=transport,
        ) as client:
            response = await client.get(ref.api_url, headers=headers)
    except httpx.TimeoutException as exc:
        raise GitHubUnavailable(
            "GitHub took too long to respond. Try again shortly."
        ) from exc
    except httpx.HTTPError as exc:
        raise GitHubUnavailable("Could not reach GitHub. Try again shortly.") from exc

    _raise_for_status(response)
    info, is_private = _parse_repo_info(response)

    if is_private:
        raise RepositoryNotFound("Only public repositories are supported.")
    if info.size_kb > MAX_REPO_SIZE_KB:
        raise RepositoryTooLarge(
            f"This repository is about {info.size_kb // 1024} MB. "
            f"The limit is {MAX_REPO_SIZE_KB // 1024} MB."
        )
    return info
