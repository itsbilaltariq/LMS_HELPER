"""FastAPI Application entry point for NUST LMS Helper."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.auth import auth_router
from app.config import get_settings
from app.jobs import jobs_router
from app.logging import setup_logging
from app.security import SecurityHeadersMiddleware

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan initialization."""
    settings = get_settings()
    logger.info(f"Starting NUST LMS Helper API in {settings.APP_ENV} mode")
    logger.info(f"Target NUST LMS Base URL: {settings.LMS_BASE_URL}")
    logger.info(f"LLM Engine: Groq ({settings.GROQ_MODEL})")
    yield
    logger.info("Shutting down NUST LMS Helper API")


app = FastAPI(
    title="NUST LMS Lab Helper API",
    version="0.1.0",
    lifespan=lifespan,
)

# Apply ASVS Security Headers Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Attach Modular Routers
app.include_router(auth_router)
app.include_router(jobs_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "lms": "lms.nust.edu.pk",
        "llm": "groq",
    }
