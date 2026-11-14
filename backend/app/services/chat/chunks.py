"""Split kept files into chunks for retrieval: by function and class for Python, by
fixed line windows for everything else. Secrets are masked and .env files skipped."""

import ast
import warnings
from dataclasses import dataclass

from app.core.limits import (
    CHUNK_OVERLAP_LINES,
    CHUNK_WINDOW_LINES,
    MAX_CHAT_CHUNKS,
    MAX_CHUNK_LINES,
    MAX_CHUNKS_PER_FILE,
)
from app.services.intelligence.improvements import is_env_file, redact_secrets
from app.services.intelligence.languages import language_of
from app.services.intelligence.paths import is_test_path
from app.services.intelligence.reader import RepoReader

# Data files rarely answer questions about how code works.
_SKIP_LANGUAGES = frozenset({"CSV", "SVG", "Jupyter Notebook"})


@dataclass(frozen=True)
class Chunk:
    path: str
    start_line: int  # 1-based, inclusive
    end_line: int  # inclusive
    symbol: str | None  # function or class name for Python chunks
    text: str


def _windows(
    lines: list[str], start: int, end: int, symbol: str | None
) -> list[tuple[int, int, str | None]]:
    """1-based inclusive line ranges covering start..end in overlapping windows."""
    spans = []
    step = CHUNK_WINDOW_LINES - CHUNK_OVERLAP_LINES
    first = start
    while first <= end:
        last = min(end, first + CHUNK_WINDOW_LINES - 1)
        spans.append((first, last, symbol))
        if last == end:
            break
        first += step
    return spans


def _python_spans(text: str, lines: list[str]) -> list[tuple[int, int, str | None]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return _windows(lines, 1, len(lines), None)

    spans: list[tuple[int, int, str | None]] = []
    covered: set[int] = set()

    def add(node: ast.AST, name: str) -> None:
        start = min(
            [node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]
        )
        end = node.end_lineno or node.lineno
        covered.update(range(start, end + 1))
        if end - start + 1 <= MAX_CHUNK_LINES:
            spans.append((start, end, name))
        else:
            spans.extend(_windows(lines, start, end, name))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node, node.name)
        elif isinstance(node, ast.ClassDef):
            size = (node.end_lineno or node.lineno) - node.lineno + 1
            methods = [
                n
                for n in node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if size <= MAX_CHUNK_LINES or not methods:
                add(node, node.name)
            else:
                for method in methods:
                    add(method, f"{node.name}.{method.name}")
                header_end = max(node.lineno, methods[0].lineno - 1)
                spans.append((node.lineno, header_end, node.name))
                covered.update(range(node.lineno, header_end + 1))

    # Module-level code that is not inside a function or class.
    run_start = None
    for number in range(1, len(lines) + 2):
        loose = number <= len(lines) and number not in covered
        if loose and run_start is None:
            run_start = number
        elif not loose and run_start is not None:
            first, last = run_start, number - 1
            while first <= last and not lines[first - 1].strip():
                first += 1
            while last >= first and not lines[last - 1].strip():
                last -= 1
            if first <= last:
                spans.extend(_windows(lines, first, last, None))
            run_start = None
    return sorted(spans)


def chunk_file(path: str, text: str) -> list[Chunk]:
    lines = text.splitlines()
    if not lines:
        return []
    if path.endswith(".py"):
        spans = _python_spans(text, lines)
    else:
        spans = _windows(lines, 1, len(lines), None)
    chunks = []
    for start, end, symbol in spans[:MAX_CHUNKS_PER_FILE]:
        body = "\n".join(lines[start - 1 : end])
        if body.strip():
            chunks.append(Chunk(path, start, end, symbol, redact_secrets(body)))
    return chunks


def build_chunks(reader: RepoReader) -> list[Chunk]:
    def priority(path: str) -> tuple[int, int, str]:
        # Source first, tests last, so the cap drops the least useful chunks.
        return (is_test_path(path), path.count("/"), path)

    chunks: list[Chunk] = []
    for path in sorted(reader.paths, key=priority):
        language = language_of(path)
        if is_env_file(path) or language is None or language in _SKIP_LANGUAGES:
            continue
        text = reader.text(path)
        if not text:
            continue
        chunks.extend(chunk_file(path, text))
        if len(chunks) >= MAX_CHAT_CHUNKS:
            return chunks[:MAX_CHAT_CHUNKS]
    return chunks
