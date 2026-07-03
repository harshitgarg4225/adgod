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
    web_base_url: str = Field(default="http://localhost:3000")
    # Comma-separated allowed CORS origins in production. Empty → fall back to web_base_url.
    cors_allowed_origins: str = Field(default="")
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
    db_pool_size: int = 3
    db_max_overflow: int = 7
    # Trust X-Forwarded-For for the real client IP (true behind a proxy like Railway).
    trust_proxy: bool = False
    app_tenant_db_role: str = "leadpilot_app"
    # Role used by platform_session for legitimate cross-tenant work (webhooks, admin,
    # cron). Must be able to bypass RLS. Empty → use the base connection role (works only
    # if that role is a superuser/BYPASSRLS, e.g. local/CI). Set in production.
    app_platform_db_role: str = ""
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Auth
    jwt_secret: str = Field(default="dev-only-change-me")
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_min: int = 43200
    token_encryption_key: str = Field(default="dev-only-32byte-key-change-me____")

    # LLM router. Defaults favour Anthropic (one key covers every role); Gemini models are
    # opt-in via env. gemini-1.5-* is retired for new API projects — use 2.x if overriding.
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_reasoning_model: str = "claude-opus-4-8"
    llm_creative_model: str = "claude-haiku-4-5-20251001"
    llm_closer_model: str = "claude-haiku-4-5-20251001"
    llm_daily_budget_per_account_paise: int = 5000
    llm_max_output_tokens: int = 2048
    llm_request_timeout_s: float = 30.0
    # UGC video generation via fal.ai (Kling / other text-to-video models).
    fal_api_key: str | None = None
    fal_video_model: str = "fal-ai/kling-video/v1/standard/text-to-video"
    fal_video_duration: str = "5"        # seconds, as the model expects
    fal_poll_timeout_s: float = 180.0    # video renders take a while
    fal_poll_interval_s: float = 3.0

    # Meta
    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    # Founder/agency Business Manager System User token — the review-free launch path
    # runs every client's ads with this one token. Per-account tokens stored on
    # MetaConnection (encrypted) take precedence when present.
    meta_system_user_token: str | None = None
    meta_graph_api_version: str = "v23.0"
    meta_webhook_verify_token: str = "dev-verify-token"
    # Meta rejects ad sets under a per-currency daily minimum (~₹90/day for INR
    # impressions billing). Ad-set tiers whose share of the budget falls below this fold
    # into PROSPECTING instead of failing the launch (small budgets → fewer, viable tiers).
    meta_min_adset_daily_paise: int = 9000

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
    # DLT-registered OTP template id — mandatory for OTP SMS delivery in India.
    msg91_template_id: str | None = None

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

    def production_warnings(self) -> list[str]:
        """Non-fatal production misconfig — logged loudly at boot so a half-configured
        deploy is obvious (dev-default secrets are handled separately and fail-closed)."""
        w: list[str] = []
        if not self.is_production:
            return w
        if not self.app_platform_db_role:
            w.append("APP_PLATFORM_DB_ROLE empty (webhooks/admin/cron need a BYPASSRLS role)")
        if not self.cors_allowed_origins:
            w.append("CORS_ALLOWED_ORIGINS empty (falling back to WEB_BASE_URL)")
        if self.pipeline_inline:
            w.append("PIPELINE_INLINE=true in production (should enqueue workers)")
        # A live integration with no credentials is almost certainly a mistake.
        if not self.mock_meta and not self.meta_system_user_token:
            w.append("MOCK_META=false but META_SYSTEM_USER_TOKEN is empty — accounts "
                     "without a per-client token in meta_connections cannot run ads")
        if not self.mock_otp and not (self.msg91_api_key and self.msg91_template_id):
            w.append("MOCK_OTP=false but MSG91_API_KEY/MSG91_TEMPLATE_ID incomplete — "
                     "OTP SMS will not deliver (DLT template id is mandatory in India)")
        if not self.mock_whatsapp and not (self.whatsapp_app_secret or self.bsp_api_key):
            w.append("MOCK_WHATSAPP=false but no WhatsApp secret configured")
        if not self.mock_razorpay and not self.razorpay_webhook_secret:
            w.append("MOCK_RAZORPAY=false but RAZORPAY_WEBHOOK_SECRET is empty")
        if not self.mock_llm and not (self.anthropic_api_key or self.gemini_api_key):
            w.append("MOCK_LLM=false but no LLM API key configured")
        if not self.database_url_pooled:
            w.append("DATABASE_URL_POOLED empty — use PgBouncer (transaction mode) so "
                     "worker replicas don't exhaust Postgres max_connections")
        if not self.trust_proxy:
            w.append("TRUST_PROXY=false behind a proxy → per-IP rate limits/audit see the "
                     "proxy IP; set TRUST_PROXY=true on Railway")
        return w

    @staticmethod
    def _with_psycopg(url: str) -> str:
        """Force the psycopg (v3) driver. A bare postgresql:// (what Railway's
        ${{Postgres.DATABASE_URL}} provides) maps to psycopg2, which we don't install —
        create_engine would crash at import. Normalise so operators can paste the URL as-is."""
        if url.startswith("postgresql+"):
            return url
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        return url

    @property
    def db_url(self) -> str:
        """Runtime (pooled) DB URL for app services."""
        return self._with_psycopg(self.database_url_pooled or self.database_url)

    @property
    def migration_db_url(self) -> str:
        return self._with_psycopg(self.database_migration_url or self.database_url)

    @property
    def is_production(self) -> bool:
        """Fail-closed: any environment that is not an explicitly recognised local/dev/test
        value gets the full production posture (dev-secret boot refusal, restricted CORS,
        hidden dev_code, RLS role required). A typo'd ENVIRONMENT ('prod', 'staging', '')
        must never silently boot with dev defaults — same allowlist the webhook signature
        gate uses."""
        return self.environment.lower() not in {"development", "dev", "test", "local"}

    @property
    def requires_secure_webhooks(self) -> bool:
        """Fail-closed posture: only an explicitly recognised local/dev/test environment
        may accept unsigned webhooks. Any unknown or mis-spelled ENVIRONMENT value (e.g.
        'prod', 'staging', '') is treated as needing signatures — so a typo can never
        silently disable signature verification."""
        return self.environment.lower() not in {"development", "dev", "test", "local"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
