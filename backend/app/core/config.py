import os
from dataclasses import dataclass


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Life++ API")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", "backend/data/lifepp.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")


settings = Settings()
