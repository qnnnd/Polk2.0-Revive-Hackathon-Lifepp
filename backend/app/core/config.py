"""
Life++ — Application Configuration
Pydantic Settings for 12-factor config from environment variables.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Life++"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+asyncpg://lifeplusplus:lifeplusplus@localhost:5432/lifeplusplus"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "dev-secret-change-in-production"
    JWT_SECRET: str = "dev-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    EMBEDDING_MODEL: str = "text-embedding-3-small"
    MAX_TOKENS: int = 4096

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    API_V1_PREFIX: str = "/api/v1"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
