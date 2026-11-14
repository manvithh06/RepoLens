"""Deterministic checks that turn the analysis into a ranked list of improvements.

Every finding here is "Confirmed": a rule found it in the files, and its evidence points
at real paths. Pattern matches that are only a guess (generic password assignments) are
marked "Potential". Secret values are always masked before they leave this module.
"""

import ast
import re
import warnings
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from posixpath import basename, dirname

from app.core.limits import MAX_FILE_SIZE_BYTES
from app.schemas.analysis import (
    EntryPoint,
    Evidence,
    Finding,
    FindingCategory,
    ImportGraph,
    Manifest,
    Severity,
)
from app.schemas.repository import RepositoryScan
from app.services.intelligence.imports import is_python, is_script
from app.services.intelligence.paths import is_test_path
from app.services.intelligence.reader import RepoReader

MAX_EVIDENCE = 10
THIN_README_CHARS = 400
LONG_FILE_LINES = 1000
LONG_FUNCTION_LINES = 80
DEEP_NESTING = 5
MIN_FILES_FOR_TOOLING = 3

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Context:
    reader: RepoReader
    scan: RepositoryScan
    manifests: list[Manifest]
    graph: ImportGraph
    entry_points: list[EntryPoint]

    @property
    def paths(self) -> list[str]:
        return self.reader.paths

    def root_files(self) -> dict[str, str]:
        """Lowercased name -> path, for files directly in the repository root."""
        return {p.lower(): p for p in self.paths if "/" not in p}

    def scripts(self, *, include_tests: bool = False) -> list[str]:
        return [
            p
            for p in self.paths
            if is_script(p) and (include_tests or not is_test_path(p))
        ]


def _finding(
    id: str,
    title: str,
    severity: Severity,
    category: FindingCategory,
    why: str,
    fix: str,
    evidence: Iterable[Evidence] = (),
    *,
    detail: str | None = None,
    status: str = "Confirmed",
    impact: int = 0,
) -> Finding:
    evidence = list(evidence)
    return Finding(
        id=id,
        title=title,
        severity=severity,
        category=category,
        status=status,  # type: ignore[arg-type]
        evidence=evidence[:MAX_EVIDENCE],
        evidence_total=len(evidence),
        detail=detail,
        why=why,
        fix=fix,
        impact=impact,
    )


# ---------- documentation and project hygiene ----------


def check_readme(ctx: Context) -> list[Finding]:
    readme = next(
        (path for name, path in ctx.root_files().items() if name.startswith("readme")),
        None,
    )
    if readme is None:
        return [
            _finding(
                "missing-readme",
                "No README at the repository root",
                "high",
                "Documentation",
                "The README is the first thing people see. Without it nobody knows what "
                "the project does, how to run it, or whether it is maintained.",
                "Add README.md with a one paragraph summary, setup steps, how to run "
                "and test it, and the license.",
                detail="Looked for a file named README (any extension) at the root.",
                impact=90,
            )
        ]
    text = ctx.reader.text(readme) or ""
    stripped = re.sub(r"\s+", " ", text).strip()
    if len(stripped) < THIN_README_CHARS:
        return [
            _finding(
                "thin-readme",
                "README is very short",
                "medium",
                "Documentation",
                "A README this short rarely explains how to install, run and test the "
                "project, so new contributors have to read the code to find out.",
                "Add sections for what it does, setup, running locally, running tests "
                "and configuration.",
                [Evidence(path=readme, line=1)],
                detail=f"{len(stripped)} characters of text.",
                impact=50,
            )
        ]
    return []


_LICENSE_NAMES = ("license", "licence", "copying", "unlicense")


def check_license(ctx: Context) -> list[Finding]:
    if any(name.startswith(_LICENSE_NAMES) for name in ctx.root_files()):
        return []
    return [
        _finding(
            "missing-license",
            "No LICENSE file",
            "medium",
            "Documentation",
            "Without a license, the code is all rights reserved by default. Others "
            "cannot legally use, change or share it, even if it is public.",
            "Choose a license (MIT, Apache-2.0 and GPL-3.0 are common) and add it as "
            "LICENSE at the root.",
            detail="Looked for LICENSE, LICENCE or COPYING at the root.",
            impact=60,
        )
    ]


