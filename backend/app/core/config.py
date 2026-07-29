"""阶段 0 的轻量配置入口，后续可替换为 pydantic-settings。"""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "DevSage API"
    environment: str = "development"
    sample_data_root: str = "sample-data"


def get_settings() -> Settings:
    """Read only non-secret local settings from environment variables."""

    return Settings(
        environment=os.getenv("DEVSAGE_ENVIRONMENT", "development"),
        sample_data_root=os.getenv("SAMPLE_DATA_ROOT", "sample-data"),
    )

