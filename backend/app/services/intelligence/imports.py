"""Find which repository files import which, without running any of them.

Python is parsed with `ast` (parsing never executes code). JavaScript and TypeScript are
scanned with regular expressions, which is good enough for import statements.
"""

import ast
import re
import sys
import warnings
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from posixpath import dirname, normpath, splitext

from app.services.intelligence.reader import RepoReader

PYTHON_EXTENSIONS = (".py",)
JS_EXTENSIONS = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".mts",
    ".cts",
    ".vue",
    ".svelte",
)
SCRIPT_EXTENSIONS = PYTHON_EXTENSIONS + JS_EXTENSIONS

_STDLIB = frozenset(sys.stdlib_module_names)

NODE_BUILTINS = frozenset(
    {
        "assert", "async_hooks", "buffer", "child_process", "cluster", "console",
        "constants", "crypto", "dgram", "diagnostics_channel", "dns", "domain",
        "events", "fs", "http", "http2", "https", "inspector", "module", "net", "os",
        "path", "perf_hooks", "process", "punycode", "querystring", "readline",
        "repl", "stream", "string_decoder", "sys", "timers", "tls", "trace_events",
        "tty", "url", "util", "v8", "vm", "wasi", "worker_threads", "zlib",
    }
)  # fmt: skip

