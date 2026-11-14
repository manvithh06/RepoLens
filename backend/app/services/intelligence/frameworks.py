"""Detect frameworks and tooling from manifest dependencies and well-known files."""

from collections.abc import Iterable
from fnmatch import fnmatch
from posixpath import basename

from app.schemas.analysis import Evidence, Framework, FrameworkCategory, Manifest

FRONTEND: FrameworkCategory = "Frontend"
BACKEND: FrameworkCategory = "Backend"
DATA: FrameworkCategory = "Data and storage"
ML: FrameworkCategory = "Machine learning and AI"
TESTING: FrameworkCategory = "Testing"
TOOLING: FrameworkCategory = "Build and tooling"
DEPLOY: FrameworkCategory = "Deployment and CI"

# (ecosystem, dependency name) -> (framework, category). Python names are normalised.
DEPENDENCY_FRAMEWORKS: dict[tuple[str, str], tuple[str, FrameworkCategory]] = {
    # npm: frontend
    ("npm", "react"): ("React", FRONTEND),
    ("npm", "next"): ("Next.js", FRONTEND),
    ("npm", "vue"): ("Vue", FRONTEND),
    ("npm", "nuxt"): ("Nuxt", FRONTEND),
    ("npm", "svelte"): ("Svelte", FRONTEND),
    ("npm", "@sveltejs/kit"): ("SvelteKit", FRONTEND),
    ("npm", "@angular/core"): ("Angular", FRONTEND),
    ("npm", "solid-js"): ("Solid", FRONTEND),
    ("npm", "astro"): ("Astro", FRONTEND),
    ("npm", "@remix-run/react"): ("Remix", FRONTEND),
    ("npm", "react-native"): ("React Native", FRONTEND),
    ("npm", "expo"): ("Expo", FRONTEND),
    ("npm", "tailwindcss"): ("Tailwind CSS", FRONTEND),
    ("npm", "@tanstack/react-query"): ("TanStack Query", FRONTEND),
    ("npm", "@tanstack/react-router"): ("TanStack Router", FRONTEND),
    ("npm", "react-router"): ("React Router", FRONTEND),
    ("npm", "react-router-dom"): ("React Router", FRONTEND),
    ("npm", "redux"): ("Redux", FRONTEND),
    ("npm", "@reduxjs/toolkit"): ("Redux", FRONTEND),
    ("npm", "zustand"): ("Zustand", FRONTEND),
    ("npm", "@chakra-ui/react"): ("Chakra UI", FRONTEND),
    ("npm", "@mui/material"): ("Material UI", FRONTEND),
    ("npm", "three"): ("three.js", FRONTEND),
    ("npm", "d3"): ("D3", FRONTEND),
    # npm: backend
    ("npm", "express"): ("Express", BACKEND),
    ("npm", "fastify"): ("Fastify", BACKEND),
    ("npm", "koa"): ("Koa", BACKEND),
    ("npm", "hono"): ("Hono", BACKEND),
    ("npm", "@nestjs/core"): ("NestJS", BACKEND),
    ("npm", "@trpc/server"): ("tRPC", BACKEND),
    ("npm", "socket.io"): ("Socket.IO", BACKEND),
    ("npm", "graphql"): ("GraphQL", BACKEND),
    ("npm", "@apollo/server"): ("Apollo Server", BACKEND),
    ("npm", "electron"): ("Electron", FRONTEND),
    # npm: data
    ("npm", "prisma"): ("Prisma", DATA),
    ("npm", "@prisma/client"): ("Prisma", DATA),
    ("npm", "drizzle-orm"): ("Drizzle ORM", DATA),
    ("npm", "mongoose"): ("Mongoose", DATA),
    ("npm", "typeorm"): ("TypeORM", DATA),
    ("npm", "sequelize"): ("Sequelize", DATA),
    ("npm", "pg"): ("PostgreSQL client", DATA),
    ("npm", "mysql2"): ("MySQL client", DATA),
    ("npm", "redis"): ("Redis client", DATA),
    ("npm", "ioredis"): ("Redis client", DATA),
    ("npm", "@supabase/supabase-js"): ("Supabase", DATA),
    ("npm", "firebase"): ("Firebase", DATA),
    # npm: ML
    ("npm", "openai"): ("OpenAI SDK", ML),
    ("npm", "@anthropic-ai/sdk"): ("Anthropic SDK", ML),
    ("npm", "langchain"): ("LangChain", ML),
    ("npm", "@tensorflow/tfjs"): ("TensorFlow.js", ML),
    ("npm", "ai"): ("Vercel AI SDK", ML),
    # npm: testing
    ("npm", "jest"): ("Jest", TESTING),
    ("npm", "vitest"): ("Vitest", TESTING),
    ("npm", "mocha"): ("Mocha", TESTING),
    ("npm", "cypress"): ("Cypress", TESTING),
    ("npm", "@playwright/test"): ("Playwright", TESTING),
    ("npm", "@testing-library/react"): ("Testing Library", TESTING),
    # npm: tooling
    ("npm", "vite"): ("Vite", TOOLING),
    ("npm", "webpack"): ("webpack", TOOLING),
    ("npm", "esbuild"): ("esbuild", TOOLING),
    ("npm", "rollup"): ("Rollup", TOOLING),
    ("npm", "parcel"): ("Parcel", TOOLING),
    ("npm", "turbo"): ("Turborepo", TOOLING),
    ("npm", "typescript"): ("TypeScript", TOOLING),
    ("npm", "eslint"): ("ESLint", TOOLING),
    ("npm", "oxlint"): ("Oxlint", TOOLING),
    ("npm", "@biomejs/biome"): ("Biome", TOOLING),
    ("npm", "prettier"): ("Prettier", TOOLING),
    # Python: backend
    ("pypi", "fastapi"): ("FastAPI", BACKEND),
    ("pypi", "flask"): ("Flask", BACKEND),
    ("pypi", "django"): ("Django", BACKEND),
    ("pypi", "djangorestframework"): ("Django REST framework", BACKEND),
    ("pypi", "starlette"): ("Starlette", BACKEND),
    ("pypi", "litestar"): ("Litestar", BACKEND),
    ("pypi", "aiohttp"): ("aiohttp", BACKEND),
    ("pypi", "tornado"): ("Tornado", BACKEND),
    ("pypi", "sanic"): ("Sanic", BACKEND),
    ("pypi", "uvicorn"): ("Uvicorn", BACKEND),
    ("pypi", "gunicorn"): ("Gunicorn", BACKEND),
    ("pypi", "celery"): ("Celery", BACKEND),
    ("pypi", "pydantic"): ("Pydantic", BACKEND),
    ("pypi", "click"): ("Click", BACKEND),
    ("pypi", "typer"): ("Typer", BACKEND),
    ("pypi", "streamlit"): ("Streamlit", FRONTEND),
    ("pypi", "gradio"): ("Gradio", FRONTEND),
    ("pypi", "dash"): ("Dash", FRONTEND),
    # Python: data
    ("pypi", "sqlalchemy"): ("SQLAlchemy", DATA),
    ("pypi", "sqlmodel"): ("SQLModel", DATA),
    ("pypi", "alembic"): ("Alembic", DATA),
    ("pypi", "psycopg"): ("PostgreSQL client", DATA),
    ("pypi", "psycopg2"): ("PostgreSQL client", DATA),
    ("pypi", "psycopg2-binary"): ("PostgreSQL client", DATA),
    ("pypi", "asyncpg"): ("PostgreSQL client", DATA),
    ("pypi", "pymongo"): ("MongoDB client", DATA),
    ("pypi", "motor"): ("MongoDB client", DATA),
    ("pypi", "redis"): ("Redis client", DATA),
    ("pypi", "pandas"): ("pandas", DATA),
    ("pypi", "polars"): ("Polars", DATA),
    ("pypi", "numpy"): ("NumPy", DATA),
    ("pypi", "neo4j"): ("Neo4j client", DATA),
    # Python: ML
    ("pypi", "torch"): ("PyTorch", ML),
    ("pypi", "tensorflow"): ("TensorFlow", ML),
    ("pypi", "keras"): ("Keras", ML),
    ("pypi", "scikit-learn"): ("scikit-learn", ML),
    ("pypi", "transformers"): ("Hugging Face Transformers", ML),
    ("pypi", "huggingface-hub"): ("Hugging Face Hub", ML),
    ("pypi", "sentence-transformers"): ("Sentence Transformers", ML),
    ("pypi", "openai"): ("OpenAI SDK", ML),
    ("pypi", "anthropic"): ("Anthropic SDK", ML),
    ("pypi", "langchain"): ("LangChain", ML),
    ("pypi", "llama-index"): ("LlamaIndex", ML),
    ("pypi", "xgboost"): ("XGBoost", ML),
    ("pypi", "lightgbm"): ("LightGBM", ML),
    ("pypi", "faiss-cpu"): ("FAISS", ML),
    ("pypi", "networkx"): ("NetworkX", DATA),
    # Python: testing and tooling
    ("pypi", "pytest"): ("pytest", TESTING),
    ("pypi", "hypothesis"): ("Hypothesis", TESTING),
    ("pypi", "tox"): ("tox", TESTING),
    ("pypi", "nox"): ("nox", TESTING),
    ("pypi", "coverage"): ("Coverage.py", TESTING),
    ("pypi", "ruff"): ("Ruff", TOOLING),
    ("pypi", "black"): ("Black", TOOLING),
    ("pypi", "flake8"): ("Flake8", TOOLING),
    ("pypi", "mypy"): ("mypy", TOOLING),
    ("pypi", "pyright"): ("Pyright", TOOLING),
    ("pypi", "pre-commit"): ("pre-commit", TOOLING),
    ("pypi", "sphinx"): ("Sphinx", TOOLING),
    ("pypi", "mkdocs"): ("MkDocs", TOOLING),
    # Rust
    ("cargo", "tokio"): ("Tokio", BACKEND),
    ("cargo", "axum"): ("Axum", BACKEND),
    ("cargo", "actix-web"): ("Actix Web", BACKEND),
    ("cargo", "rocket"): ("Rocket", BACKEND),
    ("cargo", "serde"): ("Serde", BACKEND),
    ("cargo", "clap"): ("clap", BACKEND),
    ("cargo", "diesel"): ("Diesel", DATA),
    ("cargo", "sqlx"): ("SQLx", DATA),
    ("cargo", "tauri"): ("Tauri", FRONTEND),
    # Go
    ("go", "github.com/gin-gonic/gin"): ("Gin", BACKEND),
    ("go", "github.com/labstack/echo/v4"): ("Echo", BACKEND),
    ("go", "github.com/gofiber/fiber/v2"): ("Fiber", BACKEND),
    ("go", "github.com/go-chi/chi/v5"): ("chi", BACKEND),
    ("go", "github.com/spf13/cobra"): ("Cobra", BACKEND),
    ("go", "gorm.io/gorm"): ("GORM", DATA),
    ("go", "github.com/stretchr/testify"): ("Testify", TESTING),
    # PHP and Ruby
    ("composer", "laravel/framework"): ("Laravel", BACKEND),
    ("composer", "symfony/framework-bundle"): ("Symfony", BACKEND),
    ("composer", "phpunit/phpunit"): ("PHPUnit", TESTING),
    ("rubygems", "rails"): ("Ruby on Rails", BACKEND),
    ("rubygems", "sinatra"): ("Sinatra", BACKEND),
    ("rubygems", "rspec"): ("RSpec", TESTING),
    ("rubygems", "rspec-rails"): ("RSpec", TESTING),
}

