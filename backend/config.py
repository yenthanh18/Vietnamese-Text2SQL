from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = "localhost"
    db_port: int = Field(default=5432, ge=1, le=65535)
    db_name: str = "student_management_demo"
    db_user: str = "postgres"
    db_password: SecretStr = SecretStr("")
    model_device: str = Field(default="cpu", pattern=r"^(cpu|cuda(?::\d+)?)$")
    base_model: str = "Qwen/Qwen2.5-Coder-3B-Instruct"
    adapter_path: Path = Path("model/e2_qlora_dew_final")
    spider_db_path: Path = Path("database/spider")
    spider_execute_enabled: bool = True  # Local development only; disable in deployment.


@lru_cache
def get_settings() -> Settings:
    return Settings()
