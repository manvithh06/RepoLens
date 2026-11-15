from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[2] is the backend/ folder
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        populate_by_name=True,
    )

    app_name: str = "RepoLens"
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"
    github_token: SecretStr = SecretStr("")
    workspace_dir: Path = BACKEND_DIR / "workspace"
    # Language model for the guided tour and chat. Keys are never sent to the browser.
    # With LLM_BASE_URL set, any OpenAI-compatible endpoint is used (for example Groq).
    # Without it, Hugging Face Inference Providers are used with HF_TOKEN.
    llm_base_url: str = ""
    llm_api_key: SecretStr = Field(
        default=SecretStr(""),
        validation_alias=AliasChoices("LLM_API_KEY", "GROQ_API_KEY"),
    )
    llm_model: str = Field(
        default="", validation_alias=AliasChoices("LLM_MODEL", "HF_MODEL")
    )
    hf_token: SecretStr = SecretStr("")
    hf_provider: str = "auto"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
