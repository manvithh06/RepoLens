import json
from pathlib import Path

from app.services.intelligence.manifests import (
    PARSE_ERROR,
    normalize_python_name,
    parse_manifests,
)
from tests.fakerepo import make_reader


def _by_path(tmp_path: Path, files: dict[str, str]) -> dict:
    return {m.path: m for m in parse_manifests(make_reader(tmp_path / "r", files))}


def test_normalizes_python_names() -> None:
    assert normalize_python_name("Django_REST.framework") == "django-rest-framework"


def test_package_json(tmp_path: Path) -> None:
    text = json.dumps(
        {
            "name": "web",
            "scripts": {"dev": "vite"},
            "dependencies": {"react": "^19.0.0"},
            "devDependencies": {"vite": "8.0.0"},
        },
        indent=2,
    )
    manifest = _by_path(tmp_path, {"web/package.json": text})["web/package.json"]

    assert manifest.ecosystem == "npm"
    assert manifest.name == "web"
    assert manifest.scripts == {"dev": "vite"}
    deps = {d.name: d for d in manifest.dependencies}
    assert deps["react"].spec == "^19.0.0"
    assert not deps["react"].dev
    assert deps["vite"].dev
    assert text.splitlines()[deps["vite"].line - 1].strip().startswith('"vite"')


def test_requirements_files_and_folder(tmp_path: Path) -> None:
    found = _by_path(
        tmp_path,
        {
            "requirements.txt": "# web\nFastAPI==0.1\nuvicorn[standard]>=0.3 ; python_version>'3'\n-r dev.txt\n\nhttpx\n",
            "requirements-dev.txt": "pytest\n",
            "requirements/test.txt": "hypothesis\n",
            "requirements/base.txt": "pydantic\n",
        },
    )

    main = found["requirements.txt"]
    assert [(d.name, d.spec, d.line) for d in main.dependencies] == [
        ("fastapi", "==0.1", 2),
        ("uvicorn", ">=0.3", 3),
        ("httpx", "", 6),
    ]
    assert not main.dependencies[0].dev
    assert found["requirements-dev.txt"].dependencies[0].dev
    assert found["requirements/test.txt"].dependencies[0].dev
    assert not found["requirements/base.txt"].dependencies[0].dev


def test_pyproject_all_sections(tmp_path: Path) -> None:
    text = """
[project]
name = "demo"
dependencies = ["Click>=8", "rich"]

[project.optional-dependencies]
docs = ["sphinx"]
redis = ["redis>=5"]

[project.scripts]
demo = "demo.cli:main"

[dependency-groups]
dev = ["pytest", {include-group = "lint"}]
lint = ["ruff"]

[tool.poetry.dependencies]
python = "^3.11"
SQLAlchemy = {version = "^2.0"}

[tool.poetry.group.test.dependencies]
coverage = "*"
"""
    manifest = _by_path(tmp_path, {"pyproject.toml": text})["pyproject.toml"]

    deps = {d.name: d for d in manifest.dependencies}
    assert manifest.name == "demo"
    assert manifest.scripts == {"demo": "demo.cli:main"}
    assert deps["click"].spec == ">=8" and not deps["click"].dev
    assert deps["sphinx"].dev
    assert not deps["redis"].dev
    assert deps["pytest"].dev and deps["ruff"].dev
    assert deps["sqlalchemy"].spec == "^2.0"
    assert deps["coverage"].dev and deps["coverage"].spec == ""
    assert "python" not in deps


def test_other_ecosystems(tmp_path: Path) -> None:
    found = _by_path(
        tmp_path,
        {
            "Pipfile": '[packages]\nflask = "*"\n[dev-packages]\npytest = "==8"\n',
            "Cargo.toml": '[package]\nname = "cli"\n[dependencies]\nserde = "1"\ntokio = { version = "1", features = ["full"] }\n[dev-dependencies]\ninsta = "1"\n',
            "composer.json": '{"require": {"php": ">=8", "laravel/framework": "^11"}, "require-dev": {"phpunit/phpunit": "^10"}}',
            "go.mod": "module example.com/app\n\ngo 1.22\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n\tgolang.org/x/net v0.1.0 // indirect\n)\n",
            "Gemfile": "source 'https://rubygems.org'\ngem 'rails', '~> 7.1'\ngroup :development, :test do\n  gem 'rspec'\nend\ngem 'puma'\n",
        },
    )

    assert [(d.name, d.dev) for d in found["Pipfile"].dependencies] == [
        ("flask", False),
        ("pytest", True),
    ]
    cargo = {d.name: d for d in found["Cargo.toml"].dependencies}
    assert found["Cargo.toml"].name == "cli"
    assert cargo["tokio"].spec == "1" and cargo["insta"].dev
    composer = [d.name for d in found["composer.json"].dependencies]
    assert composer == ["laravel/framework", "phpunit/phpunit"]
    go = found["go.mod"]
    assert go.name == "example.com/app"
    first, indirect = go.dependencies
    assert (first.name, first.spec, first.line) == (
        "github.com/gin-gonic/gin",
        "v1.9.1",
        6,
    )
    assert indirect.dev
    gems = [(d.name, d.spec, d.dev) for d in found["Gemfile"].dependencies]
    assert gems == [
        ("rails", "~> 7.1", False),
        ("rspec", "", True),
        ("puma", "", False),
    ]


def test_broken_manifests_are_reported_not_raised(tmp_path: Path) -> None:
    found = _by_path(
        tmp_path,
        {
            "package.json": "{not json",
            "pyproject.toml": "[project\nname=",
            "sub/composer.json": "[1, 2]",
        },
    )

    assert found["package.json"].error == PARSE_ERROR
    assert found["pyproject.toml"].error == PARSE_ERROR
    assert found["sub/composer.json"].error == PARSE_ERROR
    assert found["package.json"].dependencies == []


def test_ignores_manifests_deeper_than_three_folders(tmp_path: Path) -> None:
    found = _by_path(
        tmp_path,
        {
            "a/b/c/package.json": "{}",
            "a/b/c/d/package.json": "{}",
        },
    )
    assert list(found) == ["a/b/c/package.json"]
