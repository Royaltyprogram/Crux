"""
Dependency injection for FastAPI endpoints.
"""
import uuid
from typing import Annotated, Optional

import redis.asyncio as redis
from celery import Celery
from fastapi import Request

from app.core.providers.factory import create_provider
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Global instances (initialized in lifespan)
redis_client: Optional[redis.Redis] = None
celery_app: Optional[Celery] = None


async def get_redis() -> redis.Redis:
    """Get Redis client."""
    if not redis_client:
        raise RuntimeError("Redis client not initialized")
    return redis_client


async def get_celery() -> Celery:
    """Get Celery app."""
    if not celery_app:
        raise RuntimeError("Celery app not initialized")
    return celery_app


async def get_request_id(
    request: Request,
) -> str:
    """Get or generate request ID."""
    # Check if already set in request state
    if hasattr(request.state, "request_id"):
        return request.state.request_id
    
    # Generate new ID
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    return request_id


async def get_provider(
    provider_name: Optional[str] = None,
):
    """
    Get LLM provider instance.
    
    Args:
        provider_name: Optional provider override
        
    Returns:
        Provider instance
    """
    try:
        return create_provider(provider_name=provider_name)
    except Exception as e:
        logger.error(f"Failed to create provider: {e}")
        raise