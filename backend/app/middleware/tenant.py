from typing import Optional
from fastapi import Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.organization import Organization
from ..services.auth import AuthService


class TenantMiddleware:
    @staticmethod
    async def resolve_organization(request: Request, db: AsyncSession) -> Optional[Organization]:
        """Resolve organization from subdomain or JWT token."""
        
        # Try subdomain first
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            if subdomain and subdomain != "www":
                result = await db.execute(
                    select(Organization).where(Organization.subdomain == subdomain)
                )
                org = result.scalar_one_or_none()
                if org:
                    return org

        # Fallback to JWT org_id
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = AuthService.verify_token(token)
            if payload and "org_id" in payload:
                result = await db.execute(
                    select(Organization).where(Organization.id == payload["org_id"])
                )
                return result.scalar_one_or_none()

        return None

    @staticmethod
    def get_current_org(request: Request) -> Organization:
        """Get current organization from request state."""
        org = getattr(request.state, "current_org", None)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization context not found"
            )
        return org