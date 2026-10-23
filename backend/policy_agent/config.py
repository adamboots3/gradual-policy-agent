from typing import Annotated

from pydantic import Field, StringConstraints
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLICY_", env_file=".env", extra="ignore")

    chat_provider: str = ""
    chat_model: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_extra_body: dict = Field(default_factory=dict)
    # 0: model profile if available, otherwise a documented 32,768-token fallback.
    chat_context_window_tokens: int = Field(default=0, ge=0)
    chat_max_output_tokens: int = Field(default=2048, ge=1)
    chat_context_margin_tokens: int = Field(default=512, ge=0)
    github_ref: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ] = "HEAD"
    github_token: str = ""
    max_policy_reads: int = Field(default=6, ge=1, le=12)
    read_max_chars: int = Field(default=24000, ge=1000, le=64000)
