from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PROVIDER = "fixture"
OWNER_ID = "efren"


class Settings(BaseSettings):
    # Explicit environment only: never load a credentials file implicitly.
    model_config = SettingsConfigDict(extra="ignore")

    app_env: Literal["local"] = "local"
    app_timezone: str = "America/Merida"
    demo_owner_id: Literal["efren"] = OWNER_ID
    database_url: str = "postgresql+psycopg://efren_bot:local_demo_only@127.0.0.1:55432/efren_bot"
    worker_poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=60, allow_inf_nan=False)
    claude_bridge_enabled: bool = False
    claude_bridge_token_file: str = "/run/efren-bot-bridge/token"
    claude_bridge_profile_file: str = "/run/efren-bot-bridge/profile.json"
    claude_bridge_api_url: Literal["http://127.0.0.1:8000"] = "http://127.0.0.1:8000"
    # Factory control plane. Defaults are fully mocked: no executor binary, no real effects.
    factory_projects_file: str = ""
    factory_profiles_dir: str = ""
    factory_scraft_ops_bin: str = "scraft-ops"
    factory_state_dir: str = ""
    factory_agent_executor: Literal["", "fake", "claude", "opencode"] = ""
    factory_agent_fallbacks: list[Literal["opencode", "claude"]] | None = Field(
        default=None, max_length=1
    )
    factory_gateway: Literal["recording", "real"] = "recording"
    factory_effect_ttl_hours: int = Field(default=24, ge=1, le=720)
    # Notion (official API). Both empty means Notion is not wired: no adapter, no gateway.
    factory_notion_token: str = ""
    factory_notion_database_id: str = ""
    factory_notion_status_property: str = "Status"
    # WhatsApp Cloud API webhook. Empty means the webhook answers 503 (fail closed).
    factory_whatsapp_app_secret: str = ""
    factory_whatsapp_verify_token: str = ""

    @field_validator("app_timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValueError("APP_TIMEZONE must name an IANA timezone") from exc
        return value

    @field_validator("database_url")
    @classmethod
    def local_postgres(cls, value: str) -> str:
        try:
            url = make_url(value)
            valid = (
                url.drivername == "postgresql+psycopg"
                and url.host in {"127.0.0.1", "localhost", "::1", "db", "test-db"}
                and bool(url.database)
                and not url.query  # no host/service overrides via libpq query arguments
            )
        except Exception as exc:
            raise ValueError("DATABASE_URL must be local PostgreSQL with psycopg") from exc
        if not valid:
            raise ValueError("DATABASE_URL must be local PostgreSQL with psycopg")
        return value
