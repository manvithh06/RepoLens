"""Parse dependency manifests. A broken manifest is reported, never raised."""

import json
import logging
import re
import tomllib
from collections.abc import Callable
from posixpath import basename, dirname
from typing import Any

from app.core.limits import MAX_MANIFEST_DEPTH
from app.schemas.analysis import Dependency, Manifest
from app.services.intelligence.reader import RepoReader

logger = logging.getLogger(__name__)

PARSE_ERROR = "Could not parse"

_DEV_NAME = re.compile(r"dev|test|lint|check|type|doc", re.IGNORECASE)
_PEP508_NAME = re.compile(r"\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")


def normalize_python_name(name: str) -> str:
    """PEP 503 normalisation: 'Django_REST.framework' -> 'django-rest-framework'."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _line_of(text: str, needle: str, start: int = 1) -> int | None:
    """First 1-based line at or after `start` that contains `needle`."""
    for number, line in enumerate(text.splitlines(), start=1):
        if number >= start and needle in line:
            return number
    return None


def _pep508(requirement: str) -> tuple[str, str] | None:
    """Split 'name[extra]>=1.0; marker' into ('name', '>=1.0')."""
    requirement = requirement.split(";", 1)[0].strip()
    match = _PEP508_NAME.match(requirement)
    if not match:
        return None
    rest = requirement[match.end() :].strip()
    if rest.startswith("["):
        rest = rest.split("]", 1)[-1].strip()
    return normalize_python_name(match.group(1)), rest.replace(" ", "")


def _python_deps(
    text: str, requirements: Any, dev: bool, seen_line: int = 1
) -> list[Dependency]:
    deps: list[Dependency] = []
    if not isinstance(requirements, list):
        return deps
    for requirement in requirements:
        if not isinstance(requirement, str):
            continue  # {include-group = "..."} and friends
        parsed = _pep508(requirement)
        if parsed:
            name, spec = parsed
            deps.append(
                Dependency(
                    name=name,
                    spec=spec,
                    dev=dev,
                    line=_line_of(text, requirement.split(";")[0].strip(), seen_line),
                )
            )
    return deps


# ---------- one parser per manifest kind ----------


def _parse_package_json(path: str, text: str) -> Manifest:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("not an object")
    deps: list[Dependency] = []
    for key, dev in (
        ("dependencies", False),
        ("devDependencies", True),
        ("peerDependencies", False),
        ("optionalDependencies", False),
    ):
        section = data.get(key)
        if not isinstance(section, dict):
            continue
        start = _line_of(text, f'"{key}"') or 1
        for name, spec in section.items():
            deps.append(
                Dependency(
                    name=str(name),
                    spec=str(spec),
                    dev=dev,
                    line=_line_of(text, f'"{name}"', start),
                )
            )
    scripts = data.get("scripts")
    return Manifest(
        path=path,
        kind="package.json",
        ecosystem="npm",
        name=data.get("name") if isinstance(data.get("name"), str) else None,
        dependencies=deps,
        scripts={str(k): str(v) for k, v in scripts.items()}
        if isinstance(scripts, dict)
        else {},
    )


def _requirements_dev(path: str) -> bool:
    return bool(_DEV_NAME.search(basename(path))) or (
        basename(dirname(path)) == "requirements" and bool(_DEV_NAME.search(path))
    )


def _parse_requirements(path: str, text: str) -> Manifest:
    dev = _requirements_dev(path)
    deps: list[Dependency] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith(("#", "-", "git+", "http://", "https://")):
            continue
        parsed = _pep508(line)
        if parsed:
            deps.append(
                Dependency(name=parsed[0], spec=parsed[1], dev=dev, line=number)
            )
    return Manifest(
        path=path, kind="requirements.txt", ecosystem="pypi", dependencies=deps
    )


def _poetry_spec(value: Any) -> str:
    if isinstance(value, str):
        return "" if value == "*" else value
    if isinstance(value, dict):
        return str(value.get("version", ""))
    return ""


def _poetry_deps(text: str, section: Any, dev: bool) -> list[Dependency]:
    if not isinstance(section, dict):
        return []
    return [
        Dependency(
            name=normalize_python_name(name),
            spec=_poetry_spec(value),
            dev=dev,
            line=_line_of(text, name),
        )
        for name, value in section.items()
        if name.lower() != "python"
    ]


def _parse_pyproject(path: str, text: str) -> Manifest:
    data = tomllib.loads(text)
    project = data.get("project") if isinstance(data.get("project"), dict) else {}
    tool = data.get("tool") if isinstance(data.get("tool"), dict) else {}
    poetry = tool.get("poetry") if isinstance(tool.get("poetry"), dict) else {}

    deps = _python_deps(text, project.get("dependencies"), dev=False)
    optional = project.get("optional-dependencies")
    if isinstance(optional, dict):
        for group, items in optional.items():
            deps += _python_deps(text, items, dev=bool(_DEV_NAME.search(group)))
    groups = data.get("dependency-groups")
    if isinstance(groups, dict):
        for items in groups.values():
            deps += _python_deps(text, items, dev=True)

    deps += _poetry_deps(text, poetry.get("dependencies"), dev=False)
    deps += _poetry_deps(text, poetry.get("dev-dependencies"), dev=True)
    poetry_groups = poetry.get("group")
    if isinstance(poetry_groups, dict):
        for group, body in poetry_groups.items():
            if isinstance(body, dict):
                deps += _poetry_deps(
                    text, body.get("dependencies"), dev=group != "main"
                )

    scripts: dict[str, str] = {}
    for source in (project.get("scripts"), poetry.get("scripts")):
        if isinstance(source, dict):
            scripts.update({str(k): str(v) for k, v in source.items()})

    name = project.get("name") or poetry.get("name")
    return Manifest(
        path=path,
        kind="pyproject.toml",
        ecosystem="pypi",
        name=name if isinstance(name, str) else None,
        dependencies=deps,
        scripts=scripts,
    )


def _parse_pipfile(path: str, text: str) -> Manifest:
    data = tomllib.loads(text)
    deps = _poetry_deps(text, data.get("packages"), dev=False)
    deps += _poetry_deps(text, data.get("dev-packages"), dev=True)
    return Manifest(path=path, kind="Pipfile", ecosystem="pypi", dependencies=deps)


def _parse_cargo(path: str, text: str) -> Manifest:
    data = tomllib.loads(text)
    deps: list[Dependency] = []
    for key, dev in (
        ("dependencies", False),
        ("dev-dependencies", True),
        ("build-dependencies", True),
    ):
        section = data.get(key)
        if not isinstance(section, dict):
            continue
        start = _line_of(text, f"[{key}]") or 1
        for name, value in section.items():
            deps.append(
                Dependency(
                    name=name,
                    spec=_poetry_spec(value),
                    dev=dev,
                    line=_line_of(text, name, start),
                )
            )
    package = data.get("package") if isinstance(data.get("package"), dict) else {}
    name = package.get("name")
    return Manifest(
        path=path,
        kind="Cargo.toml",
        ecosystem="cargo",
        name=name if isinstance(name, str) else None,
        dependencies=deps,
    )


def _parse_composer(path: str, text: str) -> Manifest:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("not an object")
    deps: list[Dependency] = []
    for key, dev in (("require", False), ("require-dev", True)):
        section = data.get(key)
        if not isinstance(section, dict):
            continue
        for name, spec in section.items():
            if name == "php" or name.startswith("ext-"):
                continue
            deps.append(
                Dependency(
                    name=name, spec=str(spec), dev=dev, line=_line_of(text, f'"{name}"')
                )
            )
    scripts = data.get("scripts")
    return Manifest(
        path=path,
        kind="composer.json",
        ecosystem="composer",
        name=data.get("name") if isinstance(data.get("name"), str) else None,
        dependencies=deps,
        scripts={k: str(v) for k, v in scripts.items()}
        if isinstance(scripts, dict)
        else {},
    )


_GO_REQUIRE = re.compile(r"^\s*(?:require\s+)?([^\s()]+)\s+(v[^\s]+)")


def _parse_go_mod(path: str, text: str) -> Manifest:
    name = None
    deps: list[Dependency] = []
    in_block = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("//", 1)[0].strip()
        if line.startswith("module "):
            name = line.split(None, 1)[1].strip()
        elif line.startswith("require ("):
            in_block = True
        elif in_block and line == ")":
            in_block = False
        elif in_block or line.startswith("require "):
            match = _GO_REQUIRE.match(line)
            if match:
                deps.append(
                    Dependency(
                        name=match.group(1),
                        spec=match.group(2),
                        dev="// indirect" in raw,
                        line=number,
                    )
                )
    return Manifest(
        path=path, kind="go.mod", ecosystem="go", name=name, dependencies=deps
    )


_GEM = re.compile(r"""^\s*gem\s+['"]([^'"]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""")
_GEM_GROUP = re.compile(r"^\s*group\s+(.+?)\s+do\b")


