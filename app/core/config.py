from pathlib import Path
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Configuration for mini-menu-api-gateway."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Server Configuration
    PORT: int = Field(default=8000, description="Gateway listening port")
    ENVIRONMENT: str = Field(default="production", description="Environment mode")
    PROJECT_NAME: str = "mini-menu-api-gateway"

    # Downstream Service URLs
    AUTH_SERVICE_URL: str = Field(
        default="http://127.0.0.1:8001",
        description="Downstream mini-menu-auth-service base URL",
    )
    CATALOG_SERVICE_URL: str = Field(
        default="http://127.0.0.1:8002",
        description="Downstream mini-menu-catalog-service base URL",
    )
    ORDER_SERVICE_URL: str = Field(
        default="http://127.0.0.1:8003",
        description="Downstream mini-menu-order-service base URL",
    )

    # Security & CORS
    CORS_ORIGINS: str = Field(
        default="*",
        description="Comma-separated allowed CORS origins or *",
    )

    # In-memory Rate Limiter
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        default=120,
        description="Maximum allowed requests per minute per client IP",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS into a clean list of origins."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
