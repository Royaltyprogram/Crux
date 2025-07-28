"""
Main FastAPI application factory.
"""
from contextlib import asynccontextmanager
from datetime import datetime

import redis.asyncio as redis
from celery import Celery
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import dependencies
from app.api.routers import jobs, solve
from app.api.routers import settings as settings_router
from app.core.providers.factory import create_provider
from app.schemas.response import ErrorResponse, HealthResponse
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{__version__}")
    
    # Initialize Redis
    try:
        dependencies.redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=False,  # We'll handle decoding
        )
        await dependencies.redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise
    
    # Initialize Celery
    dependencies.celery_app = Celery(
        settings.app_name,
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    logger.info("Celery app initialized")
    
    # Test provider initialization
    try:
        provider = create_provider()
        logger.info(f"Provider initialized: {provider.__class__.__name__}")
    except Exception as e:
        logger.warning(f"Provider initialization test failed: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    # Close Redis
    if dependencies.redis_client:
        await dependencies.redis_client.close()
        logger.info("Redis connection closed")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI app instance
    """
    app = FastAPI(
        title=settings.app_name,
        description="Production-ready FastAPI service implementing Crux agent with Self-Evolve algorithm",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )
    
    # Add CORS middleware
    cors_origins = settings.cors_origins.split(",") if settings.cors_origins else ["http://localhost:3000"]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Add custom exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle uncaught exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        
        # Get request ID if available
        request_id = getattr(request.state, "request_id", None)
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="InternalServerError",
                message="An unexpected error occurred",
                detail=str(exc) if settings.debug else None,
                request_id=request_id,
            ).model_dump(),
        )
    
    # Include routers
    app.include_router(solve.router, prefix=settings.api_v1_str)
    app.include_router(jobs.router, prefix=settings.api_v1_str)
    app.include_router(settings_router.router, prefix=settings.api_v1_str)
    
    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint."""
        return {
            "name": settings.app_name,
            "version": __version__,
            "status": "running",
            "docs": "/docs" if settings.debug else None,
        }
    
    # Health check endpoint
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check():
        """
        Health check endpoint.
        
        Checks the status of all dependencies and returns overall health.
        """
        health = HealthResponse(
            status="healthy",
            version=__version__,
            timestamp=datetime.utcnow(),
            providers={},
            redis=False,
        )
        
        # Check Redis
        try:
            if dependencies.redis_client:
                await dependencies.redis_client.ping()
                health.redis = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            health.status = "degraded"
        
        # Check providers
        for provider_name in ["openai", "openrouter"]:
            try:
                provider = create_provider(provider_name=provider_name)
                health.providers[provider_name] = True
            except Exception as e:
                logger.error(f"Provider {provider_name} health check failed: {e}")
                health.providers[provider_name] = False
                health.status = "degraded"
        
        return health
    
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add request ID to all requests."""
        # Generate request ID if not present
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            import uuid
            request_id = f"req_{uuid.uuid4().hex[:12]}"
        
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response
        response.headers["X-Request-ID"] = request_id
        
        return response
    
    return app


# For development: Create app instance
# In production, use: uvicorn app.main:create_app --factory
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    ) 