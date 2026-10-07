import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("DB_PATH", "data/opportunities.db")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    telegram_token: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = os.getenv("TELEGRAM_CHAT_ID")
    imap_host: str = os.getenv("IMAP_HOST", "imap.gmail.com")
    imap_port: int = int(os.getenv("IMAP_PORT", "993"))
    imap_username: str | None = os.getenv("IMAP_USERNAME")
    imap_password: str | None = os.getenv("IMAP_PASSWORD")
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"
