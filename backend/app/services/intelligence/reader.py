"""The only way analysis code reads repository files.

Every read is checked: the path must be one of the files the filter kept, and its real
location must still be inside the workspace root. Contents are decoded as UTF-8 with
replacement characters, so bad bytes never raise.
"""

import os
import stat
from collections.abc import Iterable
from pathlib import Path

from app.core.limits import MAX_FILE_SIZE_BYTES, MAX_READER_CACHE_BYTES
from app.services.acquisition.file_filter import KeptFile


class RepoReader:
    def __init__(
        self,
        root: Path,
        kept_files: Iterable[KeptFile],
        *,
        max_cache_bytes: int = MAX_READER_CACHE_BYTES,
    ) -> None:
        self._real_root = os.path.realpath(root)
        self._sizes = {kept.path: kept.size for kept in kept_files}
        self._cache: dict[str, str | None] = {}
        self._cached_bytes = 0
        self._max_cache_bytes = max_cache_bytes

    @property
    def paths(self) -> list[str]:
        return list(self._sizes)

    def has(self, path: str) -> bool:
        return path in self._sizes

    def size(self, path: str) -> int:
        return self._sizes.get(path, 0)

    def _safe_location(self, path: str) -> str | None:
        if not self.has(path) or path.startswith("/") or "\\" in path:
            return None
        if any(part in ("", ".", "..") for part in path.split("/")):
            return None
        location = os.path.join(self._real_root, *path.split("/"))
        # realpath must not move the file: no symlinked folders on the way.
        if os.path.realpath(location) != location:
            return None
        try:
            if os.path.commonpath([self._real_root, location]) != self._real_root:
                return None
        except ValueError:
            return None
        return location

    def _read(self, path: str) -> str | None:
        location = self._safe_location(path)
        if location is None:
            return None
        try:
            info = os.lstat(location)
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_SIZE_BYTES:
                return None
            with open(location, "rb") as handle:
                data = handle.read(MAX_FILE_SIZE_BYTES + 1)
        except OSError:
            return None
        if len(data) > MAX_FILE_SIZE_BYTES:
            return None
        return data.decode("utf-8", errors="replace")

    def text(self, path: str) -> str | None:
        """Return the file's text, or None if it is not a kept file or cannot be read."""
        if path in self._cache:
            return self._cache[path]
        content = self._read(path)
        size = len(content) if content else 0
        if self._cached_bytes + size <= self._max_cache_bytes:
            self._cache[path] = content
            self._cached_bytes += size
        return content
