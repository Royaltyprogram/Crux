"""
Solve endpoints for basic and enhanced modes.
"""
import json
import time
import uuid
from datetime import datetime, timezone
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
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request": json.dumps(request.model_dump()),
            "mode": "basic",
            "model_name": request.model_name or provider.model,
        }
        await redis_client.hset(f"job:{job_id}", mapping=job_data)
        # TESTING MODE: Extended TTL to prevent automatic deletion during testing
        await redis_client.expire(f"job:{job_id}", 86400 * 7)  # 7 days TTL (was 1 hour)
        
        # Submit task to Celery
        celery_app.send_task(
            "app.worker.solve_basic_task",
            args=[job_id, request.model_dump()],
            task_id=job_id,
        )
        
        return AsyncJobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
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
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request": json.dumps(request.model_dump()),
            "mode": "enhanced",
            "model_name": request.model_name or provider.model,
        }
        await redis_client.hset(f"job:{job_id}", mapping=job_data)
        # TESTING MODE: Extended TTL to prevent automatic deletion during testing
        await redis_client.expire(f"job:{job_id}", 86400 * 7)  # 7 days TTL (was 1 hour)
        
        # Submit task to Celery
        celery_app.send_task(
            "app.worker.solve_enhanced_task",
            args=[job_id, request.model_dump()],
            task_id=job_id,
        )
        
        return AsyncJobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
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


@router.post("/continue/{job_id}", response_model=SolutionResponse | AsyncJobResponse)
async def continue_task(
    job_id: str,
    provider: Annotated[BaseProvider, Depends(get_provider)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)],
    celery_app: Annotated[Celery, Depends(get_celery)],
    request_id: Annotated[str, Depends(get_request_id)],
    additional_iterations: int = 1,
) -> SolutionResponse | AsyncJobResponse:
    """
    Continue a completed task with additional iterations.
    
    This endpoint allows extending a task that reached max iterations
    but hasn't converged by adding more iterations.
    
    Args:
        job_id: The job ID to continue
        additional_iterations: Number of additional iterations to run (default: 1)
    
    Returns:
        New solution with extended iterations or async job response
    """
    logger.info(f"Continue task request: {job_id} (+{additional_iterations} iterations) [request_id={request_id}]")
    
    # Check if job exists
    job_data = await redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    
    # Decode bytes to strings
    job_data = {k.decode(): v.decode() for k, v in job_data.items()}
    
    # Check if job is completed
    if job_data.get("status") != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not completed. Current status: {job_data.get('status')}",
        )
    
    # Parse the result to get evolution history
    try:
        result = json.loads(job_data.get("result", "{}"))
        evolution_history = result.get("metadata", {}).get("evolution_history", [])
        
        if not evolution_history:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job has no evolution history to continue from",
            )
        
        # Check if task already converged
        if result.get("converged", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task already converged. Cannot continue a converged task.",
            )
        
        # Parse original request
        original_request = json.loads(job_data.get("request", "{}"))
        mode = job_data.get("mode", "basic")
        
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job data: {str(e)}",
        )
    
    # Create new job ID for the continuation
    new_job_id = str(uuid.uuid4())
    
    # Store initial job info in Redis
    continuation_job_data = {
        "job_id": new_job_id,
        "status": JobStatus.PENDING.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "request": json.dumps(original_request),
        "mode": mode,
        "continued_from": job_id,
        "additional_iterations": additional_iterations,
        "model_name": job_data.get("model_name", provider.model),
    }
    await redis_client.hset(f"job:{new_job_id}", mapping=continuation_job_data)
    await redis_client.expire(f"job:{new_job_id}", 86400 * 7)  # 7 days TTL
    
    # Submit continuation task to Celery
    if mode == "basic":
        celery_app.send_task(
            "app.worker.continue_basic_task",
            args=[new_job_id, original_request, evolution_history, additional_iterations],
            task_id=new_job_id,
        )
    else:
        # For now, only support basic mode continuation
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task continuation is currently only supported for basic mode",
        )
    
    return AsyncJobResponse(
        job_id=new_job_id,
        status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        message=f"Task continuation submitted successfully (+{additional_iterations} iterations)",
    )
