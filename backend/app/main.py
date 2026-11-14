import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.limits import STALE_WORKSPACE_SECONDS
from app.core.logging import setup_logging
from app.services.acquisition.workspace import cleanup_stale_workspaces

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "Starting %s v%s (%s)", settings.app_name, __version__, settings.app_env
    )

    removed = cleanup_stale_workspaces(settings.workspace_dir, STALE_WORKSPACE_SECONDS)
    if removed:
        logger.info("Removed %d stale workspace(s) left by an earlier run", removed)

    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.is_development else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
