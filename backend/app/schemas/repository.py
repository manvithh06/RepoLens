from pydantic import BaseModel, Field


class RepositoryCheckRequest(BaseModel):
    url: str = Field(min_length=1, max_length=300)


class RepositoryInfo(BaseModel):
    owner: str
    name: str
    full_name: str
    html_url: str
    description: str | None = None
    default_branch: str
    primary_language: str | None = None
    size_kb: int


class RepositoryScan(BaseModel):
    repository: RepositoryInfo
    file_count: int
    total_bytes: int
    truncated: bool
    skipped: dict[str, int]
    extensions: dict[str, int]
    sample_paths: list[str]
