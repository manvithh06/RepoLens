from app.services.acquisition.file_filter import KeptFile
from app.services.intelligence.tree import build_tree


def test_builds_nested_tree_with_folders_first_and_totals() -> None:
    files = [
        KeptFile("README.md", 10),
        KeptFile("src/b.py", 5),
        KeptFile("src/A.py", 7),
        KeptFile("src/util/x.py", 3),
        KeptFile("Docs/guide.md", 2),
    ]

    root = build_tree(files, root_name="demo")

    assert root.name == "demo"
    assert root.path == ""
    assert root.file_count == 5
    assert root.size == 27
    assert [c.name for c in root.children] == ["Docs", "src", "README.md"]
    src = root.children[1]
    assert [c.name for c in src.children] == ["util", "A.py", "b.py"]
    assert src.children[0].path == "src/util"
    assert src.children[0].is_dir
    assert src.file_count == 3
    assert src.size == 15
    assert src.children[1].path == "src/A.py"


def test_empty_repository_gives_an_empty_root() -> None:
    root = build_tree([])
    assert root.is_dir
    assert root.children == []
    assert root.file_count == 0
