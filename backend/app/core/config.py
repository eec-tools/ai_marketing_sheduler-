from pydantic_settings import BaseSettings
from typing import List
import secrets


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Social Media Manager"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str = "k7W1mX9FqQvD4jR8sT2uV6wY0zA3bC5eG8hJ1kM4nP7="

    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_social.db"
    HF_TOKEN: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "ai-social-media"

    # CORS
    FRONTEND_URL: str = "http://localhost:5173"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"]

    # LinkedIn
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/linkedin/callback"
    LINKEDIN_ORG_ID: str = ""

    # Instagram
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    INSTAGRAM_REDIRECT_URI: str = "http://localhost:8000/api/v1/social/instagram/callback"

    # Scheduler
    KEY_COOLDOWN_SECONDS: int = 60
    MAX_IMAGE_RETRIES: int = 3
    SCHEDULER_INTERVAL_SECONDS: int = 60

    # AI Workflow APIs
    WINDSOR_API_KEY: str | None = None
    HIGGSFIELD_API_KEY: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
