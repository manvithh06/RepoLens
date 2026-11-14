import os
from pathlib import Path

from app.services.acquisition.file_filter import KeptFile
from app.services.intelligence.reader import RepoReader
from tests.fakerepo import make_reader, write_repo


def test_reads_kept_files_and_refuses_everything_else(tmp_path: Path) -> None:
    reader = make_reader(tmp_path / "repo", {"src/a.py": "x = 1\n", "README.md": "hi"})

    assert reader.has("src/a.py")
    assert reader.text("src/a.py") == "x = 1\n"
    assert reader.size("README.md") == 2
    assert reader.text("missing.py") is None
    assert not reader.has("../secret")
    assert reader.text("../secret") is None


def test_rejects_paths_that_escape_even_if_listed(tmp_path: Path) -> None:
    root = write_repo(tmp_path / "repo", {"a.py": "ok"})
    (tmp_path / "secret.txt").write_text("top secret")
    os.symlink(tmp_path, root / "link")

    forged = [
        KeptFile(path="../secret.txt", size=10),
        KeptFile(path="link/secret.txt", size=10),
        KeptFile(path="/etc/passwd", size=10),
        KeptFile(path="./a.py", size=2),
    ]
    reader = RepoReader(root, forged)

    for kept in forged:
        assert reader.text(kept.path) is None


def test_decodes_bad_bytes_with_replacement(tmp_path: Path) -> None:
    reader = make_reader(tmp_path / "repo", {"a.txt": b"caf\xe9 ok"})
    assert reader.text("a.txt") == "caf� ok"


def test_caches_reads_up_to_the_budget(tmp_path: Path) -> None:
    root = write_repo(tmp_path / "repo", {"a.py": "aaaa", "b.py": "bbbb"})
    reader = RepoReader(
        root, [KeptFile("a.py", 4), KeptFile("b.py", 4)], max_cache_bytes=5
    )

    assert reader.text("a.py") == "aaaa"
    assert reader.text("b.py") == "bbbb"
    (root / "a.py").write_text("changed")
    (root / "b.py").write_text("changed")

    assert reader.text("a.py") == "aaaa"  # cached
    assert reader.text("b.py") == "changed"  # over budget, read again