def check_tests(ctx: Context) -> list[Finding]:
    code = ctx.scripts()
    if len(code) < MIN_FILES_FOR_TOOLING:
        return []
    if any(is_test_path(p) for p in ctx.paths):
        return []
    return [
        _finding(
            "no-tests",
            "No automated tests found",
            "high",
            "Testing",
            "Without tests, every change has to be checked by hand, and regressions "
            "reach users before anyone notices.",
            "Add a test runner (pytest for Python, Vitest or Jest for JavaScript) and "
            "start with tests for the entry points and the most imported modules.",
            detail=f"{len(code)} source files and no test files or test folders.",
            impact=85,
        )
    ]


_CI_PATTERNS = (
    re.compile(r"^\.github/workflows/[^/]+\.ya?ml$"),
    re.compile(r"^\.gitlab-ci\.ya?ml$"),
    re.compile(r"^\.circleci/config\.ya?ml$"),
    re.compile(r"^\.travis\.ya?ml$"),
    re.compile(r"^azure-pipelines\.ya?ml$"),
    re.compile(r"^jenkinsfile$"),
    re.compile(r"^bitbucket-pipelines\.ya?ml$"),
    re.compile(r"^\.buildkite/"),
)


def check_ci(ctx: Context) -> list[Finding]:
    if len(ctx.scripts()) < MIN_FILES_FOR_TOOLING:
        return []
    if any(pattern.match(p.lower()) for p in ctx.paths for pattern in _CI_PATTERNS):
        return []
    return [
        _finding(
            "no-ci",
            "No continuous integration",
            "medium",
            "CI and deployment",
            "Without CI, tests and linters only run when someone remembers to run "
            "them, so broken changes get merged.",
            "Add a GitHub Actions workflow in .github/workflows/ that installs "
            "dependencies and runs the tests and linter on every push and pull request.",
            detail="No GitHub Actions, GitLab CI, CircleCI, Travis, Azure or Jenkins "
            "configuration found.",
            impact=55,
        )
    ]


_ENV_FILE = re.compile(r"^\.env(\.[\w-]+)?$", re.IGNORECASE)
_ENV_TEMPLATE = re.compile(r"(example|sample|template|dist|defaults?)$", re.IGNORECASE)


def is_env_file(path: str) -> bool:
    name = basename(path)
    return bool(_ENV_FILE.match(name)) and not _ENV_TEMPLATE.search(name)


