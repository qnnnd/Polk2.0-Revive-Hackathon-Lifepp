"""
Life++ — Application Configuration
Pydantic Settings for 12-factor config from environment variables.
"""
from __future__ import annotations

from typing import Any, List, Optional

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

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002"

    PORT: int = 8002  # Backend server port (default 8002 to avoid conflict with 8000/8001)

    API_V1_PREFIX: str = "/api/v1"

    # Revive testnet (required for 13.4 compliance)
    REVIVE_RPC_URL: Optional[str] = None
    AGENT_REGISTRY_ADDRESS: Optional[str] = None
    TASK_MARKET_ADDRESS: Optional[str] = None
    REPUTATION_ADDRESS: Optional[str] = None
    REVIVE_DEPLOYER_PRIVATE_KEY: Optional[str] = None  # for backend-signed txs (agent register, marketplace)

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def revive_configured(self) -> bool:
        return bool(
            self.REVIVE_RPC_URL
            and self.AGENT_REGISTRY_ADDRESS
            and self.TASK_MARKET_ADDRESS
            and self.REPUTATION_ADDRESS
        )

    def model_post_init(self, __context: Any) -> None:
        """
        Enforce local-node-only usage in development.
        In development, REVIVE_RPC_URL (if set) must point to a local Revive node
        and must not be configured to a remote testnet endpoint.
        """
        if self.is_development and self.REVIVE_RPC_URL:
            url = self.REVIVE_RPC_URL.strip()
            if not (
                url.startswith("http://127.0.0.1:8545")
                or url.startswith("http://localhost:8545")
            ):
                raise ValueError(
                    "In development, REVIVE_RPC_URL must point to a local Revive node "
                    "(http://127.0.0.1:8545 or http://localhost:8545). "
                    "Do not use remote Revive RPC in local environment."
                )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # ignore legacy keys e.g. COG_TOKEN_ADDRESS


settings = Settings()
