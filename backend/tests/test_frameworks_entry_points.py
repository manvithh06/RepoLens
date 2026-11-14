from pathlib import Path

from app.services.intelligence.entry_points import find_entry_points
from app.services.intelligence.frameworks import detect_frameworks
from app.services.intelligence.manifests import parse_manifests
from app.services.intelligence.paths import is_test_path
from tests.fakerepo import make_reader


def test_frameworks_from_dependencies_and_files(tmp_path: Path) -> None:
    reader = make_reader(
        tmp_path / "r",
        {
            "backend/requirements.txt": "fastapi\nSQLAlchemy==2.0\npytest\n",
            "frontend/package.json": '{"dependencies": {"react": "19"}, "devDependencies": {"vite": "8"}}',
            "Dockerfile": "FROM python\n",
            "docker-compose.yml": "services: {}\n",
            ".github/workflows/ci.yml": "on: push\n",
            "infra/main.tf": "",
            "frontend/tsconfig.json": "{}",
        },
    )
    manifests = parse_manifests(reader)
    frameworks = {f.name: f for f in detect_frameworks(manifests, reader.paths)}

    assert frameworks["FastAPI"].category == "Backend"
    assert frameworks["FastAPI"].evidence[0].path == "backend/requirements.txt"
    assert frameworks["FastAPI"].evidence[0].line == 1
    assert frameworks["SQLAlchemy"].category == "Data and storage"
    assert frameworks["pytest"].category == "Testing"
    assert frameworks["React"].category == "Frontend"
    assert frameworks["Vite"].category == "Build and tooling"
    assert frameworks["Docker"].evidence[0].path == "Dockerfile"
    assert frameworks["Docker Compose"].category == "Deployment and CI"
    assert frameworks["GitHub Actions"].evidence[0].path == ".github/workflows/ci.yml"
    assert frameworks["Terraform"].evidence[0].path == "infra/main.tf"
    assert frameworks["TypeScript"].evidence[0].path == "frontend/tsconfig.json"
    order = [f.category for f in detect_frameworks(manifests, reader.paths)]
    assert (
        order.index("Frontend")
        < order.index("Backend")
        < order.index("Deployment and CI")
    )


def test_entry_points(tmp_path: Path) -> None:
    reader = make_reader(
        tmp_path / "r",
        {
            "app/main.py": "from fastapi import FastAPI\n\napp = FastAPI(title='x')\n",
            "flask_app.py": "from flask import Flask\napp = Flask(__name__)\n",
            "proj/wsgi.py": "application = get_wsgi_application()\n",
            "manage.py": "execute_from_command_line(sys.argv)\n",
            "dash.py": "import streamlit as st\nst.title('hi')\n",
            "tool.py": "def main(): ...\n\nif __name__ == '__main__':\n    main()\n",
            "tests/test_tool.py": "if __name__ == '__main__':\n    pass\n",
            "web/index.html": "<div id=root>",
            "web/package.json": '{\n  "main": "server.js",\n  "scripts": {\n    "dev": "vite",\n    "build": "tsc"\n  }\n}',
            "web/server.js": "app.listen(3000)\n",
            "web/src/main.tsx": "createRoot(document.getElementById('root')!).render(<App />)\n",
            "cmd/main.go": "package main\n\nfunc main() {}\n",
            "src/main.rs": "fn main() {}\n",
            "pyproject.toml": '[project]\nname="x"\n[project.scripts]\nx = "tool:main"\n',
        },
    )
    entries = find_entry_points(reader, parse_manifests(reader))
    found = {(e.path, e.kind): e for e in entries}

    assert found[("app/main.py", "FastAPI app")].line == 3
    assert found[("app/main.py", "FastAPI app")].detail == "app = FastAPI(title='x')"
    assert ("flask_app.py", "Flask app") in found
    assert ("proj/wsgi.py", "Django WSGI") in found
    assert ("manage.py", "Django manage.py") in found
    assert ("dash.py", "Streamlit app") in found
    assert found[("tool.py", "Main guard")].line == 3
    assert ("web/index.html", "Web page") in found
    assert found[("web/package.json", "npm script")].detail == "npm run dev: vite"
    assert found[("web/package.json", "npm script")].line == 4
    assert ("web/server.js", "package.json main") in found
    assert ("web/server.js", "Node server") in found
    assert ("web/src/main.tsx", "React root") in found
    assert ("cmd/main.go", "Go main package") in found
    assert ("src/main.rs", "Rust binary") in found
    assert ("tool.py", "Console script") in found
    assert not any(e.path.startswith("tests/") for e in entries)
    assert entries[0].kind in {
        "FastAPI app",
        "Flask app",
        "Streamlit app",
        "React root",
    }


def test_entry_points_are_capped(tmp_path: Path) -> None:
    files = {f"s{i}.py": "if __name__ == '__main__':\n    pass\n" for i in range(30)}
    reader = make_reader(tmp_path / "r", files)
    assert len(find_entry_points(reader, [])) == 20


def test_is_test_path() -> None:
    assert is_test_path("tests/x.py")
    assert is_test_path("pkg/test_x.py")
    assert is_test_path("src/a.test.tsx")
    assert is_test_path("x_test.go")
    assert not is_test_path("src/testing.py")
    assert not is_test_path("contest/main.py")
