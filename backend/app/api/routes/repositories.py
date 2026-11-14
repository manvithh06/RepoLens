import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi import Path as PathParam
from fastapi.responses import StreamingResponse

from app.api.deps import SettingsDep
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.limits import RATE_LIMIT_ANALYZE, RATE_LIMIT_CHAT, RATE_LIMIT_TOUR
from app.core.rate_limit import rate_limit
from app.schemas.analysis import RepositoryAnalysis
from app.schemas.chat import ChatAnswer, ChatRequest
from app.schemas.repository import (
    RepositoryCheckRequest,
    RepositoryInfo,
    RepositoryScan,
)
from app.schemas.tour import Tour
from app.services.acquisition.github_client import fetch_repo_info
from app.services.acquisition.repository import acquired_repository, summarize_scan
from app.services.acquisition.url_validator import parse_github_url
from app.services.chat.chat import answer_question
from app.services.intelligence.analysis import analyze_repository
from app.services.store import analysis_store
from app.services.tour.llm import LLMClient, build_client
from app.services.tour.tour import get_or_create_tour

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["repositories"])

AnalyzeLimit = Depends(rate_limit("analyze", RATE_LIMIT_ANALYZE))

AnalysisId = Annotated[str, PathParam(pattern=r"^[0-9a-f]{32}$")]


def get_llm_client(settings: Annotated[Settings, Depends(get_settings)]) -> LLMClient:
    return build_client(settings)


LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]


@router.post("/check", response_model=RepositoryInfo)
async def check_repository(
    payload: RepositoryCheckRequest,
    settings: SettingsDep,
) -> RepositoryInfo:
    ref = parse_github_url(payload.url)
    return await fetch_repo_info(ref, settings.github_token.get_secret_value())


@router.post("/scan", response_model=RepositoryScan)
async def scan_repository(
    payload: RepositoryCheckRequest,
    settings: SettingsDep,
) -> RepositoryScan:
    """Temporary endpoint: clones, filters and summarizes. Replaced by background jobs later."""
    ref = parse_github_url(payload.url)
    info = await fetch_repo_info(ref, settings.github_token.get_secret_value())
    async with acquired_repository(ref, info, settings.workspace_dir) as repo:
        return summarize_scan(repo)


@router.post("/analyze", response_model=RepositoryAnalysis, dependencies=[AnalyzeLimit])
async def analyze(
    payload: RepositoryCheckRequest,
    settings: SettingsDep,
) -> RepositoryAnalysis:
    """Clone, analyse and delete the clone before the response is sent."""
    ref = parse_github_url(payload.url)
    info = await fetch_repo_info(ref, settings.github_token.get_secret_value())
    async with acquired_repository(ref, info, settings.workspace_dir) as repo:
        bundle = await asyncio.to_thread(analyze_repository, repo)
    analysis_store.put(bundle.stored)
    return bundle.analysis


@router.post(
    "/analyze/stream",
    dependencies=[AnalyzeLimit],
    responses={200: {"content": {"application/x-ndjson": {}}}},
)
async def analyze_stream(
    payload: RepositoryCheckRequest,
    settings: SettingsDep,
) -> StreamingResponse:
    """Same as /analyze, but streams one JSON line per real stage, then the result.

    Lines: {"stage": "checking" | "cloning" | "analysing"}, then {"result": ...}
    or {"error": {"code": ..., "message": ...}}.
    """
    ref = parse_github_url(payload.url)  # bad URLs fail before the stream starts

    def line(value: dict[str, Any]) -> str:
        return json.dumps(value, separators=(",", ":")) + "\n"

    async def events() -> AsyncIterator[str]:
        try:
            yield line({"stage": "checking"})
            info = await fetch_repo_info(ref, settings.github_token.get_secret_value())
            yield line({"stage": "cloning"})
            async with acquired_repository(ref, info, settings.workspace_dir) as repo:
                yield line({"stage": "analysing"})
                bundle = await asyncio.to_thread(analyze_repository, repo)
            analysis_store.put(bundle.stored)
            yield line({"result": bundle.analysis.model_dump(mode="json")})
        except AppError as error:
            yield line({"error": {"code": error.code, "message": error.message}})
        except Exception:
            logger.exception("Streamed analysis failed")
            yield line(
                {
                    "error": {
                        "code": "internal_error",
                        "message": "Something went wrong on our side.",
                    }
                }
            )

    return StreamingResponse(events(), media_type="application/x-ndjson")


@router.post(
    "/{analysis_id}/tour",
    response_model=Tour,
    dependencies=[Depends(rate_limit("tour", RATE_LIMIT_TOUR))],
)
async def guided_tour(analysis_id: AnalysisId, client: LLMClientDep) -> Tour:
    """Summarise key files, then folders, then the repository. Cached per commit."""
    stored = analysis_store.get(analysis_id)
    return await get_or_create_tour(stored, client)


@router.post(
    "/{analysis_id}/chat",
    response_model=ChatAnswer,
    dependencies=[Depends(rate_limit("chat", RATE_LIMIT_CHAT))],
)
async def chat(
    analysis_id: AnalysisId, payload: ChatRequest, client: LLMClientDep
) -> ChatAnswer:
    """Answer from retrieved code only. Refuses when the code does not answer it."""
    stored = analysis_store.get(analysis_id)
    return await answer_question(stored, client, payload.question, payload.history)
