"""Configuration management using Pydantic settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # xAI (Grok) API
    xai_api_key: str = ""
    xai_base_url: str = "https://api.x.ai/v1"

    # Gmail OAuth
    gmail_client_id: str = ""
    gmail_client_secret: str = ""

    # Cache settings
    cache_ttl_days: int = 7
    cache_db_path: Path = Path("data/cache.db")

    # Rate limiting
    rate_limit_requests_per_second: float = 2.0
    rate_limit_domain_delay_seconds: float = 2.0

    # Scraping settings
    scrape_timeout_seconds: float = 30.0
    max_article_content_chars: int = 2000
    min_article_words: int = 100

    # Gmail token path
    gmail_token_path: Path = Path("data/gmail_token.json")
    gmail_credentials_path: Path = Path("data/credentials.json")

    # AI settings (Grok models)
    ai_model: str = "grok-3-latest"
    ai_model_fast: str = "grok-3-fast-latest"  # Used for quick tasks like blog finding
    ai_model_dry_run: str = "grok-3-fast-latest"
    ai_max_tokens: int = 256

    # Output settings
    dry_run_output_dir: Path = Path("output/dry_run_results")


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
