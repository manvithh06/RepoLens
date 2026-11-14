from pathlib import Path

from app.schemas.analysis import Finding
from app.schemas.repository import RepositoryInfo, RepositoryScan
from app.services.intelligence.entry_points import find_entry_points
from app.services.intelligence.graph import build_import_graph
from app.services.intelligence.imports import collect_imports
from app.services.intelligence.improvements import (
    Context,
    find_improvements,
    is_env_file,
    mask_secret,
)
from app.services.intelligence.manifests import parse_manifests
from tests.fakerepo import make_reader

# Built at runtime so secret scanners do not flag this test file.
FAKE_AWS = "AKIA" + "Q7" * 8
FAKE_GITHUB = "ghp_" + "a1B2" * 9
LONG_README = "# Demo\n\n" + "This project does useful things. " * 20

INFO = RepositoryInfo(
    owner="o", name="r", full_name="o/r", html_url="https://github.com/o/r",
    default_branch="main", size_kb=1,
)  # fmt: skip


def _findings(
    tmp_path: Path, files: dict[str, str], skipped: dict[str, int] | None = None
) -> dict[str, Finding]:
    reader = make_reader(tmp_path / "repo", files)
    manifests = parse_manifests(reader)
    scan = RepositoryScan(
        repository=INFO, file_count=len(files), total_bytes=0, truncated=False,
        skipped=skipped or {}, extensions={}, sample_paths=[],
    )  # fmt: skip
    ctx = Context(
        reader=reader,
        scan=scan,
        manifests=manifests,
        graph=build_import_graph(reader, collect_imports(reader)),
        entry_points=find_entry_points(reader, manifests),
    )
    return {f.id: f for f in find_improvements(ctx)}


HEALTHY = {
    "README.md": LONG_README,
    "LICENSE": "MIT",
    ".gitignore": ".env\n",
    ".github/workflows/ci.yml": "on: push\n",
    "pyproject.toml": "[project]\nname='x'\ndependencies=['httpx>=0.27']\n"
    "[tool.ruff]\n[tool.mypy]\n",
    "app/a.py": "def f():\n    return 1\n",
    "app/b.py": "import app.a\n",
    "app/c.py": "x = 1\n",
    "tests/test_a.py": "def test_a():\n    assert True\n",
}


def test_a_healthy_repository_has_no_findings(tmp_path: Path) -> None:
    assert _findings(tmp_path, HEALTHY) == {}


def test_missing_basics(tmp_path: Path) -> None:
    found = _findings(
        tmp_path, {"a.py": "x = 1\n", "b.py": "y = 2\n", "c.py": "z = 3\n"}
    )

    for key in (
        "missing-readme",
        "missing-license",
        "no-tests",
        "no-ci",
        "no-gitignore",
    ):
        assert found[key].status == "Confirmed"
        assert found[key].evidence == []
    assert found["missing-readme"].severity == "high"
    assert found["no-python-linter"].severity == "low"
    assert found["no-python-typecheck"].category == "Tooling"


def test_thin_readme(tmp_path: Path) -> None:
    found = _findings(tmp_path, {**HEALTHY, "README.md": "# hi\n"})
    assert found["thin-readme"].evidence[0].path == "README.md"


def test_committed_env_files(tmp_path: Path) -> None:
    files = {**HEALTHY, ".env": "DB_PASSWORD=hunter22hunter\n", ".env.example": "X=\n"}
    found = _findings(tmp_path, files)

    assert [e.path for e in found["committed-env"].evidence] == [".env"]
    assert found["committed-env"].severity == "high"
    assert "hunter" not in found["committed-env"].model_dump_json()
    assert is_env_file("config/.env.production")
    assert not is_env_file(".env.sample")


def test_secrets_are_found_and_masked(tmp_path: Path) -> None:
    files = {
        **HEALTHY,
        "app/settings.py": f'AWS = "{FAKE_AWS}"\nTOKEN = "{FAKE_GITHUB}"\n',
        "app/db.py": 'password = "s3cr3tPassw0rd!"\nAPI_KEY = "your-api-key-here"\n',
        "docs/notes.md": "key: AKIAIOSFODNN7EXAMPLE\n",
    }
    found = _findings(tmp_path, files)

    secrets = found["hardcoded-secrets"]
    assert [(e.path, e.line) for e in secrets.evidence] == [
        ("app/settings.py", 1),
        ("app/settings.py", 2),
    ]
    dumped = secrets.model_dump_json()
    assert FAKE_AWS not in dumped and FAKE_GITHUB not in dumped
    assert mask_secret(FAKE_AWS) in dumped
    generic = found["generic-secrets"]
    assert generic.status == "Potential"
    assert [(e.path, e.line) for e in generic.evidence] == [("app/db.py", 1)]
    assert "s3cr3t" not in generic.model_dump_json()


