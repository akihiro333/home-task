import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .middleware.tenant import TenantMiddleware
from .routers import auth, tasks, health, websocket

# Configure structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)
        return json.dumps(log_entry)

# Apply JSON formatter to root logger
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.getLogger().handlers = [handler]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Starting TaskManager API")
    yield
    # Shutdown
    logging.info("Shutting down TaskManager API")


app = FastAPI(
    title="TaskManager API",
    description="Multi-tenant SaaS task management system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """Middleware to resolve and inject organization context."""
    # Skip tenant resolution for health and auth endpoints
    if request.url.path in ["/health", "/docs", "/openapi.json"] or request.url.path.startswith("/auth"):
        response = await call_next(request)
        return response
    
    # Resolve organization for other endpoints
    async with AsyncSessionLocal() as db:
        try:
            org = await TenantMiddleware.resolve_organization(request, db)
            request.state.current_org = org
        except Exception as e:
            logging.error(f"Tenant resolution failed: {e}")
            request.state.current_org = None
    
    response = await call_next(request)
    return response


# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {"message": "TaskManager API", "version": "1.0.0"}


# Import AsyncSessionLocal here to avoid circular imports
from .database import AsyncSessionLocal