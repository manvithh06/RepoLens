"""Work out which languages a repository is written in, measured by bytes of source."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from posixpath import basename, splitext

from app.services.acquisition.file_filter import KeptFile

# Lowercased extension -> language name.
EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".swift": "Swift",
    ".dart": "Dart",
    ".scala": "Scala",
    ".lua": "Lua",
    ".r": "R",
    ".jl": "Julia",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SCSS",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".ipynb": "Jupyter Notebook",
    # Not programming languages: reported separately so they never win "primary language".
    ".md": "Markdown",
    ".mdx": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".xml": "XML",
    ".csv": "CSV",
    ".svg": "SVG",
}

# Files recognised by their whole (lowercased) name rather than an extension.
FILENAME_LANGUAGES: dict[str, str] = {
    "dockerfile": "Dockerfile",
    "makefile": "Makefile",
    "cmakelists.txt": "CMake",
    "gemfile": "Ruby",
    "rakefile": "Ruby",
    "jenkinsfile": "Groovy",
    "procfile": "Procfile",
}

NON_CODE_LANGUAGES = frozenset(
    {
        "Markdown",
        "reStructuredText",
        "Text",
        "JSON",
        "YAML",
        "TOML",
        "INI",
        "XML",
        "CSV",
        "SVG",
        "Procfile",
    }
)


@dataclass(frozen=True)
class LanguageStat:
    name: str
    files: int
    bytes: int
    percent: float  # share of the bytes in its own group (code or other), 0 to 100


@dataclass(frozen=True)
class LanguageBreakdown:
    code: list[LanguageStat]  # programming languages, largest first
    other: list[LanguageStat]  # docs, config and data formats, largest first
    primary: str | None  # the code language with the most bytes
    unknown_files: int  # kept files we could not assign a language to


def language_of(path: str) -> str | None:
    """Return the language for a repository-relative path, or None if unknown."""
    name = basename(path).lower()
    if name in FILENAME_LANGUAGES:
        return FILENAME_LANGUAGES[name]
    if name.startswith("dockerfile."):
        return "Dockerfile"
    return EXTENSION_LANGUAGES.get(splitext(name)[1])


def _ranked(totals: dict[str, list[int]]) -> list[LanguageStat]:
    group_bytes = sum(size for _, size in totals.values())
    ordered = sorted(totals.items(), key=lambda item: (-item[1][1], item[0]))
    return [
        LanguageStat(
            name=name,
            files=files,
            bytes=size,
            percent=round(100 * size / group_bytes, 1) if group_bytes else 0.0,
        )
        for name, (files, size) in ordered
    ]


def detect_languages(files: Iterable[KeptFile]) -> LanguageBreakdown:
    code: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    other: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    unknown = 0

    for kept in files:
        language = language_of(kept.path)
        if language is None:
            unknown += 1
            continue
        bucket = other if language in NON_CODE_LANGUAGES else code
        bucket[language][0] += 1
        bucket[language][1] += kept.size

    code_stats = _ranked(code)
    return LanguageBreakdown(
        code=code_stats,
        other=_ranked(other),
        primary=code_stats[0].name if code_stats else None,
        unknown_files=unknown,
    )