from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..models.user import User
from ..models.membership import Membership
from ..services.auth import AuthService


class AuthMiddleware:
    @staticmethod
    async def get_current_user(
        request: Request,
        db: AsyncSession = Depends(get_db)
    ) -> Optional[User]:
        """Get current user from JWT token."""
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]
        payload = AuthService.verify_token(token)
        if not payload or "user_id" not in payload:
            return None

        result = await db.execute(
            select(User).where(User.id == payload["user_id"])
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def require_auth(
        request: Request,
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """Require authentication and return current user."""
        user = await AuthMiddleware.get_current_user(request, db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        return user

    @staticmethod
    async def require_admin(
        request: Request,
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """Require admin role in current organization."""
        user = await AuthMiddleware.require_auth(request, db)
        
        # Get current org from request state
        current_org = getattr(request.state, "current_org", None)
        if not current_org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization context required"
            )

        # Check if user is admin in this org
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.org_id == current_org.id,
                Membership.role == "admin"
            )
        )
        membership = result.scalar_one_or_none()
        
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        return user

    @staticmethod
    async def get_user_membership(
        user: User,
        org_id: int,
        db: AsyncSession
    ) -> Optional[Membership]:
        """Get user's membership in organization."""
        result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.org_id == org_id
            )
        )
        return result.scalar_one_or_none()