# (glob on the lowercased path, or on the file name when the pattern has no "/") ->
# (framework, category)
FILE_SIGNALS: list[tuple[str, str, FrameworkCategory]] = [
    ("dockerfile", "Docker", DEPLOY),
    ("dockerfile.*", "Docker", DEPLOY),
    ("*.dockerfile", "Docker", DEPLOY),
    ("docker-compose*.yml", "Docker Compose", DEPLOY),
    ("docker-compose*.yaml", "Docker Compose", DEPLOY),
    ("compose.yml", "Docker Compose", DEPLOY),
    ("compose.yaml", "Docker Compose", DEPLOY),
    (".github/workflows/*.yml", "GitHub Actions", DEPLOY),
    (".github/workflows/*.yaml", "GitHub Actions", DEPLOY),
    (".gitlab-ci.yml", "GitLab CI", DEPLOY),
    (".circleci/config.yml", "CircleCI", DEPLOY),
    ("render.yaml", "Render", DEPLOY),
    ("vercel.json", "Vercel", DEPLOY),
    ("netlify.toml", "Netlify", DEPLOY),
    ("fly.toml", "Fly.io", DEPLOY),
    ("procfile", "Procfile (Heroku style)", DEPLOY),
    ("*.tf", "Terraform", DEPLOY),
    ("manage.py", "Django", BACKEND),
    ("tsconfig.json", "TypeScript", TOOLING),
    ("makefile", "Make", TOOLING),
    (".pre-commit-config.yaml", "pre-commit", TOOLING),
]