def test_mask_secret() -> None:
    assert mask_secret("abcdefghijklmnop") == "abcd********"
    assert mask_secret("abcdef") == "abcd****"


def test_unpinned_dependencies(tmp_path: Path) -> None:
    files = {
        **HEALTHY,
        "requirements.txt": "flask\nrequests==2.0\n",
        "requirements-dev.txt": "pytest\n",
        "web/package.json": '{"dependencies": {"left-pad": "*", "react": "^19"}}',
    }
    found = _findings(tmp_path, files)

    evidence = [(e.path, e.line) for e in found["unpinned-dependencies"].evidence]
    assert evidence == [("requirements.txt", 1), ("web/package.json", 1)]


def test_broken_manifest(tmp_path: Path) -> None:
    found = _findings(tmp_path, {**HEALTHY, "web/package.json": "{nope"})
    assert found["broken-manifest"].evidence[0].path == "web/package.json"


def test_size_and_structure(tmp_path: Path) -> None:
    long_body = "\n".join(f"    x{i} = {i}" for i in range(90))
    nested = (
        "def deep(a):\n"
        "    if a:\n        for i in a:\n            while i:\n"
        "                with open(i) as f:\n                    try:\n"
        "                        if f:\n                            pass\n"
        "                    except OSError:\n                        pass\n"
    )
    files = {
        **HEALTHY,
        "app/big.py": "\n".join(f"v{i} = {i}" for i in range(1100)) + "\n",
        "app/long.py": f"def long_one():\n{long_body}\n",
        "app/nested.py": nested,
        "app/broken.py": "def (:\n",
        "app/todo.py": "# TODO: tidy\nx = 1  # FIXME later\n",
    }
    found = _findings(tmp_path, files, skipped={"too_large": 2})

    assert found["large-files"].evidence[0].path == "app/big.py"
    assert found["oversized-files"].evidence == []
    assert found["long-functions"].evidence[0].path == "app/long.py"
    assert found["long-functions"].evidence_total == 1
    assert "long_one() 91 lines" in found["long-functions"].detail
    assert found["deep-nesting"].evidence[0].path == "app/nested.py"
    assert found["deep-nesting"].evidence[0].line == 7
    assert found["python-syntax-errors"].evidence[0].path == "app/broken.py"
    todo = found["todo-comments"]
    assert [(e.path, e.line) for e in todo.evidence] == [
        ("app/todo.py", 1),
        ("app/todo.py", 2),
    ]


def test_import_cycles(tmp_path: Path) -> None:
    files = {**HEALTHY, "app/x.py": "import app.y\n", "app/y.py": "import app.x\n"}
    found = _findings(tmp_path, files)
    assert "app/x.py -> app/y.py -> app/x.py" in found["import-cycles"].detail


def test_js_tooling_and_docker(tmp_path: Path) -> None:
    files = {
        **HEALTHY,
        "web/package.json": '{"dependencies": {"react": "19"}}',
        "web/src/a.ts": "",
        "web/src/b.ts": "",
        "web/src/c.tsx": "",
        "Dockerfile": "FROM python\n",
        "web/Dockerfile": "FROM node\n",
        "web/.dockerignore": "node_modules\n",
    }
    found = _findings(tmp_path, files)

    assert found["no-js-linter"].severity == "low"
    assert found["no-tsconfig"].severity == "medium"
    assert [e.path for e in found["no-dockerignore"].evidence] == ["Dockerfile"]


def test_ranking_puts_severity_first(tmp_path: Path) -> None:
    files = {"a.py": "x = 1\n", "b.py": "", "c.py": "", ".env": "X=1\n"}
    reader = make_reader(tmp_path / "repo", files)
    manifests = parse_manifests(reader)
    scan = RepositoryScan(
        repository=INFO, file_count=4, total_bytes=0, truncated=False,
        skipped={}, extensions={}, sample_paths=[],
    )  # fmt: skip
    ctx = Context(
        reader=reader,
        scan=scan,
        manifests=manifests,
        graph=build_import_graph(reader, collect_imports(reader)),
        entry_points=[],
    )
    ranked = find_improvements(ctx)
    severities = [f.severity for f in ranked]
    assert severities == sorted(severities, key=["high", "medium", "low"].index)
    assert ranked[0].id == "committed-env"
