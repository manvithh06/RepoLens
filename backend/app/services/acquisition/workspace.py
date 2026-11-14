import logging
import os
import shutil
import stat
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_PREFIX = "repolens-"


def _force_remove(func: Callable[[str], object], path: str, exc: BaseException) -> None:
    """Retry a failed delete after making the path writable (git marks some files read-only)."""
    try:
        os.chmod(path, stat.S_IRWXU)
        func(path)
    except OSError:
        logger.warning("Could not delete %s", path)


def remove_tree(path: Path) -> None:
    shutil.rmtree(path, onexc=_force_remove)


@contextmanager
def temporary_workspace(base_dir: Path) -> Iterator[Path]:
    """Create a private, randomly named folder and always delete it afterwards."""
    base_dir.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix=WORKSPACE_PREFIX, dir=base_dir))
    try:
        yield workspace
    finally:
        remove_tree(workspace)


def cleanup_stale_workspaces(base_dir: Path, max_age_seconds: float) -> int:
    """Delete leftover workspaces from crashed runs. Returns how many were removed."""
    if not base_dir.is_dir():
        return 0

    cutoff = time.time() - max_age_seconds
    removed = 0
    for entry in base_dir.iterdir():
        if (
            not entry.name.startswith(WORKSPACE_PREFIX)
            or entry.is_symlink()
            or not entry.is_dir()
        ):
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                remove_tree(entry)
                removed += 1
        except OSError:
            logger.warning("Could not inspect %s", entry)
    return removed
