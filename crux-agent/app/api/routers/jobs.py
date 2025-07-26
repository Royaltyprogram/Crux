"""
Job status and management endpoints.
"""
import json
from datetime import datetime, timezone
from typing import Annotated

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from celery import Celery

from app.api.dependencies import get_redis, get_celery
from app.schemas.response import JobStatus, JobStatusResponse, SolutionResponse
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: Annotated[str, Path(description="Job ID to check status")],
    include_partial_results: Annotated[bool, Query(description="Whether to include partial results if job is still running")] = False,
    include_evolution_history: Annotated[bool, Query(description="Whether to include detailed evolution history in results")] = False,
    include_specialist_details: Annotated[bool, Query(description="Whether to include detailed specialist consultation results")] = False,
    redis_client: Annotated[redis.Redis, Depends(get_redis)] = None,
) -> JobStatusResponse:
    """
    Get job status and results.
    
    Check the status of an asynchronous job and retrieve results when complete.
    """
    logger.info(f"Checking job status: {job_id}")
    
    try:
        # Get job data from Redis
        job_data = await redis_client.hgetall(f"job:{job_id}")
        
        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )
        
        # Decode bytes to strings
        job_data = {k.decode(): v.decode() for k, v in job_data.items()}
        
        # Parse dates
        created_at = None
        if "created_at" in job_data:
            created_at = datetime.fromisoformat(job_data["created_at"])
        
        started_at = None
        if "started_at" in job_data:
            started_at = datetime.fromisoformat(job_data["started_at"])
        
        completed_at = None
        if "completed_at" in job_data:
            completed_at = datetime.fromisoformat(job_data["completed_at"])
        
        # Build response
        response = JobStatusResponse(
            job_id=job_id,
            status=JobStatus(job_data["status"]),
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            progress=float(job_data.get("progress", 0.0)),
            current_phase=job_data.get("current_phase"),
        )
        
        # Add result if completed
        if job_data["status"] == JobStatus.COMPLETED and "result" in job_data:
            result_data = json.loads(job_data["result"])
            response.result = SolutionResponse(**result_data)
        
        # Add error if failed
        if job_data["status"] == JobStatus.FAILED and "error" in job_data:
            response.error = job_data["error"]
        
        # Add partial results if requested and available
        if include_partial_results and "partial_results" in job_data:
            response.partial_results = json.loads(job_data["partial_results"])
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}",
        )


@router.delete("/{job_id}")
async def cancel_job(
    job_id: Annotated[str, Path(description="Job ID to cancel")],
    celery_app: Annotated[Celery, Depends(get_celery)],
    redis_client: Annotated[redis.Redis, Depends(get_redis)] = None,
) -> dict:
    """
    Cancel a pending or running job.
    
    Note: This sets the job status to cancelled but doesn't stop running workers.
    Full cancellation requires Celery task revocation.
    """
    logger.info(f"Cancelling job: {job_id}")
    
    try:
        # Check if job exists
        exists = await redis_client.exists(f"job:{job_id}")
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )
        
        # Get current status
        current_status = await redis_client.hget(f"job:{job_id}", "status")
        current_status = current_status.decode() if current_status else None
        
        # Only cancel if pending or running
        if current_status not in [JobStatus.PENDING.value, JobStatus.RUNNING.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job in status: {current_status}",
            )
        
        # Update status first so clients immediately see cancellation.
        await redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.CANCELLED.value,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Revoke the running Celery task (terminate=True ‑ force kill).
        # The job_id is used as Celery task_id when the task was submitted
        # (see app/api/routers/solve.py). Hence we can directly revoke it.
        try:
            celery_app.control.revoke(job_id, terminate=True, signal="SIGKILL")
            logger.info(f"Celery task revoked: {job_id}")
        except Exception as revoke_err:
            logger.warning(f"Failed to revoke Celery task {job_id}: {revoke_err}")
        
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancellation requested and task revoked",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}",
        ) 