from fastapi import APIRouter

from app.api.deps import SettingsDep
from app.schemas.repository import RepositoryCheckRequest, RepositoryInfo
from app.services.acquisition.github_client import fetch_repo_info
from app.services.acquisition.url_validator import parse_github_url

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("/check", response_model=RepositoryInfo)
async def check_repository(
    payload: RepositoryCheckRequest,
    settings: SettingsDep,
) -> RepositoryInfo:
    ref = parse_github_url(payload.url)
    return await fetch_repo_info(ref, settings.github_token.get_secret_value())