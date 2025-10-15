import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from google.auth.transport import requests
from google.oauth2 import id_token
import httpx

from ..config import settings
from ..redis_client import redis_client

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def generate_otp() -> str:
        return f"{secrets.randbelow(1000000):06d}"

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def create_access_token(data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TTL_MIN)
        to_encode.update({"exp": expire, "iss": settings.JWT_ISSUER})
        return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")

    @staticmethod
    def create_refresh_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            return payload
        except jwt.PyJWTError:
            return None

    @staticmethod
    async def check_rate_limit(key: str, limit: int = 5, window: int = 300) -> bool:
        """Check if rate limit is exceeded. Returns True if allowed."""
        current = await redis_client.get(key)
        if current is None:
            await redis_client.setex(key, window, 1)
            return True
        
        if int(current) >= limit:
            return False
        
        await redis_client.incr(key)
        return True

    @staticmethod
    async def verify_google_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify Google ID token. Returns user info if valid."""
        if not settings.GOOGLE_CLIENT_ID:
            # Mock mode for development
            if token == "MOCK_ID_TOKEN":
                return {
                    "email": "test@example.com",
                    "name": "Test User",
                    "sub": "mock_google_id"
                }
            return None

        try:
            idinfo = id_token.verify_oauth2_token(
                token, requests.Request(), settings.GOOGLE_CLIENT_ID
            )
            return idinfo
        except ValueError:
            return None