_CATEGORY_ORDER = [FRONTEND, BACKEND, DATA, ML, TESTING, TOOLING, DEPLOY]
MAX_EVIDENCE = 5


def _matches(path: str, pattern: str) -> bool:
    lowered = path.lower()
    if "/" in pattern:
        return fnmatch(lowered, pattern) or fnmatch(lowered, f"*/{pattern}")
    return fnmatch(basename(lowered), pattern)


def detect_frameworks(
    manifests: Iterable[Manifest], paths: Iterable[str]
) -> list[Framework]:
    found: dict[str, tuple[FrameworkCategory, list[Evidence]]] = {}

    def add(name: str, category: FrameworkCategory, evidence: Evidence) -> None:
        _, items = found.setdefault(name, (category, []))
        if len(items) < MAX_EVIDENCE and evidence not in items:
            items.append(evidence)

    for manifest in manifests:
        for dep in manifest.dependencies:
            match = DEPENDENCY_FRAMEWORKS.get((manifest.ecosystem, dep.name))
            if match:
                add(match[0], match[1], Evidence(path=manifest.path, line=dep.line))

    for path in sorted(paths):
        for pattern, name, category in FILE_SIGNALS:
            if _matches(path, pattern):
                add(name, category, Evidence(path=path))

    frameworks = [
        Framework(name=name, category=category, evidence=evidence)
        for name, (category, evidence) in found.items()
    ]
    frameworks.sort(
        key=lambda f: (_CATEGORY_ORDER.index(f.category), -len(f.evidence), f.name)
    )
    return frameworks