_JS_PATTERNS = [
    re.compile(r"""\bfrom\s*['"]([^'"\n]+)['"]"""),
    re.compile(r"""\bimport\s*['"]([^'"\n]+)['"]"""),
    re.compile(r"""\brequire\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""),
    re.compile(r"""\bimport\s*\(\s*['"]([^'"\n]+)['"]\s*\)"""),
]
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)


def is_script(path: str) -> bool:
    return path.lower().endswith(SCRIPT_EXTENSIONS)


def is_python(path: str) -> bool:
    return path.endswith(PYTHON_EXTENSIONS)


@dataclass
class ImportResult:
    script_files: list[str]
    # importer -> {imported local file: first line of the import}
    edges: dict[str, dict[str, int]] = field(default_factory=dict)
    # (package, "python" | "npm") -> number of files importing it
    external: Counter[tuple[str, str]] = field(default_factory=Counter)
    parse_errors: int = 0
    unresolved: int = 0


# ---------- Python ----------


def _python_module_index(paths: Iterable[str]) -> dict[str, list[str]]:
    """Map every dotted suffix of every module to its files.

    backend/app/core/config.py is registered as backend.app.core.config, app.core.config,
    core.config and config, so `import app.core.config` resolves inside a monorepo.
    """
    index: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        if not is_python(path):
            continue
        parts = path[: -len(".py")].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        for start in range(len(parts)):
            index[".".join(parts[start:])].append(path)
    return index


def _shared_depth(a: str, b: str) -> int:
    depth = 0
    for left, right in zip(dirname(a).split("/"), dirname(b).split("/"), strict=False):
        if left != right:
            break
        depth += 1
    return depth


def _closest(importer: str, candidates: list[str]) -> str:
    return min(
        candidates,
        key=lambda c: (-_shared_depth(importer, c), c.count("/"), c),
    )


def _python_file(parts: list[str], paths: set[str]) -> str | None:
    if not parts:
        return None
    base = "/".join(parts)
    for candidate in (f"{base}.py", f"{base}/__init__.py"):
        if candidate in paths:
            return candidate
    return None


def _python_imports(tree: ast.AST) -> list[tuple[int, str, list[str], int]]:
    """(level, module, imported names, line) for every import in the file."""
    found: list[tuple[int, str, list[str], int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((0, alias.name, [], node.lineno))
        elif isinstance(node, ast.ImportFrom):
            names = [alias.name for alias in node.names if alias.name != "*"]
            found.append((node.level, node.module or "", names, node.lineno))
    return found


def _resolve_python(
    importer: str,
    level: int,
    module: str,
    names: list[str],
    paths: set[str],
    index: dict[str, list[str]],
) -> tuple[list[str], str | None, bool]:
    """Return (local targets, external package or None, unresolved?)."""
    if level > 0:
        base = dirname(importer).split("/") if dirname(importer) else []
        if level - 1 > len(base):
            return [], None, True
        base = base[: len(base) - (level - 1)]
        target = base + (module.split(".") if module else [])
        found = [f for n in names if (f := _python_file(target + [n], paths))]
        if not found:
            single = _python_file(target, paths)
            found = [single] if single else []
        return found, None, not found

    top = module.split(".")[0]
    if not top or top in _STDLIB or top.startswith("_"):
        return [], None, False

    found = []
    for name in names:
        candidates = index.get(f"{module}.{name}")
        if candidates:
            found.append(_closest(importer, candidates))
    if found:
        return found, None, False
    parts = module.split(".")
    for end in range(len(parts), 0, -1):
        candidates = index.get(".".join(parts[:end]))
        if candidates:
            return [_closest(importer, candidates)], None, False
    return [], top, False


# ---------- JavaScript and TypeScript ----------


def _js_specifiers(text: str) -> list[tuple[str, int]]:
    # Keep newlines when removing comments so line numbers stay right.
    text = _BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    text = _LINE_COMMENT.sub("", text)
    found: list[tuple[int, str]] = []
    for pattern in _JS_PATTERNS:
        for match in pattern.finditer(text):
            found.append((match.start(), match.group(1)))
    found.sort()
    return [(spec, text.count("\n", 0, position) + 1) for position, spec in found]


def _js_package(spec: str) -> str | None:
    if spec.startswith(("/", "#", "$")) or ":" in spec.split("/")[0]:
        return None  # absolute URLs, subpath imports, virtual modules, node: builtins
    parts = spec.split("/")
    name = "/".join(parts[:2]) if spec.startswith("@") and len(parts) > 1 else parts[0]
    if not name or name in NODE_BUILTINS:
        return None
    return name


def _nearest_package_dir(importer: str, package_dirs: set[str]) -> str:
    current = dirname(importer)
    while True:
        if current in package_dirs:
            return current
        if not current:
            return ""
        current = dirname(current)


def _js_candidates(base: str) -> list[str]:
    stem, extension = splitext(base)
    candidates = [base]
    if extension.lower() in (".js", ".jsx", ".mjs", ".cjs"):
        # TypeScript ESM style: `import "./x.js"` refers to x.ts
        candidates += [f"{stem}.ts", f"{stem}.tsx", f"{stem}.mts", f"{stem}.cts"]
    candidates += [f"{base}{ext}" for ext in JS_EXTENSIONS]
    candidates += [f"{base}/index{ext}" for ext in JS_EXTENSIONS]
    return candidates


def _resolve_js(
    importer: str, spec: str, paths: set[str], package_dirs: set[str]
) -> tuple[str | None, str | None, bool]:
    """Return (local target, external package, unresolved?)."""
    spec = spec.split("?", 1)[0]
    if spec.startswith("."):
        base = normpath(f"{dirname(importer)}/{spec}" if dirname(importer) else spec)
    elif spec.startswith(("@/", "~/")):
        root = _nearest_package_dir(importer, package_dirs)
        base = normpath(f"{root}/src/{spec[2:]}" if root else f"src/{spec[2:]}")
    else:
        return None, _js_package(spec), False

    if base.startswith(".."):
        return None, None, True
    base = "" if base == "." else base
    for candidate in _js_candidates(base):
        if candidate in paths:
            if is_script(candidate):
                return candidate, None, False
            return None, None, False  # a stylesheet, JSON file or asset: not linked
    return None, None, True


# ---------- entry point ----------


def collect_imports(reader: RepoReader) -> ImportResult:
    paths = set(reader.paths)
    scripts = sorted(p for p in paths if is_script(p))
    result = ImportResult(script_files=scripts)
    index = _python_module_index(scripts)
    package_dirs = {
        dirname(p) for p in paths if p == "package.json" or p.endswith("/package.json")
    }

    for path in scripts:
        text = reader.text(path)
        if text is None:
            continue
        targets: dict[str, int] = {}
        externals: set[tuple[str, str]] = set()

        if is_python(path):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    tree = ast.parse(text, filename=path)
            except (SyntaxError, ValueError, RecursionError, MemoryError):
                result.parse_errors += 1
                continue
            for level, module, names, line in _python_imports(tree):
                found, package, unresolved = _resolve_python(
                    path, level, module, names, paths, index
                )
                for target in found:
                    targets.setdefault(target, line)
                if package:
                    externals.add((package, "python"))
                if unresolved:
                    result.unresolved += 1
        else:
            for spec, line in _js_specifiers(text):
                target, package, unresolved = _resolve_js(
                    path, spec, paths, package_dirs
                )
                if target:
                    targets.setdefault(target, line)
                if package:
                    externals.add((package, "npm"))
                if unresolved:
                    result.unresolved += 1

        targets.pop(path, None)
        if targets:
            result.edges[path] = targets
        result.external.update(externals)

    return result
