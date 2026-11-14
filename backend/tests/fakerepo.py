"""Build small fake repositories on disk for tests."""

from pathlib import Path

from app.services.acquisition.file_filter import filter_repository
from app.services.intelligence.reader import RepoReader


def write_repo(root: Path, files: dict[str, str | bytes]) -> Path:
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content)
    return root


def make_reader(root: Path, files: dict[str, str | bytes]) -> RepoReader:
    write_repo(root, files)
    return RepoReader(root, filter_repository(root).files)
