from pathlib import Path

from app.services.intelligence.graph import (
    build_architecture,
    build_import_graph,
    find_cycles,
    module_kind,
    strongly_connected,
)
from app.services.intelligence.imports import collect_imports
from tests.fakerepo import make_reader


def _imports(tmp_path: Path, files: dict[str, str]):
    reader = make_reader(tmp_path / "repo", files)
    return reader, collect_imports(reader)


def test_python_absolute_relative_and_monorepo_imports(tmp_path: Path) -> None:
    _, result = _imports(
        tmp_path,
        {
            "backend/app/__init__.py": "",
            "backend/app/main.py": (
                "import os\nfrom app.core import config\nfrom .api import routes\n"
                "import fastapi\nfrom _private import x\n"
            ),
            "backend/app/core/__init__.py": "",
            "backend/app/core/config.py": "from ..api.routes import handler\n",
            "backend/app/api/__init__.py": "",
            "backend/app/api/routes.py": "from . import missing_mod\nimport app.core.config\n",
        },
    )

    assert result.edges["backend/app/main.py"] == {
        "backend/app/core/config.py": 2,
        "backend/app/api/routes.py": 3,
    }
    assert set(result.edges["backend/app/core/config.py"]) == {
        "backend/app/api/routes.py"
    }
    # "from . import missing_mod" falls back to the package itself.
    assert set(result.edges["backend/app/api/routes.py"]) == {
        "backend/app/api/__init__.py",
        "backend/app/core/config.py",
    }
    assert result.external == {("fastapi", "python"): 1}
    assert result.parse_errors == 0


def test_python_prefers_the_closest_matching_module(tmp_path: Path) -> None:
    _, result = _imports(
        tmp_path,
        {
            "one/utils.py": "",
            "one/main.py": "import utils\n",
            "two/utils.py": "",
            "two/deep/main.py": "import utils\n",
        },
    )
    assert set(result.edges["one/main.py"]) == {"one/utils.py"}
    assert set(result.edges["two/deep/main.py"]) == {"two/utils.py"}


def test_python_syntax_errors_are_counted(tmp_path: Path) -> None:
    _, result = _imports(tmp_path, {"bad.py": "def (:\n", "ok.py": "import bad\n"})
    assert result.parse_errors == 1
    assert set(result.edges["ok.py"]) == {"bad.py"}


def test_js_and_ts_imports(tmp_path: Path) -> None:
    _, result = _imports(
        tmp_path,
        {
            "web/package.json": "{}",
            "web/src/main.tsx": (
                "import React from 'react'\n"
                "import { App } from './App'\n"
                "import './index.css'\n"
                "import data from './data.json'\n"
                "import { api } from '@/lib/api'\n"
                "import fs from 'node:fs'\n"
                "import path from 'path'\n"
                'export { thing } from "./components"\n'
                "// import nope from './Nope'\n"
                "const lazy = import('./Lazy.js')\n"
                "const x = require('@tanstack/react-query/build')\n"
                "import gone from './gone'\n"
            ),
            "web/src/App.tsx": "",
            "web/src/index.css": "",
            "web/src/data.json": "{}",
            "web/src/lib/api.ts": "",
            "web/src/components/index.ts": "",
            "web/src/Lazy.ts": "",
            "web/src/Nope.ts": "",
        },
    )

    assert result.edges["web/src/main.tsx"] == {
        "web/src/App.tsx": 2,
        "web/src/lib/api.ts": 5,
        "web/src/components/index.ts": 8,
        "web/src/Lazy.ts": 10,
    }
    assert result.external == {
        ("react", "npm"): 1,
        ("@tanstack/react-query", "npm"): 1,
    }
    assert result.unresolved == 1


def test_cycles_and_scc() -> None:
    adjacency = {
        "a": ["b"],
        "b": ["c"],
        "c": ["a", "d"],
        "d": [],
        "e": ["e2"],
        "e2": ["e"],
    }
    components = strongly_connected(["a", "b", "c", "d", "e", "e2"], adjacency)

    assert sorted(sorted(c) for c in components if len(c) > 1) == [
        ["a", "b", "c"],
        ["e", "e2"],
    ]
    cycles = find_cycles(["a", "b", "c", "d", "e", "e2"], adjacency)
    assert cycles[0].files == ["a", "b", "c"]
    assert cycles[0].group_size == 3
    assert cycles[1].files == ["e", "e2"]


def test_tarjan_handles_long_chains_without_recursion() -> None:
    nodes = [f"n{i}" for i in range(20_000)]
    adjacency = {nodes[i]: [nodes[i + 1]] for i in range(len(nodes) - 1)}
    adjacency[nodes[-1]] = [nodes[0]]
    components = strongly_connected(nodes, adjacency)
    assert len(components) == 1


def test_graph_nodes_edges_and_externals(tmp_path: Path) -> None:
    reader, result = _imports(
        tmp_path,
        {
            "a.py": "import b\nimport requests\n",
            "b.py": "import a\nimport requests\n",
            "c.py": "import numpy\n",
        },
    )
    graph = build_import_graph(reader, result)

    assert {n.id for n in graph.nodes} == {"a.py", "b.py", "c.py"}
    node_a = next(n for n in graph.nodes if n.id == "a.py")
    assert (node_a.imports, node_a.imported_by, node_a.language) == (1, 1, "Python")
    assert {(e.source, e.target) for e in graph.edges} == {
        ("a.py", "b.py"),
        ("b.py", "a.py"),
    }
    assert graph.cycles[0].files == ["a.py", "b.py"]
    assert [(p.name, p.files) for p in graph.external_packages] == [
        ("requests", 2),
        ("numpy", 1),
    ]
    assert not graph.truncated


def test_architecture_picks_deepest_level_and_tags_modules(tmp_path: Path) -> None:
    reader, result = _imports(
        tmp_path,
        {
            "src/pkg/api/routes.py": "from pkg.core import db\nfrom pkg.core import models\n",
            "src/pkg/core/db.py": "",
            "src/pkg/core/models.py": "",
            "tests/test_api.py": "from pkg.api import routes\n",
            "examples/demo.py": "from pkg.core import db\n",
            "setup.py": "",
        },
    )
    arch = build_architecture(reader, result)

    assert arch.depth == 4
    kinds = {m.id: m.kind for m in arch.modules}
    assert kinds == {
        "(root)": "source",
        "src/pkg/api": "source",
        "src/pkg/core": "source",
        "tests": "test",
        "examples": "example",
    }
    weights = {(e.source, e.target): e.weight for e in arch.edges}
    assert weights == {
        ("src/pkg/api", "src/pkg/core"): 2,
        ("tests", "src/pkg/api"): 1,
        ("examples", "src/pkg/core"): 1,
    }


def test_architecture_stays_within_the_group_limit(tmp_path: Path) -> None:
    files = {f"mod{i}/sub{j}/f.py": "" for i in range(5) for j in range(5)}
    reader, result = _imports(tmp_path, files)
    arch = build_architecture(reader, result)
    assert arch.depth == 1
    assert len(arch.modules) == 5

    wide = {f"top{i}/f.py": "" for i in range(30)}
    reader, result = _imports(tmp_path / "wide", wide)
    arch = build_architecture(reader, result)
    assert len(arch.modules) == 18
    assert any(m.id == "(other folders)" for m in arch.modules)


def test_module_kind() -> None:
    assert module_kind("backend/tests") == "test"
    assert module_kind("src/__tests__") == "test"
    assert module_kind("docs_src/tutorial") == "example"
    assert module_kind("src/testing_utils") == "source"
