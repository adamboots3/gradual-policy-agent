from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLICY_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    chat_provider: str = ""
    chat_model: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_extra_body: dict = Field(default_factory=dict)
    embedding_provider: str = ""
    embedding_model: str = ""
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_batch_size: int = Field(default=10, ge=1, le=100)
    max_search_calls: int = Field(default=3, ge=1, le=5)
    retrieval_mode: Literal["keyword", "hybrid"] = "keyword"
    history_turns: int = Field(default=6, ge=1, le=20)

    @property
    def database(self) -> Path:
        return self.data_dir / "policies.sqlite3"
