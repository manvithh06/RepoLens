import asyncio
import os
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from app.schemas.repository import RepositoryInfo, RepositoryScan
from app.services.acquisition.file_filter import FilterResult, filter_repository
from app.services.acquisition.git_clone import shallow_clone
from app.services.acquisition.url_validator import RepoRef
from app.services.acquisition.workspace import temporary_workspace

SAMPLE_PATH_COUNT = 30
TOP_EXTENSION_COUNT = 10


@dataclass(frozen=True)
class AcquiredRepository:
    info: RepositoryInfo
    root: Path
    filtered: FilterResult


@asynccontextmanager
async def acquired_repository(
    ref: RepoRef,
    info: RepositoryInfo,
    workspace_base: Path,
) -> AsyncIterator[AcquiredRepository]:
    """Clone and filter a repository. The files are deleted when the `async with` block ends."""
    with temporary_workspace(workspace_base) as workspace:
        root = workspace / "repo"
        await shallow_clone(ref.clone_url, info.default_branch, root)
        filtered = await asyncio.to_thread(filter_repository, root)
        yield AcquiredRepository(info=info, root=root, filtered=filtered)


def summarize_scan(repo: AcquiredRepository) -> RepositoryScan:
    files = repo.filtered.files
    extensions = Counter(
        os.path.splitext(kept.path)[1].lower() or "(none)" for kept in files
    )
    return RepositoryScan(
        repository=repo.info,
        file_count=len(files),
        total_bytes=sum(kept.size for kept in files),
        truncated=repo.filtered.truncated,
        skipped=repo.filtered.skipped,
        extensions=dict(extensions.most_common(TOP_EXTENSION_COUNT)),
        sample_paths=[kept.path for kept in files[:SAMPLE_PATH_COUNT]],
    )
