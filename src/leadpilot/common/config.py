"""Central settings. One source of truth; read from env (Railway variables)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Runtime
    environment: str = Field(default="development")
    app_base_url: str = Field(default="http://localhost:8000")
    log_level: str = Field(default="INFO")
    railway_region: str = Field(default="southeast-asia")

    # Mock switches — true keeps the walking skeleton self-contained (no external accounts).
    mock_meta: bool = True
    mock_whatsapp: bool = True
    mock_razorpay: bool = True
    mock_llm: bool = True
    mock_otp: bool = True

    # Datastores
    database_url: str = Field(
        default="postgresql+psycopg://leadpilot:leadpilot@localhost:5432/leadpilot"
    )
    database_url_pooled: str | None = None
    database_migration_url: str | None = None
    app_tenant_db_role: str = "leadpilot_app"
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Auth
    jwt_secret: str = Field(default="dev-only-change-me")
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_min: int = 43200
    token_encryption_key: str = Field(default="dev-only-32byte-key-change-me____")

    # LLM router
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_reasoning_model: str = "claude-opus-4-8"
    llm_creative_model: str = "gemini-1.5-flash"
    llm_closer_model: str = "gemini-1.5-flash"
    llm_daily_budget_per_account_paise: int = 5000

    # Meta
    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    meta_graph_api_version: str = "v21.0"
    meta_webhook_verify_token: str = "dev-verify-token"

    # WhatsApp Cloud API
    whatsapp_cloud_api_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_app_secret: str | None = None
    whatsapp_webhook_verify_token: str = "dev-verify-token"

    # WhatsApp transport when not mocked: "cloud" (Meta direct) or "bsp" (aggregator
    # middleware — fastest go-live, the BSP is the Meta Tech Provider).
    whatsapp_provider: str = "cloud"
    # Generic BSP config (works for most Indian BSPs that expose a Meta-compatible REST
    # send endpoint; see docs/WHATSAPP_PROVIDERS.md for per-provider mapping).
    bsp_base_url: str | None = None
    bsp_api_key: str | None = None
    bsp_send_path: str = "/messages"
    bsp_auth_header: str = "Authorization"
    bsp_auth_scheme: str = "Bearer"

    # Razorpay
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

    # Object storage (R2/S3)
    r2_endpoint: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket: str = "leadpilot-assets"
    r2_region: str = "auto"

    # OTP
    otp_provider: str = "msg91"
    msg91_api_key: str | None = None

    # Observability
    sentry_dsn: str | None = None
    otel_exporter_otlp_endpoint: str | None = None

    # Scaling
    optimizer_shard_count: int = 4
    default_trust_threshold: int = 2
    # Run owner-initiated pipeline phases synchronously in the BFF request (pilot/dev).
    # Set false in production → BFF enqueues worker jobs and returns immediately.
    pipeline_inline: bool = True

    def insecure_secrets(self) -> list[str]:
        """Dev-default secrets that MUST be replaced in production."""
        bad = []
        if self.jwt_secret == "dev-only-change-me":
            bad.append("JWT_SECRET")
        if self.token_encryption_key == "dev-only-32byte-key-change-me____":
            bad.append("TOKEN_ENCRYPTION_KEY")
        return bad

    @property
    def db_url(self) -> str:
        """Runtime (pooled) DB URL for app services."""
        return self.database_url_pooled or self.database_url

    @property
    def migration_db_url(self) -> str:
        return self.database_migration_url or self.database_url

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
