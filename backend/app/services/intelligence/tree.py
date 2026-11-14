"""Build a nested file tree from the kept files."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.schemas.analysis import TreeNode
from app.services.acquisition.file_filter import KeptFile


@dataclass
class _Folder:
    folders: dict[str, "_Folder"] = field(default_factory=dict)
    files: dict[str, int] = field(default_factory=dict)


def _sort_key(node: TreeNode) -> tuple[bool, str, str]:
    return (not node.is_dir, node.name.lower(), node.name)


def _to_node(name: str, path: str, folder: _Folder) -> TreeNode:
    children = [
        _to_node(child, f"{path}/{child}" if path else child, sub)
        for child, sub in folder.folders.items()
    ]
    children += [
        TreeNode(
            name=child,
            path=f"{path}/{child}" if path else child,
            is_dir=False,
            size=size,
            file_count=1,
        )
        for child, size in folder.files.items()
    ]
    children.sort(key=_sort_key)
    return TreeNode(
        name=name,
        path=path,
        is_dir=True,
        size=sum(child.size for child in children),
        file_count=sum(child.file_count for child in children),
        children=children,
    )


def build_tree(files: Iterable[KeptFile], root_name: str = "") -> TreeNode:
    root = _Folder()
    for kept in files:
        *folders, name = kept.path.split("/")
        current = root
        for part in folders:
            current = current.folders.setdefault(part, _Folder())
        current.files[name] = kept.size
    return _to_node(root_name, "", root)
