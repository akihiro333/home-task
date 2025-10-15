import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, OtpCode
from app.services.auth import AuthService


@pytest.mark.asyncio
async def test_otp_flow(client: AsyncClient, db_session: AsyncSession):
    """Test OTP authentication flow."""
    
    # Register a new organization and user
    register_data = {
        "organization_name": "Test Company",
        "subdomain": "testco",
        "email": "admin@testco.com",
        "password": "password123"
    }
    
    response = await client.post("/auth/register", json=register_data)
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    
    # Test login (should require OTP)
    login_data = {
        "email": "admin@testco.com",
        "password": "password123"
    }
    
    response = await client.post("/auth/login", json=login_data)
    assert response.status_code == 200
    data = response.json()
    assert data["otp_required"] is True
    
    # Get the OTP from database (in real app, this would be sent via email)
    from sqlalchemy import select
    result = await db_session.execute(
        select(User).where(User.email == "admin@testco.com")
    )
    user = result.scalar_one()
    
    result = await db_session.execute(
        select(OtpCode).where(OtpCode.user_id == user.id).order_by(OtpCode.id.desc())
    )
    otp = result.scalar_one()
    
    # Verify OTP
    verify_data = {
        "email": "admin@testco.com",
        "code": otp.code
    }
    
    response = await client.post("/auth/verify-otp", json=verify_data)
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    
    # Test invalid OTP
    verify_data = {
        "email": "admin@testco.com",
        "code": "000000"
    }
    
    response = await client.post("/auth/verify-otp", json=verify_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_google_mock_login(client: AsyncClient):
    """Test Google OAuth mock login."""
    
    # First create an organization to login to
    register_data = {
        "organization_name": "Test Company",
        "subdomain": "testco",
        "email": "admin@testco.com",
        "password": "password123"
    }
    
    await client.post("/auth/register", json=register_data)
    
    # Test mock Google login
    google_data = {
        "id_token": "MOCK_ID_TOKEN"
    }
    
    response = await client.post(
        "/auth/login/google",
        json=google_data,
        headers={"Host": "testco.example.local"}
    )
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens


@pytest.mark.asyncio
async def test_token_refresh(client: AsyncClient):
    """Test refresh token functionality."""
    
    # Register and get initial tokens
    register_data = {
        "organization_name": "Test Company",
        "subdomain": "testco",
        "email": "admin@testco.com",
        "password": "password123"
    }
    
    response = await client.post("/auth/register", json=register_data)
    tokens = response.json()
    refresh_token = tokens["refresh_token"]
    
    # Use refresh token to get new tokens
    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    new_tokens = response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != refresh_token  # Should be rotated
    
    # Old refresh token should be invalid
    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401