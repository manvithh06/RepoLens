import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import Path as PathParam

from app.api.deps import SettingsDep
from app.core.config import Settings, get_settings
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

router = APIRouter(prefix="/repositories", tags=["repositories"])

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


@router.post("/analyze", response_model=RepositoryAnalysis)
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


@router.post("/{analysis_id}/tour", response_model=Tour)
async def guided_tour(analysis_id: AnalysisId, client: LLMClientDep) -> Tour:
    """Summarise key files, then folders, then the repository. Cached per commit."""
    stored = analysis_store.get(analysis_id)
    return await get_or_create_tour(stored, client)


@router.post("/{analysis_id}/chat", response_model=ChatAnswer)
async def chat(
    analysis_id: AnalysisId, payload: ChatRequest, client: LLMClientDep
) -> ChatAnswer:
    """Answer from retrieved code only. Refuses when the code does not answer it."""
    stored = analysis_store.get(analysis_id)
    return await answer_question(stored, client, payload.question, payload.history)