def _parse_gemfile(path: str, text: str) -> Manifest:
    deps: list[Dependency] = []
    group_dev: list[bool] = []
    for number, line in enumerate(text.splitlines(), start=1):
        group = _GEM_GROUP.match(line)
        if group:
            group_dev.append(bool(_DEV_NAME.search(group.group(1))))
            continue
        if re.match(r"^\s*end\b", line) and group_dev:
            group_dev.pop()
            continue
        gem = _GEM.match(line)
        if gem:
            deps.append(
                Dependency(
                    name=gem.group(1),
                    spec=gem.group(2) or "",
                    dev=any(group_dev),
                    line=number,
                )
            )
    return Manifest(path=path, kind="Gemfile", ecosystem="rubygems", dependencies=deps)


# ---------- discovery ----------

_PARSERS: dict[str, tuple[str, str, Callable[[str, str], Manifest]]] = {
    "package.json": ("package.json", "npm", _parse_package_json),
    "pyproject.toml": ("pyproject.toml", "pypi", _parse_pyproject),
    "pipfile": ("Pipfile", "pypi", _parse_pipfile),
    "cargo.toml": ("Cargo.toml", "cargo", _parse_cargo),
    "composer.json": ("composer.json", "composer", _parse_composer),
    "go.mod": ("go.mod", "go", _parse_go_mod),
    "gemfile": ("Gemfile", "rubygems", _parse_gemfile),
}
_REQUIREMENTS = ("requirements.txt", "pypi", _parse_requirements)


def _parser_for(path: str) -> tuple[str, str, Callable[[str, str], Manifest]] | None:
    name = basename(path).lower()
    if name in _PARSERS:
        return _PARSERS[name]
    if name.startswith("requirements") and name.endswith((".txt", ".in")):
        return _REQUIREMENTS
    if basename(dirname(path)).lower() == "requirements" and name.endswith(
        (".txt", ".in")
    ):
        return _REQUIREMENTS
    return None


def is_manifest(path: str) -> bool:
    return _parser_for(path) is not None


def parse_manifests(reader: RepoReader) -> list[Manifest]:
    manifests: list[Manifest] = []
    for path in sorted(reader.paths):
        if path.count("/") > MAX_MANIFEST_DEPTH:
            continue
        found = _parser_for(path)
        if found is None:
            continue
        kind, ecosystem, parse = found
        text = reader.text(path)
        try:
            if text is None:
                raise ValueError("unreadable")
            manifests.append(parse(path, text))
        except Exception as error:  # noqa: BLE001 - untrusted input, never fatal
            logger.info("Could not parse manifest %s: %s", path, type(error).__name__)
            manifests.append(
                Manifest(path=path, kind=kind, ecosystem=ecosystem, error=PARSE_ERROR)
            )
    return manifests
