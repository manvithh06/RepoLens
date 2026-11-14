"""Find the files where a program starts. Matching is textual; nothing is executed."""

import re
from collections.abc import Iterable
from posixpath import basename, dirname, normpath

from app.core.limits import MAX_ENTRY_POINTS
from app.schemas.analysis import EntryPoint, Manifest
from app.services.intelligence.paths import is_test_path, path_kind
from app.services.intelligence.reader import RepoReader

# (pattern, kind, priority); lower priority numbers are listed first.
_PYTHON_RULES = [
    (re.compile(r"^[ \t]*(\w+)\s*=\s*FastAPI\s*\(", re.MULTILINE), "FastAPI app", 0),
    (
        re.compile(r"^[ \t]*(\w+)\s*=\s*Flask\s*\(\s*__name__", re.MULTILINE),
        "Flask app",
        0,
    ),
    (re.compile(r"get_wsgi_application\s*\("), "Django WSGI", 1),
    (re.compile(r"get_asgi_application\s*\("), "Django ASGI", 1),
    (
        re.compile(r"""^if\s+__name__\s*==\s*['"]__main__['"]\s*:""", re.MULTILINE),
        "Main guard",
        3,
    ),
]
_STREAMLIT_IMPORT = re.compile(r"^[ \t]*import\s+streamlit\b", re.MULTILINE)
_STREAMLIT_CALL = re.compile(r"\bst\.(title|set_page_config|write|header|sidebar)\b")

_JS_RULES = [
    (re.compile(r"\bcreateRoot\s*\("), "React root", 0),
    (re.compile(r"\bReactDOM\.render\s*\("), "React root", 0),
    (re.compile(r"\bcreateApp\s*\("), "Vue app", 0),
    (re.compile(r"\bnew\s+Vue\s*\("), "Vue app", 0),
    (re.compile(r"\b(app|server|fastify)\.listen\s*\("), "Node server", 1),
    (re.compile(r"\bcreateServer\s*\([^)]*\)\s*\.listen\s*\("), "Node server", 1),
]
_JS_EXTENSIONS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
_GO_MAIN = re.compile(
    r"^package\s+main\b.*?^func\s+main\s*\(", re.MULTILINE | re.DOTALL
)
_NPM_ENTRY_SCRIPTS = ("start", "dev", "serve")


def _is_page(lowered: str) -> bool:
    """index.html at the root, or one folder down (a Vite or static frontend)."""
    return basename(lowered) == "index.html" and lowered.count("/") <= 1


def _line_at(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _first_line(text: str, position: int) -> str:
    line = text[text.rfind("\n", 0, position) + 1 :].split("\n", 1)[0].strip()
    return line[:120]


def _scan_file(path: str, text: str) -> list[tuple[int, EntryPoint]]:
    found: list[tuple[int, EntryPoint]] = []
    lowered = path.lower()

    def add(priority: int, kind: str, position: int) -> None:
        found.append(
            (
                priority,
                EntryPoint(
                    path=path,
                    line=_line_at(text, position),
                    kind=kind,
                    detail=_first_line(text, position),
                ),
            )
        )

    if lowered.endswith(".py"):
        if basename(lowered) == "manage.py" and "execute_from_command_line" in text:
            position = text.find("execute_from_command_line")
            add(1, "Django manage.py", position)
        for pattern, kind, priority in _PYTHON_RULES:
            match = pattern.search(text)
            if match:
                add(priority, kind, match.start())
        if _STREAMLIT_IMPORT.search(text):
            call = _STREAMLIT_CALL.search(text)
            if call:
                add(0, "Streamlit app", call.start())
    elif lowered.endswith(_JS_EXTENSIONS):
        for pattern, kind, priority in _JS_RULES:
            match = pattern.search(text)
            if match:
                add(priority, kind, match.start())
                break
    elif lowered.endswith(".go"):
        match = _GO_MAIN.search(text)
        if match:
            add(1, "Go main package", match.start())
    elif lowered == "src/main.rs" or lowered.endswith("/src/main.rs"):
        position = text.find("fn main")
        if position != -1:
            add(1, "Rust binary", position)
    elif _is_page(lowered):
        add(2, "Web page", 0)
    return found


def _line_of(text: str, needle: str) -> int | None:
    for number, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return number
    return None


def _module_to_file(module: str, paths: set[str]) -> str | None:
    """Turn 'pkg.cli' into a kept file such as src/pkg/cli.py."""
    tail = module.replace(".", "/")
    for suffix in (f"{tail}.py", f"{tail}/__init__.py", f"{tail}/__main__.py"):
        for path in sorted(paths, key=lambda p: (p.count("/"), p)):
            if path == suffix or path.endswith(f"/{suffix}"):
                return path
    return None


def _manifest_entries(
    manifests: Iterable[Manifest], reader: RepoReader
) -> list[tuple[int, EntryPoint]]:
    found: list[tuple[int, EntryPoint]] = []
    paths = set(reader.paths)
    for manifest in manifests:
        if manifest.error:
            continue
        text = reader.text(manifest.path) or ""

        if manifest.kind == "package.json":
            for script in _NPM_ENTRY_SCRIPTS:
                command = manifest.scripts.get(script)
                if command:
                    found.append(
                        (
                            2,
                            EntryPoint(
                                path=manifest.path,
                                line=_line_of(text, f'"{script}"'),
                                kind="npm script",
                                detail=f"npm run {script}: {command}"[:120],
                            ),
                        )
                    )
            main = _package_main(text)
            if main:
                folder = dirname(manifest.path)
                target = normpath(f"{folder}/{main}" if folder else main)
                if target in paths:
                    found.append(
                        (
                            2,
                            EntryPoint(
                                path=target,
                                kind="package.json main",
                                detail=f"main: {main}"[:120],
                            ),
                        )
                    )
        elif manifest.kind == "pyproject.toml":
            for name, target in manifest.scripts.items():
                module = target.split(":", 1)[0].strip()
                resolved = _module_to_file(module, paths)
                found.append(
                    (
                        2,
                        EntryPoint(
                            path=resolved or manifest.path,
                            line=None if resolved else _line_of(text, name),
                            kind="Console script",
                            detail=f"{name} = {target}"[:120],
                        ),
                    )
                )
    return found


_PACKAGE_MAIN = re.compile(r'^[ \t]*"main"\s*:\s*"([^"]+)"', re.MULTILINE)


def _package_main(text: str) -> str | None:
    match = _PACKAGE_MAIN.search(text)
    return match.group(1) if match else None


def find_entry_points(
    reader: RepoReader, manifests: Iterable[Manifest]
) -> list[EntryPoint]:
    found: list[tuple[int, EntryPoint]] = []
    for path in reader.paths:
        if is_test_path(path):
            continue
        lowered = path.lower()
        if not lowered.endswith(
            (".py", ".go", ".rs", *_JS_EXTENSIONS)
        ) and not _is_page(lowered):
            continue
        text = reader.text(path)
        if text:
            found.extend(_scan_file(path, text))
    found.extend(
        item
        for item in _manifest_entries(manifests, reader)
        if not is_test_path(item[1].path)
    )

    unique: dict[tuple[str, str], tuple[int, EntryPoint]] = {}
    for priority, entry in found:
        unique.setdefault((entry.path, entry.kind), (priority, entry))
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            path_kind(item[1].path) == "example",
            item[0],
            item[1].path.count("/"),
            item[1].path,
        ),
    )
    return [entry for _, entry in ordered[:MAX_ENTRY_POINTS]]
