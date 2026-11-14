import asyncio
import logging
import os
import re
from pathlib import Path

from app.core.limits import CLONE_TIMEOUT_SECONDS, MAX_CONCURRENT_CLONES
from app.services.acquisition.exceptions import CloneFailed, CloneTimeout, ServerBusy
from app.services.acquisition.workspace import remove_tree

logger = logging.getLogger(__name__)

_SAFE_BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,254}")

# Only these variables are passed to git. Everything else (API keys, tokens) stays out.
_ENV_ALLOWLIST = (
    "PATH",
    "SYSTEMROOT",
    "TMPDIR",
    "TEMP",
    "TMP",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "CURL_CA_BUNDLE",
)

_clone_slots = asyncio.Semaphore(MAX_CONCURRENT_CLONES)


def _is_safe_branch(branch: str) -> bool:
    return _SAFE_BRANCH.fullmatch(branch) is not None and ".." not in branch


def _build_env(allowed_protocols: str) -> dict[str, str]:
    env = {name: os.environ[name] for name in _ENV_ALLOWLIST if name in os.environ}
    env.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ALLOW_PROTOCOL": allowed_protocols,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_LFS_SKIP_SMUDGE": "1",
        }
    )
    return env


async def _run_git(args: list[str], allowed_protocols: str, timeout: float) -> None:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        env=_build_env(allowed_protocols),
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        raise CloneTimeout("Downloading the repository took too long.") from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()

    if process.returncode != 0:
        logger.warning(
            "git clone failed (exit %s): %s",
            process.returncode,
            stderr.decode(errors="replace")[:500],
        )
        raise CloneFailed("Could not download the repository. Try again shortly.")


async def shallow_clone(
    url: str,
    branch: str,
    destination: Path,
    *,
    allowed_protocols: str = "https",
    timeout: float = CLONE_TIMEOUT_SECONDS,
) -> None:
    """Download only the latest snapshot of one branch, then drop the .git folder."""
    if not _is_safe_branch(branch):
        raise CloneFailed("The repository's default branch name is not supported.")
    if _clone_slots.locked():
        raise ServerBusy("RepoLens is busy with other repositories. Try again in a minute.")

    args = [
        "git",
        "-c",
        "core.symlinks=false",
        "clone",
        "--quiet",
        "--depth",
        "1",
        "--single-branch",
        "--no-tags",
        "--branch",
        branch,
        "--",
        url,
        str(destination),
    ]
    async with _clone_slots:
        await _run_git(args, allowed_protocols, timeout)

    remove_tree(destination / ".git")