def check_gitignore_and_env(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    env_files = [p for p in ctx.paths if is_env_file(p)]
    if env_files:
        findings.append(
            _finding(
                "committed-env",
                "Environment file committed to the repository",
                "high",
                "Security",
                ".env files usually hold passwords and API keys. Anything committed "
                "stays in the git history even after the file is deleted.",
                "Delete the file, add .env to .gitignore, commit a .env.example with "
                "empty values instead, and rotate every secret it contained.",
                [Evidence(path=p) for p in env_files],
                detail="The file contents are not shown.",
                impact=95,
            )
        )
    if ".gitignore" not in ctx.root_files():
        findings.append(
            _finding(
                "no-gitignore",
                "No .gitignore at the root",
                "medium" if env_files else "low",
                "Security",
                "Without a .gitignore it is easy to commit build output, dependency "
                "folders, local databases or .env files by accident.",
                "Add a .gitignore for your languages (github/gitignore has templates) "
                "and include .env, build folders and editor files.",
                impact=40,
            )
        )
    return findings


# ---------- secrets ----------

_SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("GitHub token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Stripe live key", re.compile(r"\b[sr]k_live_[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI API key", re.compile(r"\bsk-(proj-)?[A-Za-z0-9_-]{32,}")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b")),
    ("Groq API key", re.compile(r"\bgsk_[A-Za-z0-9]{40,}\b")),
    (
        "Private key",
        re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY"),
    ),
]
_GENERIC_SECRET = re.compile(
    r"""(?i)\b(password|passwd|secret|api_?key|access_?token|auth_?token|secret_?key)\b"""
    r"""\s*[:=]\s*['"]([^'"\s]{8,})['"]"""
)
_PLACEHOLDER = re.compile(
    r"(?i)(x{4,}|\*{3,}|your|example|changeme|change_me|placeholder|dummy|sample|test|"
    r"fake|<|>|\$\{|\{\{|%\(|redacted|secret_key_here|not-?a-?secret)"
)


def redact_secrets(text: str) -> str:
    """Mask anything that looks like a credential before text leaves the server."""
    for _, pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: mask_secret(m.group(0)), text)
    return _GENERIC_SECRET.sub(
        lambda m: m.group(0).replace(m.group(2), mask_secret(m.group(2))), text
    )


def mask_secret(value: str) -> str:
    """Show only the first four characters, so a value can be recognised, not reused."""
    return f"{value[:4]}{'*' * min(8, max(4, len(value) - 4))}"


def find_secrets(
    ctx: Context,
) -> tuple[list[tuple[str, Evidence, str]], list[Evidence]]:
    """Return (specific matches as (kind, evidence, masked), generic assignments)."""
    specific: list[tuple[str, Evidence, str]] = []
    generic: list[Evidence] = []
    for path in ctx.paths:
        if is_env_file(path):
            continue  # reported on its own, and its contents are never shown
        text = ctx.reader.text(path)
        if not text:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if len(line) > 2000:
                continue
            for kind, pattern in _SECRET_PATTERNS:
                match = pattern.search(line)
                if match and not _PLACEHOLDER.search(match.group(0)):
                    specific.append(
                        (
                            kind,
                            Evidence(path=path, line=number),
                            mask_secret(match.group(0)),
                        )
                    )
                    break
            else:
                match = _GENERIC_SECRET.search(line)
                if match and not _PLACEHOLDER.search(match.group(2)):
                    generic.append(Evidence(path=path, line=number))
    return specific, generic


def check_secrets(ctx: Context) -> list[Finding]:
    specific, generic = find_secrets(ctx)
    findings: list[Finding] = []
    if specific:
        kinds = sorted({kind for kind, _, _ in specific})
        samples = ", ".join(sorted({masked for _, _, masked in specific})[:5])
        findings.append(
            _finding(
                "hardcoded-secrets",
                f"Possible hard-coded secrets ({len(specific)})",
                "high",
                "Security",
                "A key in the source can be copied by anyone who can read the "
                "repository, and bots scan public repositories for keys within minutes.",
                "Revoke and rotate each key now, move it to an environment variable or "
                "a secrets manager, and remove it from the git history.",
                [evidence for _, evidence, _ in specific],
                detail=f"Looks like: {', '.join(kinds)}. Masked values: {samples}.",
                impact=100,
            )
        )
    if generic:
        findings.append(
            _finding(
                "generic-secrets",
                f"Passwords or keys assigned in code ({len(generic)})",
                "medium",
                "Security",
                "Values assigned to names like password or api_key are often real "
                "credentials that end up in the repository by accident.",
                "Check each line. Read real credentials from environment variables "
                "and keep only obvious placeholders in code.",
                generic,
                detail="Matched by name only, so some may be harmless defaults.",
                status="Potential",
                impact=70,
            )
        )
    return findings


# ---------- dependencies ----------


def _is_unpinned(manifest: Manifest, spec: str) -> bool:
    spec = spec.strip()
    if manifest.kind == "requirements.txt":
        return spec == ""
    if manifest.ecosystem == "npm":
        return spec in ("", "*", "latest", "x")
    if manifest.kind in ("Pipfile",):
        return spec in ("", "*")
    return False


def check_unpinned(ctx: Context) -> list[Finding]:
    evidence: list[Evidence] = []
    names: list[str] = []
    for manifest in ctx.manifests:
        for dep in manifest.dependencies:
            if not dep.dev and _is_unpinned(manifest, dep.spec):
                evidence.append(Evidence(path=manifest.path, line=dep.line))
                names.append(dep.name)
    if not evidence:
        return []
    return [
        _finding(
            "unpinned-dependencies",
            f"Dependencies without a version ({len(evidence)})",
            "medium" if len(evidence) >= 5 else "low",
            "Dependencies",
            "With no version, every install can pull a newer release, so the app can "
            "break or change behaviour without any change to its code.",
            "Pin exact versions (or use a lock file) for applications, and at least a "
            "lower bound for libraries.",
            evidence,
            detail=f"For example: {', '.join(names[:8])}.",
            impact=45,
        )
    ]


def check_manifest_errors(ctx: Context) -> list[Finding]:
    broken = [m for m in ctx.manifests if m.error]
    if not broken:
        return []
    return [
        _finding(
            "broken-manifest",
            f"Dependency manifest could not be parsed ({len(broken)})",
            "medium",
            "Dependencies",
            "If the manifest is invalid, package managers and tools will fail to "
            "install the project.",
            "Validate the file (for example with a JSON or TOML linter) and fix the "
            "syntax error.",
            [Evidence(path=m.path) for m in broken],
            impact=65,
        )
    ]


# ---------- code size and structure ----------


def _line_count(text: str) -> int:
    return text.count("\n") + (0 if text.endswith("\n") or not text else 1)


def check_large_files(ctx: Context) -> list[Finding]:
    large: list[tuple[int, str]] = []
    for path in ctx.scripts():
        text = ctx.reader.text(path)
        if text and (lines := _line_count(text)) >= LONG_FILE_LINES:
            large.append((lines, path))
    findings: list[Finding] = []
    if large:
        large.sort(reverse=True)
        findings.append(
            _finding(
                "large-files",
                f"Very long source files ({len(large)})",
                "medium" if large[0][0] >= 2 * LONG_FILE_LINES else "low",
                "Maintainability",
                "Files over a thousand lines usually mix several responsibilities, "
                "which makes them hard to review, test and change safely.",
                "Split each file by responsibility into smaller modules.",
                [Evidence(path=path) for _, path in large],
                detail="Longest: "
                + ", ".join(f"{path} ({lines} lines)" for lines, path in large[:3])
                + ".",
                impact=35,
            )
        )
    too_large = ctx.scan.skipped.get("too_large", 0)
    if too_large:
        findings.append(
            _finding(
                "oversized-files",
                f"Files over {MAX_FILE_SIZE_BYTES // 1000} KB in the repository ({too_large})",
                "low",
                "Maintainability",
                "Large committed files slow down every clone. Data, models and media "
                "are better kept out of git.",
                "Move large assets to Git LFS, a release download or object storage.",
                detail="These files were skipped by RepoLens, so their names are not "
                "listed.",
                impact=20,
            )
        )
    return findings


_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
)


