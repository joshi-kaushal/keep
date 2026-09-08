import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://keep:keep@db:5432/keep",
    )
    odyssey_url: str = os.getenv("ODYSSEY_URL", "http://host.docker.internal:3000")
    odyssey_api_key: str = os.getenv("ODYSSEY_API_KEY", "")
    notes_webhook_secret: str = os.getenv("NOTES_WEBHOOK_SECRET", "")
    extension_token: str = os.getenv("EXTENSION_TOKEN", "")
    esp32_token: str = os.getenv("ESP32_TOKEN", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    port: int = int(os.getenv("PORT", "3005"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
