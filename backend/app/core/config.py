"""Runtime configuration helpers for DevSage."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "DevSage API"
    environment: str = "development"
    sample_data_root: str = "sample-data"
    auth_enabled: bool = False
    auth_secret_env: str = "DEVSAGE_AUTH_SECRET"
    auth_users_file: str = ""
    auth_token_ttl_seconds: int = 3600
    cache_mode: str = "memory"
    redis_url: str = ""
    embedding_provider: str = "hash"
    embedding_api_url: str = ""
    embedding_model: str = ""
    external_issue_write_enabled: bool = False


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def get_settings() -> Settings:
    """Read non-secret runtime settings from environment variables."""

    return Settings(
        environment=os.getenv("DEVSAGE_ENVIRONMENT", "development"),
        sample_data_root=os.getenv("SAMPLE_DATA_ROOT", "sample-data"),
        auth_enabled=_env_bool("DEVSAGE_AUTH_ENABLED"),
        auth_secret_env=os.getenv("DEVSAGE_AUTH_SECRET_ENV", "DEVSAGE_AUTH_SECRET").strip()
        or "DEVSAGE_AUTH_SECRET",
        auth_users_file=os.getenv("DEVSAGE_AUTH_USERS_FILE", "").strip(),
        auth_token_ttl_seconds=_env_int("DEVSAGE_AUTH_TOKEN_TTL", 3600),
        cache_mode=os.getenv("DEVSAGE_CACHE", "memory").strip().lower() or "memory",
        redis_url=os.getenv("DEVSAGE_REDIS_URL", "").strip(),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "hash").strip().lower() or "hash",
        embedding_api_url=os.getenv("EMBEDDING_API_URL", "").strip(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "").strip(),
        external_issue_write_enabled=_env_bool("DEVSAGE_EXTERNAL_ISSUE_WRITE_ENABLED"),
    )
