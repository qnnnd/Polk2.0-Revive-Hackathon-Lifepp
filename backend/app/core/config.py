"""
Life++ — Application Configuration
Pydantic Settings for 12-factor config from environment variables.
"""
from __future__ import annotations

import os
from typing import List, Optional

from pydantic_settings import BaseSettings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Settings(BaseSettings):
    APP_NAME: str = "Life++"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'lifeplusplus.db')}"

    SECRET_KEY: str = "dev-secret-change-in-production"
    JWT_SECRET: str = "dev-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 384
    MAX_TOKENS: int = 4096

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    API_V1_PREFIX: str = "/api/v1"

    # Revive testnet
    REVIVE_RPC_URL: str = "http://127.0.0.1:8545"
    DEPLOYER_PRIVATE_KEY: str = ""
    CONTRACT_AGENT_REGISTRY: str = ""
    CONTRACT_TASK_MARKET: str = ""
    CONTRACT_REPUTATION: str = ""
    CONTRACT_COG_TOKEN: str = ""

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
