import os
from typing import Optional


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/taskmanager")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-key")
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "taskmanager")
    ACCESS_TTL_MIN: int = int(os.getenv("ACCESS_TTL_MIN", "15"))
    REFRESH_TTL_DAYS: int = int(os.getenv("REFRESH_TTL_DAYS", "7"))
    OTP_TTL_MIN: int = int(os.getenv("OTP_TTL_MIN", "10"))
    
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    PUBLIC_URL: str = os.getenv("PUBLIC_URL", "http://localhost:3000")
    TENANT_SUBDOMAIN_BASE: str = os.getenv("TENANT_SUBDOMAIN_BASE", "example.local")


settings = Settings()