"""Shared rules for telling source, test and example paths apart."""

import re
from typing import Literal

PathKind = Literal["source", "test", "example"]

_TEST_DIRS = frozenset({"test", "tests", "__tests__", "spec", "specs", "e2e"})
_TEST_FILE = re.compile(
    r"(^test_.*\.py$|.*_test\.(py|go)$|.*\.(test|spec)\.[cm]?[jt]sx?$|^conftest\.py$)"
)
_TEST_PART = re.compile(r"^(tests?|__tests__|specs?|e2e|testing|test_.*|.*_tests?)$")
_EXAMPLE_PART = re.compile(r"^(examples?|demos?|samples?|docs_src|playground|sandbox)$")


def is_test_path(path: str) -> bool:
    parts = path.lower().split("/")
    return any(part in _TEST_DIRS for part in parts[:-1]) or bool(
        _TEST_FILE.match(parts[-1])
    )


def folder_kind(folder: str) -> PathKind:
    """Classify a folder path such as 'backend/tests' or 'examples/demo'."""
    parts = folder.lower().split("/")
    if any(_TEST_PART.match(part) for part in parts):
        return "test"
    if any(_EXAMPLE_PART.match(part) for part in parts):
        return "example"
    return "source"


def path_kind(path: str) -> PathKind:
    if is_test_path(path):
        return "test"
    folder = path.rsplit("/", 1)[0] if "/" in path else ""
    return folder_kind(folder) if folder else "source"
