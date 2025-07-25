"""
Solve endpoints for basic and enhanced modes.
"""
import json
import time
import uuid
from datetime import datetime
from typing import Annotated

import redis.asyncio as redis
from celery import Celery
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import (
    get_celery,
    get_provider,
    get_redis,
    get_request_id,
)
from app.core.orchestrators.basic import BasicRunner
from app.core.orchestrators.enhanced import EnhancedRunner
from app.core.providers.base import BaseProvider
from app.schemas.request import BasicSolveRequest, EnhancedSolveRequest
from app.schemas.response import AsyncJobResponse, JobStatus, SolutionResponse
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/solve",
    tags=["solve"],
)


@router.post("/basic", response_model=SolutionResponse | AsyncJobResponse)
async def solve_basic(
    request: BasicSolveRequest,
    provider: Annotated[BaseProvider, Depends(get_provider)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    celery_app: Annotated[Celery, Depends(get_celery)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> SolutionResponse | AsyncJobResponse:
    """
    Solve a problem using basic mode.
    
    Basic mode uses a single Self-Evolve loop with:
    - Generator: General-purpose LLM
    - Evaluator: Quality assessment agent
    - Refiner: Prompt improvement agent
    
    If `async_mode` is true, returns a job ID for checking status later.
    """
    logger.info(f"Basic solve request: {request.question[:100]}... [request_id={request_id}]")
    
    if request.async_mode:
        # Submit to Celery
        job_id = str(uuid.uuid4())
        
        # Store initial job info in Redis
        job_data = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "created_at": datetime.now(datetime.UTC).isoformat(),
            "request": json.dumps(request.model_dump()),
            "mode": "basic",
        }
        await redis_client.hset(f"job:{job_id}", mapping=job_data)
        await redis_client.expire(f"job:{job_id}", 3600)  # 1 hour TTL
        
        # Submit task to Celery
        celery_app.send_task(
            "app.worker.solve_basic_task",
            args=[job_id, request.model_dump()],
            task_id=job_id,
        )
        
        return AsyncJobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(datetime.UTC),
            message="Job submitted successfully",
        )
    
    # Synchronous execution
    try:
        start_time = time.time()
        
        # Create runner
        runner = BasicRunner(
            provider=provider,
            max_iters=request.n_iters or settings.max_iters,
        )
        
        # Solve
        solution = await runner.solve(
            question=request.question,
            context=request.context,
            constraints=request.constraints,
            metadata={"request_id": request_id},
        )
        
        processing_time = time.time() - start_time
        
        return SolutionResponse(
            output=solution.output,
            iterations=solution.iterations,
            total_tokens=solution.total_tokens,
            processing_time=processing_time,
            converged=solution.metadata.get("converged", False),
            stop_reason=solution.metadata.get("stop_reason", "unknown"),
            metadata=solution.metadata,
        )
        
    except Exception as e:
        logger.error(f"Basic solve failed: {e} [request_id={request_id}]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Solve failed: {str(e)}",
        )


@router.post("/enhanced", response_model=SolutionResponse | AsyncJobResponse)
async def solve_enhanced(
    request: EnhancedSolveRequest,
    provider: Annotated[BaseProvider, Depends(get_provider)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    celery_app: Annotated[Celery, Depends(get_celery)],
    request_id: Annotated[str, Depends(get_request_id)],
) -> SolutionResponse | AsyncJobResponse:
    """
    Solve a problem using enhanced mode.
    
    Enhanced mode uses:
    1. Professor agent to analyze the problem
    2. Professor autonomously calls specialist agents via function calling
    3. Each specialist runs their own Self-Evolve
    4. Professor synthesizes all results using Self-Evolve
    
    If `async_mode` is true, returns a job ID for checking status later.
    """
    logger.info(f"Enhanced solve request: {request.question[:100]}... [request_id={request_id}]")
    
    if request.async_mode:
        # Submit to Celery
        job_id = str(uuid.uuid4())
        
        # Store initial job info in Redis
        job_data = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "created_at": datetime.now(datetime.UTC).isoformat(),
            "request": json.dumps(request.model_dump()),
            "mode": "enhanced",
        }
        await redis_client.hset(f"job:{job_id}", mapping=job_data)
        await redis_client.expire(f"job:{job_id}", 3600)  # 1 hour TTL
        
        # Submit task to Celery
        celery_app.send_task(
            "app.worker.solve_enhanced_task",
            args=[job_id, request.model_dump()],
            task_id=job_id,
        )
        
        return AsyncJobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(datetime.UTC),
            message="Job submitted successfully",
        )
    
    # Synchronous execution
    try:
        start_time = time.time()
        
        # Create runner
        runner = EnhancedRunner(
            provider=provider,
            max_iters_per_specialist=request.specialist_max_iters or settings.specialist_max_iters,
            professor_max_iters=request.professor_max_iters or settings.professor_max_iters,
        )
        
        # Solve
        solution = await runner.solve(
            question=request.question,
            metadata={"request_id": request_id},
        )
        
        processing_time = time.time() - start_time
        
        return SolutionResponse(
            output=solution.output,
            iterations=solution.iterations,
            total_tokens=solution.total_tokens,
            processing_time=processing_time,
            converged=solution.metadata.get("converged", False),
            stop_reason=solution.metadata.get("stop_reason", "unknown"),
            metadata=solution.metadata,
        )
        
    except Exception as e:
        logger.error(f"Enhanced solve failed: {e} [request_id={request_id}]")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Solve failed: {str(e)}",
        )