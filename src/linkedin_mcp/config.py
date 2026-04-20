from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    linkedin_li_at: str = ""
    linkedin_jsessionid: str = ""
    linkedin_email: str = ""
    linkedin_password: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    linkedin_mcp_db: Path = Path("./data/linkedin_mcp.sqlite")

    max_connection_requests_per_day: int = 80
    max_messages_per_day: int = 120
    max_profile_views_per_day: int = 200
    min_action_delay_seconds: int = 8
    max_action_delay_seconds: int = 25

    log_level: str = "INFO"

    # Outbound webhook for signal/campaign notifications (Slack-style JSON).
    notify_webhook_url: str = ""

    def ensure_paths(self) -> None:
        self.linkedin_mcp_db.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_paths()
