"""
Application settings, loaded from environment variables (and `.env` in development).

Every tunable lives here so deployments are configured, not patched.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "ScreenIQ"
    app_version: str = "2.0.0"
    environment: Environment = "development"
    log_level: str = "INFO"
    log_json: bool = False
    api_prefix: str = "/api/v1"
    # Public URL of the frontend — used to build candidate interview links.
    frontend_url: str = "http://localhost:5173"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/screeniq"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # ── Auth ─────────────────────────────────────────────────────────────────
    secret_key: str = "dev-insecure-secret-change-me-in-production-0123456789"
    access_token_ttl_minutes: int = 60 * 12
    auth_cookie_name: str = "screeniq_session"
    # Secure cookies require HTTPS; defaults to True in production.
    auth_cookie_secure: bool | None = None
    allow_public_signup: bool = True

    # ── LLM ──────────────────────────────────────────────────────────────────
    # "anthropic" for real inference. "mock" returns deterministic heuristic output
    # for local demos and tests — it is refused when environment=production.
    llm_provider: Literal["anthropic", "mock"] = "anthropic"
    anthropic_api_key: str | None = None
    llm_model: str = "claude-opus-5"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 3
    # Opt into server-side refusal fallbacks (Claude API only).
    llm_enable_fallbacks: bool = True

    # ── Embeddings ───────────────────────────────────────────────────────────
    # "bge": local BAAI/bge-large-en-v1.5 (needs requirements-ml.txt)
    # "openai": text-embedding-3-small projected to 1024 dims (needs OPENAI_API_KEY)
    # "hash": dependency-free lexical hashing embedder for tests / offline demos
    embedding_provider: Literal["bge", "openai", "hash"] = "bge"
    embedding_model: str | None = None
    openai_api_key: str | None = None

    # ── Pipeline ─────────────────────────────────────────────────────────────
    max_upload_mb: int = 10
    max_files_per_upload: int = 25
    max_concurrent_pipelines: int = 4
    rag_top_k_per_requirement: int = 3
    rag_max_requirements: int = 14

    # ── Interviews ───────────────────────────────────────────────────────────
    interview_link_ttl_days: int = 14
    interview_max_answer_chars: int = 4000

    # ── Email ────────────────────────────────────────────────────────────────
    # Candidate interview invitations. With SMTP_HOST unset nothing is sent:
    # the message (including the interview link) is written to the server log.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    # starttls (port 587) | ssl (port 465) | none
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_timeout_seconds: float = 20.0
    # Sender address; defaults to SMTP_USERNAME.
    email_from: str | None = None

    # ── Rate limiting (per client IP, in-process) ────────────────────────────
    rate_limit_auth_per_minute: int = 20
    rate_limit_public_per_minute: int = 30

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("secret_key", "anthropic_api_key", "openai_api_key", "smtp_host", "smtp_username",
                     "smtp_password", "email_from", mode="before")
    @classmethod
    def _blank_to_default(cls, v: object, info) -> object:
        # `KEY=` in an env file means "unset", not "empty string"
        if isinstance(v, str) and not v.strip():
            return cls.model_fields[info.field_name].default
        return v

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.environment == "production":
            problems = []
            if self.secret_key.startswith("dev-insecure") or len(self.secret_key) < 32:
                problems.append("SECRET_KEY must be set to a random value of 32+ characters")
            if self.llm_provider == "mock":
                problems.append("LLM_PROVIDER=mock is not allowed in production")
            if self.embedding_provider == "hash":
                problems.append("EMBEDDING_PROVIDER=hash is not allowed in production")
            if self.llm_provider == "anthropic" and not self.anthropic_api_key:
                problems.append("ANTHROPIC_API_KEY is required")
            if problems:
                raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cookie_secure(self) -> bool:
        return self.is_production if self.auth_cookie_secure is None else self.auth_cookie_secure

    @property
    def email_delivery(self) -> Literal["smtp", "console"]:
        return "smtp" if self.smtp_host else "console"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
