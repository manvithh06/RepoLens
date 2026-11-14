import pytest

from app.services.acquisition.file_filter import KeptFile
from app.services.intelligence.languages import detect_languages, language_of


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("main.py", "Python"),
        ("src/App.TSX", "TypeScript"),
        ("web/index.jsx", "JavaScript"),
        ("Dockerfile", "Dockerfile"),
        ("deploy/Dockerfile.prod", "Dockerfile"),
        ("Makefile", "Makefile"),
        ("README.md", "Markdown"),
        ("config/settings.yml", "YAML"),
        ("LICENSE", None),
        ("notes.unknownext", None),
    ],
)
def test_language_of(path: str, expected: str | None) -> None:
    assert language_of(path) == expected


def test_breakdown_ranks_by_bytes_and_picks_primary() -> None:
    files = [
        KeptFile(path="app/main.py", size=6_000),
        KeptFile(path="app/models.py", size=2_000),
        KeptFile(path="web/app.ts", size=1_000),
        KeptFile(path="web/style.css", size=1_000),
        KeptFile(path="README.md", size=50_000),
        KeptFile(path="LICENSE", size=1_000),
    ]

    result = detect_languages(files)

    assert [stat.name for stat in result.code] == ["Python", "CSS", "TypeScript"]
    assert result.code[0].files == 2
    assert result.code[0].bytes == 8_000
    assert result.code[0].percent == 80.0
    assert result.primary == "Python"
    assert [stat.name for stat in result.other] == ["Markdown"]
    assert result.other[0].percent == 100.0
    assert result.unknown_files == 1


def test_docs_never_become_the_primary_language() -> None:
    files = [
        KeptFile(path="docs/guide.md", size=90_000),
        KeptFile(path="script.sh", size=100),
    ]

    assert detect_languages(files).primary == "Shell"


def test_empty_repository() -> None:
    result = detect_languages([])

    assert result.code == []
    assert result.other == []
    assert result.primary is None
    assert result.unknown_files == 0


def test_percentages_add_up_to_about_100() -> None:
    files = [
        KeptFile(path=f"f{i}{ext}", size=333)
        for i, ext in enumerate([".py", ".go", ".rs"])
    ]

    total = sum(stat.percent for stat in detect_languages(files).code)

    assert total == pytest.approx(100, abs=0.2)