def _max_nesting(node: ast.AST, depth: int = 0) -> tuple[int, int]:
    """(deepest nesting below `node`, line where it happens)."""
    best = (depth, getattr(node, "lineno", 0))
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # nested definitions are measured on their own
        inner = depth + 1 if isinstance(child, _NESTING_NODES) else depth
        result = _max_nesting(child, inner)
        if result[0] > best[0]:
            best = result
    return best


def python_function_metrics(
    text: str,
) -> list[tuple[str, int, int, int, int]] | None:
    """(name, start line, length in lines, max nesting, nesting line) per function."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return None
    metrics = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            try:
                nesting, nesting_line = _max_nesting(node)
            except RecursionError:
                nesting, nesting_line = 0, node.lineno
            metrics.append((node.name, node.lineno, length, nesting, nesting_line))
    return metrics


def check_python_functions(ctx: Context) -> list[Finding]:
    long_functions: list[tuple[int, str, str, int]] = []
    deep: list[tuple[int, str, str, int]] = []
    syntax_errors: list[str] = []
    for path in ctx.scripts():
        if not is_python(path):
            continue
        text = ctx.reader.text(path)
        if not text:
            continue
        metrics = python_function_metrics(text)
        if metrics is None:
            syntax_errors.append(path)
            continue
        for name, line, length, nesting, nesting_line in metrics:
            if length >= LONG_FUNCTION_LINES:
                long_functions.append((length, path, name, line))
            if nesting >= DEEP_NESTING:
                deep.append((nesting, path, name, nesting_line))

    findings: list[Finding] = []
    if long_functions:
        long_functions.sort(reverse=True)
        findings.append(
            _finding(
                "long-functions",
                f"Long Python functions ({len(long_functions)})",
                "medium" if long_functions[0][0] >= 2 * LONG_FUNCTION_LINES else "low",
                "Maintainability",
                f"Functions over {LONG_FUNCTION_LINES} lines usually do several jobs, "
                "which makes them hard to test and easy to break.",
                "Extract the separate steps into smaller, named helper functions and "
                "test those directly.",
                [Evidence(path=p, line=line) for _, p, _, line in long_functions],
                detail="Longest: "
                + ", ".join(
                    f"{name}() {n} lines" for n, _, name, _ in long_functions[:3]
                )
                + ".",
                impact=30,
            )
        )
    if deep:
        deep.sort(reverse=True)
        findings.append(
            _finding(
                "deep-nesting",
                f"Deeply nested Python code ({len(deep)})",
                "low",
                "Maintainability",
                f"Code nested {DEEP_NESTING} or more blocks deep is hard to follow "
                "and hides edge cases.",
                "Use early returns and guard clauses, and move inner loops into helper "
                "functions.",
                [Evidence(path=p, line=line) for _, p, _, line in deep],
                detail="Deepest: "
                + ", ".join(f"{name}() {n} levels" for n, _, name, _ in deep[:3])
                + ".",
                impact=25,
            )
        )
    if syntax_errors:
        findings.append(
            _finding(
                "python-syntax-errors",
                f"Python files that do not parse ({len(syntax_errors)})",
                "medium",
                "Maintainability",
                "A file that does not parse cannot be imported or run on the current "
                "Python version.",
                "Fix the syntax error, or delete the file if it is no longer used.",
                [Evidence(path=p) for p in syntax_errors],
                impact=60,
            )
        )
    return findings


_TODO = re.compile(r"(#|//|/\*|\*|<!--)\s*(TODO|FIXME|HACK|XXX)\b")


def check_todos(ctx: Context) -> list[Finding]:
    hits: list[Evidence] = []
    fixmes = 0
    for path in ctx.scripts(include_tests=True):
        text = ctx.reader.text(path)
        if not text:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            match = _TODO.search(line)
            if match:
                hits.append(Evidence(path=path, line=number))
                fixmes += match.group(2) in ("FIXME", "HACK", "XXX")
    if not hits:
        return []
    return [
        _finding(
            "todo-comments",
            f"TODO and FIXME comments ({len(hits)})",
            "medium" if fixmes >= 10 else "low",
            "Maintainability",
            "Each one marks known unfinished or broken work that is easy to forget.",
            "Turn the important ones into tracked issues and resolve or delete the rest.",
            hits,
            detail=f"{fixmes} of {len(hits)} marked FIXME, HACK or XXX.",
            impact=15 + min(len(hits), 20),
        )
    ]


def check_cycles(ctx: Context) -> list[Finding]:
    cycles = ctx.graph.cycles
    if not cycles:
        return []
    return [
        _finding(
            "import-cycles",
            f"Import cycles ({len(cycles)})",
            "medium",
            "Maintainability",
            "Files that import each other cannot be understood, tested or reused "
            "alone, and in Python they can fail with partially initialised modules.",
            "Move the shared code into a new module that both import, or invert the "
            "dependency with an interface.",
            [Evidence(path=cycle.files[0]) for cycle in cycles],
            detail="First cycle: "
            + " -> ".join([*cycles[0].files, cycles[0].files[0]]),
            impact=40 + len(cycles),
        )
    ]


# ---------- tooling and deployment ----------


def _pyproject_tools(ctx: Context) -> str:
    texts = []
    for path in ctx.paths:
        name = basename(path).lower()
        if name in ("pyproject.toml", "setup.cfg", "tox.ini") and path.count("/") <= 2:
            texts.append(ctx.reader.text(path) or "")
    return "\n".join(texts)


def _has_dependency(ctx: Context, names: set[str]) -> bool:
    return any(dep.name in names for m in ctx.manifests for dep in m.dependencies)


def check_tooling(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    names = {basename(p).lower() for p in ctx.paths}
    python = [p for p in ctx.scripts() if is_python(p)]
    js = [p for p in ctx.scripts() if not is_python(p)]
    config = _pyproject_tools(ctx)

    if len(python) >= MIN_FILES_FOR_TOOLING:
        has_lint = (
            names & {"ruff.toml", ".ruff.toml", ".flake8", ".pylintrc", "pylintrc"}
            or re.search(r"\[(tool\.ruff|tool\.pylint|flake8|pylint)", config)
            or _has_dependency(ctx, {"ruff", "flake8", "pylint"})
        )
        if not has_lint:
            findings.append(
                _finding(
                    "no-python-linter",
                    "No Python linter configured",
                    "low",
                    "Tooling",
                    "A linter catches unused imports, undefined names and common bugs "
                    "before the code runs.",
                    "Add Ruff (pip install ruff) with a [tool.ruff] section in "
                    "pyproject.toml, and run ruff check in CI.",
                    detail=f"{len(python)} Python files; no Ruff, Flake8 or Pylint "
                    "configuration or dependency found.",
                    impact=30,
                )
            )
        has_types = (
            names & {"mypy.ini", ".mypy.ini", "pyrightconfig.json"}
            or re.search(r"\[(tool\.mypy|tool\.pyright|mypy)", config)
            or _has_dependency(ctx, {"mypy", "pyright"})
        )
        if not has_types:
            findings.append(
                _finding(
                    "no-python-typecheck",
                    "No Python type checker configured",
                    "low",
                    "Tooling",
                    "Type hints are only checked if a type checker runs. Without one, "
                    "wrong types surface as runtime errors.",
                    "Add mypy or Pyright, start with the main package, and run it in CI.",
                    detail="No mypy or Pyright configuration or dependency found.",
                    impact=25,
                )
            )

    if len(js) >= MIN_FILES_FOR_TOOLING:
        has_js_lint = any(
            n.startswith((".eslintrc", "eslint.config", "biome.json", ".oxlintrc"))
            for n in names
        ) or _has_dependency(ctx, {"eslint", "@biomejs/biome", "oxlint"})
        if not has_js_lint:
            findings.append(
                _finding(
                    "no-js-linter",
                    "No JavaScript or TypeScript linter configured",
                    "low",
                    "Tooling",
                    "A linter catches unused variables, missing hook dependencies and "
                    "common mistakes as you type.",
                    "Add ESLint, Biome or Oxlint with a config file and a lint script "
                    "in package.json.",
                    detail=f"{len(js)} script files; no ESLint, Biome or Oxlint found.",
                    impact=30,
                )
            )
        ts = [p for p in js if p.lower().endswith((".ts", ".tsx", ".mts", ".cts"))]
        if ts and "tsconfig.json" not in names:
            findings.append(
                _finding(
                    "no-tsconfig",
                    "TypeScript without tsconfig.json",
                    "medium",
                    "Tooling",
                    "Without tsconfig.json there is no strict type checking and "
                    "editors and builds may disagree about the settings.",
                    "Add tsconfig.json with strict set to true and run tsc --noEmit "
                    "in CI.",
                    [Evidence(path=ts[0])],
                    impact=40,
                )
            )
    return findings


def check_dockerignore(ctx: Context) -> list[Finding]:
    dockerfiles = [
        p
        for p in ctx.paths
        if basename(p).lower() == "dockerfile"
        or basename(p).lower().startswith("dockerfile.")
    ]
    ignores = {dirname(p) for p in ctx.paths if basename(p) == ".dockerignore"}
    missing = [
        p for p in dockerfiles if dirname(p) not in ignores and "" not in ignores
    ]
    if not missing:
        return []
    return [
        _finding(
            "no-dockerignore",
            "Dockerfile without .dockerignore",
            "low",
            "CI and deployment",
            "Without .dockerignore, the whole folder (including .git, node_modules "
            "and .env files) is sent to the Docker build and can end up in the image.",
            "Add .dockerignore next to the Dockerfile listing .git, .env, dependency "
            "folders and build output.",
            [Evidence(path=p, line=1) for p in missing],
            impact=30,
        )
    ]


DETECTORS: list[Callable[[Context], list[Finding]]] = [
    check_readme,
    check_license,
    check_tests,
    check_ci,
    check_gitignore_and_env,
    check_secrets,
    check_unpinned,
    check_manifest_errors,
    check_large_files,
    check_python_functions,
    check_todos,
    check_cycles,
    check_tooling,
    check_dockerignore,
]


def find_improvements(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    for detector in DETECTORS:
        findings.extend(detector(ctx))
    # Truthfulness guard: evidence must point at kept files.
    for finding in findings:
        kept = [e for e in finding.evidence if ctx.reader.has(e.path)]
        finding.evidence_total -= len(finding.evidence) - len(kept)
        finding.evidence = kept
    findings.sort(
        key=lambda f: (_SEVERITY_RANK[f.severity], f.status != "Confirmed", -f.impact)
    )
    return findings
