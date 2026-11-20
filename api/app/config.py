"""환경 변수 설정(인계서 17장)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:54322/postgres"

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwks_url: str = ""
    jwt_audience: str = "authenticated"

    llm_provider: str = "anthropic"  # anthropic | mock
    anthropic_api_key: str = ""
    llm_model_extract: str = "claude-sonnet-5-5"
    llm_model_light: str = "claude-haiku-5-5"

    embedding_provider: str = ""  # 19장: 착수 시 확정한다. 비어 있으면 임베딩을 계산하지 않는다
    embedding_model: str = ""
    embedding_dim: int = 1536

    cron_secret: str = ""
    allowed_origins: str = "http://localhost:3000"

    daily_limit_extract: int = 50
    daily_limit_import: int = 10
    daily_limit_document: int = 30
    daily_limit_url_add: int = 20

    worker_poll_seconds: float = Field(default=2.0, gt=0)
    stuck_job_minutes: int = 15

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
