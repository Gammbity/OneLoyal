import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OneLoyal API"
    app_version: str = "0.1.0"
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:5173"]
    )

    database_url: str = "postgresql+asyncpg://oneloyal:oneloyal@localhost:5432/oneloyal"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    secret_key: str = "change-me-in-local-development"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    encryption_key: str = "change-me-in-local-development"
    log_level: str = "INFO"
    pagination_default_limit: int = 50
    pagination_max_limit: int = 200
    password_hash_time_cost: int = 3
    password_hash_memory_cost: int = 65536
    password_hash_parallelism: int = 4
    password_min_length: int = 8
    portal_access_token_expire_hours: int = 12
    magic_link_default_expire_days: int = 30
    portal_base_url: str | None = None
    import_max_rows: int = 10000
    import_preview_error_limit: int = 50
    import_allowed_extensions: list[str] = Field(default_factory=lambda: ["csv"])
    moysklad_base_url: str = "https://api.moysklad.ru/api/remap/1.2"
    moysklad_timeout_seconds: float = 15.0
    moysklad_page_limit: int = Field(default=1000, ge=1, le=1000)
    moysklad_max_retries: int = Field(default=2, ge=0)
    sync_lock_ttl_seconds: int = 1800
    sync_task_time_limit_seconds: int = 3600
    sync_task_soft_time_limit_seconds: int = 3300
    sync_enqueue_tasks: bool = True

    # Operational Recovery Settings
    sync_queued_timeout_minutes: int = 10
    sync_running_timeout_minutes: int = 60
    notification_pending_timeout_minutes: int = 60
    notification_max_attempts: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            false_values = {"release", "production", "prod", "false", "0", "no", "off"}
            if normalized in false_values:
                return False
            if normalized in {"debug", "development", "dev", "true", "1", "yes", "on"}:
                return True
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        return cls._parse_string_list(value)

    @field_validator("import_allowed_extensions", mode="before")
    @classmethod
    def parse_import_allowed_extensions(cls, value: Any) -> Any:
        return cls._parse_string_list(value)

    @classmethod
    def _parse_string_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
