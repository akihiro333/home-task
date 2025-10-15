from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..database import get_db
from ..redis_client import redis_client
from ..celery_app import celery_app

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint that reports status of all services."""
    health_status = {
        "app": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "celery": "unknown"
    }
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        health_status["database"] = "healthy"
    except Exception as e:
        health_status["database"] = f"unhealthy: {str(e)}"
    
    # Check Redis
    try:
        await redis_client.ping()
        health_status["redis"] = "healthy"
    except Exception as e:
        health_status["redis"] = f"unhealthy: {str(e)}"
    
    # Check Celery
    try:
        # Get active workers
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        if active_workers:
            health_status["celery"] = "healthy"
        else:
            health_status["celery"] = "no active workers"
    except Exception as e:
        health_status["celery"] = f"unhealthy: {str(e)}"
    
    return health_status