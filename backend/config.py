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

    copart_username: str = ""
    copart_password: str = ""
    iaai_username: str = ""
    iaai_password: str = ""
    amerpol_username: str = ""
    amerpol_password: str = ""
    scraperapi_key: str = ""


config = Config()
ROOT = Path(__file__).resolve().parent.parent
