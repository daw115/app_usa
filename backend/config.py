from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    gmail_client_secrets: str = "./gmail_client_secret.json"
    gmail_token_path: str = "./gmail_token.json"
    public_form_base_url: str = "http://localhost:8000"
    db_path: str = "./app.db"

    email_provider: str = "gmail"
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    copart_username: str = ""
    copart_password: str = ""
    iaai_username: str = ""
    iaai_password: str = ""
    amerpol_username: str = ""
    amerpol_password: str = ""
    scraperapi_key: str = ""

    # Resource limits
    playwright_timeout: int = 30000  # ms per page navigation
    scraper_page_timeout: int = 15000  # ms waiting for selectors
    ai_timeout_seconds: int = 60  # seconds per AI analysis
    ai_max_photos: int = 6  # max photos per listing

    # Scraper rate limit (per source, per day)
    scraper_daily_limit: int = 30

    # Observability
    sentry_dsn: str = ""
    environment: str = "development"  # set to "production" on Railway
    log_format: str = "text"  # "text" for local, "json" for prod (Railway)


config = Config()
ROOT = Path(__file__).resolve().parent.parent
