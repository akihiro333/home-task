from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models.user import User
from ..models.organization import Organization
from ..models.membership import Membership
from ..models.otp_code import OtpCode
from ..models.refresh_token import RefreshToken
from ..services.auth import AuthService
from ..schemas.auth import (
    RegisterRequest, LoginRequest, VerifyOtpRequest, GoogleLoginRequest,
    LoginResponse, TokenResponse, UserResponse, OrganizationResponse
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    # Check if organization subdomain exists
    result = await db.execute(
        select(Organization).where(Organization.subdomain == request.subdomain)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subdomain already exists"
        )

    # Check if user email exists
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create organization
    org = Organization(
        name=request.organization_name,
        subdomain=request.subdomain
    )
    db.add(org)
    await db.flush()

    # Create user
    user = User(
        email=request.email,
        password_hash=AuthService.hash_password(request.password)
    )
    db.add(user)
    await db.flush()

    # Create admin membership
    membership = Membership(
        user_id=user.id,
        org_id=org.id,
        role="admin"
    )
    db.add(membership)
    await db.commit()

    # Generate tokens
    access_token = AuthService.create_access_token({
        "user_id": user.id,
        "org_id": org.id,
        "role": "admin"
    })
    
    refresh_token_str = AuthService.create_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        org_id=org.id,
        token_hash=AuthService.hash_token(refresh_token_str),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TTL_DAYS)
    )
    db.add(refresh_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=settings.ACCESS_TTL_MIN * 60
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    # Rate limiting
    rate_key = f"login_attempts:{request.email}"
    if not await AuthService.check_rate_limit(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts"
        )

    # Find user
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not user.password_hash or not AuthService.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Generate and store OTP
    otp_code = AuthService.generate_otp()
    otp = OtpCode(
        user_id=user.id,
        code=otp_code,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.OTP_TTL_MIN)
    )
    db.add(otp)
    await db.commit()

    # In production, send OTP via email/SMS
    # For demo, we'll log it
    print(f"OTP for {user.email}: {otp_code}")

    return LoginResponse(
        otp_required=True,
        message="OTP sent to your email"
    )


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    request: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db)
):
    # Find user
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # Find valid OTP
    result = await db.execute(
        select(OtpCode).where(
            OtpCode.user_id == user.id,
            OtpCode.code == request.code,
            OtpCode.expires_at > datetime.utcnow(),
            OtpCode.consumed.is_(None)
        )
    )
    otp = result.scalar_one_or_none()
    
    if not otp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired OTP"
        )

    # Mark OTP as consumed
    otp.consumed = datetime.utcnow()

    # Get user's first organization (for simplicity)
    result = await db.execute(
        select(Membership).where(Membership.user_id == user.id)
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no organization membership"
        )

    # Generate tokens
    access_token = AuthService.create_access_token({
        "user_id": user.id,
        "org_id": membership.org_id,
        "role": membership.role
    })
    
    refresh_token_str = AuthService.create_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        org_id=membership.org_id,
        token_hash=AuthService.hash_token(refresh_token_str),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TTL_DAYS)
    )
    db.add(refresh_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=settings.ACCESS_TTL_MIN * 60
    )


@router.post("/login/google", response_model=TokenResponse)
async def google_login(
    request: GoogleLoginRequest,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    # Verify Google token
    user_info = await AuthService.verify_google_token(request.id_token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )

    # Resolve organization from request
    from ..middleware.tenant import TenantMiddleware
    org = await TenantMiddleware.resolve_organization(req, db)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context required"
        )

    # Find or create user
    result = await db.execute(
        select(User).where(User.email == user_info["email"])
    )
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(email=user_info["email"])
        db.add(user)
        await db.flush()

    # Find or create membership
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.org_id == org.id
        )
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        membership = Membership(
            user_id=user.id,
            org_id=org.id,
            role="member"
        )
        db.add(membership)

    await db.commit()

    # Generate tokens
    access_token = AuthService.create_access_token({
        "user_id": user.id,
        "org_id": org.id,
        "role": membership.role
    })
    
    refresh_token_str = AuthService.create_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        org_id=org.id,
        token_hash=AuthService.hash_token(refresh_token_str),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TTL_DAYS)
    )
    db.add(refresh_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=settings.ACCESS_TTL_MIN * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    token_hash = AuthService.hash_token(refresh_token)
    
    # Find valid refresh token
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.expires_at > datetime.utcnow(),
            RefreshToken.revoked == False
        )
    )
    token_record = result.scalar_one_or_none()
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user and membership
    result = await db.execute(
        select(User, Membership).join(
            Membership, User.id == Membership.user_id
        ).where(
            User.id == token_record.user_id,
            Membership.org_id == token_record.org_id
        )
    )
    user_membership = result.first()
    
    if not user_membership:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User or membership not found"
        )
    
    user, membership = user_membership

    # Revoke old token
    token_record.revoked = True

    # Generate new tokens
    access_token = AuthService.create_access_token({
        "user_id": user.id,
        "org_id": membership.org_id,
        "role": membership.role
    })
    
    new_refresh_token_str = AuthService.create_refresh_token()
    new_refresh_token = RefreshToken(
        user_id=user.id,
        org_id=membership.org_id,
        token_hash=AuthService.hash_token(new_refresh_token_str),
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TTL_DAYS)
    )
    db.add(new_refresh_token)
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token_str,
        expires_in=settings.ACCESS_TTL_MIN * 60
    )


@router.post("/logout")
async def logout(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    token_hash = AuthService.hash_token(refresh_token)
    
    # Find and revoke refresh token
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    token_record = result.scalar_one_or_none()
    
    if token_record:
        token_record.revoked = True
        await db.commit()

    return {"message": "Logged out successfully"}