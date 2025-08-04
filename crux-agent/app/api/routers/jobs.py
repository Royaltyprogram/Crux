"""
Job status and management endpoints.
"""
import json
from datetime import datetime, timezone
from typing import Annotated, List, Dict, Any

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


def _extract_specialist_iterations(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract specialist iteration details from task metadata.
    
    Returns a list of specialist info with iterations for dashboard display.
    """
    specialist_results = metadata.get("specialist_results", [])
    specialist_info = []
    
    for result in specialist_results:
        specialist_meta = result.get("metadata", {})
        specialist_info.append({
            "specialization": result.get("specialization", "Unknown"),
            "iterations": specialist_meta.get("iterations", 0),
            "converged": specialist_meta.get("converged", False),
            "total_tokens": specialist_meta.get("total_tokens", 0),
        })
    
    return specialist_info


@router.get("/", response_model=List[JobStatusResponse])
async def list_jobs(
    status_filter: Annotated[str, Query(description="Filter by job status (completed, failed, running, pending, cancelled)")] = None,
    limit: Annotated[int, Query(description="Maximum number of jobs to return", ge=1, le=100)] = 50,
    redis_client: Annotated[redis.Redis, Depends(get_redis)] = None,
) -> List[JobStatusResponse]:
    """
    List recent jobs with optional status filtering.
    
    Returns a list of jobs sorted by creation date (newest first).
    """
    logger.info(f"Listing jobs with status filter: {status_filter}, limit: {limit}")
    
    try:
        # Find all job keys in Redis
        job_keys = await redis_client.keys("job:*")
        
        if not job_keys:
            return []
        
        jobs = []
        
        for job_key in job_keys:
            try:
                # Get job data
                job_data = await redis_client.hgetall(job_key)
                if not job_data:
                    continue
                
                # Decode bytes to strings
                job_data = {k.decode(): v.decode() for k, v in job_data.items()}
                
                # Skip if status filter is specified and doesn't match
                if status_filter and job_data.get("status") != status_filter:
                    continue
                
                # Extract job ID from key
                job_id = job_key.decode().replace("job:", "")
                
                # Parse dates
                created_at = None
                if "created_at" in job_data:
                    try:
                        created_at = datetime.fromisoformat(job_data["created_at"])
                    except ValueError:
                        pass
                
                started_at = None
                if "started_at" in job_data:
                    try:
                        started_at = datetime.fromisoformat(job_data["started_at"])
                    except ValueError:
                        pass
                
                completed_at = None
                if "completed_at" in job_data:
                    try:
                        completed_at = datetime.fromisoformat(job_data["completed_at"])
                    except ValueError:
                        pass
                
                # Build basic response (without full result data to keep response size manageable)
                response = JobStatusResponse(
                    job_id=job_id,
                    status=JobStatus(job_data["status"]),
                    created_at=created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    progress=float(job_data.get("progress", 0.0)),
                    current_phase=job_data.get("current_phase"),
                    model_name=job_data.get("model_name"),
                    provider_name=job_data.get("provider_name"),
                )
                
                # Extract question from the original request for display
                if "request" in job_data:
                    try:
                        request_data = json.loads(job_data["request"])
                        question = request_data.get("question", "")
                        # Store question snippet in metadata for frontend display
                        if not hasattr(response, 'metadata'):
                            response.metadata = {}
                        response.metadata = response.metadata or {}
                        response.metadata["question_snippet"] = question[:300] + ("..." if len(question) > 300 else "")
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Failed to parse request data for job {job_id}: {e}")
                
                # Add minimal result info for completed jobs (without full content)
                if job_data["status"] == JobStatus.COMPLETED and "result" in job_data:
                    try:
                        result_data = json.loads(job_data["result"])
                        # Only include summary info, not full output
                        response.result = SolutionResponse(
                            output="",  # Don't include full output in list view
                            iterations=result_data.get("iterations", 0),
                            total_tokens=result_data.get("total_tokens", 0),
                            processing_time=result_data.get("processing_time", 0.0),
                            converged=result_data.get("converged", False),
                            stop_reason=result_data.get("stop_reason", "unknown"),
                            metadata={
                                "runner": result_data.get("metadata", {}).get("runner", "basic"),
                                "specialist_consultations": result_data.get("metadata", {}).get("specialist_consultations", 0),
                                "specialist_iterations": _extract_specialist_iterations(result_data.get("metadata", {})),
                            }
                        )
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Failed to parse result for job {job_id}: {e}")
                
                # Add error message for failed jobs
                if job_data["status"] == JobStatus.FAILED and "error" in job_data:
                    response.error = job_data["error"]
                
                jobs.append(response)
                
            except Exception as e:
                logger.warning(f"Failed to process job {job_key}: {e}")
                continue
        
        # Sort by creation date (newest first) and limit results
        jobs.sort(key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        
        return jobs[:limit]
        
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}",
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
            model_name=job_data.get("model_name"),
            provider_name=job_data.get("provider_name"),
        )
        
        # Add job_params for mode detection
        if "mode" in job_data or "request" in job_data:
            job_params = {}
            
            # Add mode from direct field
            if "mode" in job_data:
                job_params["mode"] = job_data["mode"]
                job_params["runner"] = job_data["mode"]  # Also add as runner for compatibility
            
            # Parse original request for additional parameters
            if "request" in job_data:
                try:
                    request_data = json.loads(job_data["request"])
                    # Add any relevant request parameters
                    if "async_mode" in request_data:
                        job_params["async_mode"] = request_data["async_mode"]
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse request data for job_params in job {job_id}: {e}")
            
            if job_params:
                response.job_params = job_params
        
        # Add result if completed
        if job_data["status"] == JobStatus.COMPLETED and "result" in job_data:
            result_data = json.loads(job_data["result"])
            # Ensure token fields are accessible at the top level of metadata
            if "metadata" in result_data:
                metadata = result_data["metadata"].copy()
                # Make sure key token fields are available at metadata level for frontend access
                for token_field in ["professor_tokens", "specialist_tokens", "reasoning_tokens"]:
                    if token_field in result_data["metadata"]:
                        metadata[token_field] = result_data["metadata"][token_field]
                result_data["metadata"] = metadata
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


@router.get("/config/context-limits")
async def get_context_limits() -> dict:
    """
    Get context limits configuration for all providers.
    
    Returns context window sizes and management settings for each LLM provider.
    """
    from app.settings import settings
    
    try:
        return {
            "providers": {
                "openai": {
                    "context_limit": settings.openai_context_limit,
                    "models": {
                        # Use exact model names as they appear in the system
                        "o4-mini": 128000,
                        "o3": 1000000,
                        "gpt-4o-mini": 128000,
                        "gpt-4o": 128000,
                        "gpt-4": 8192,
                        "gpt-3.5-turbo": 16385
                    }
                },
                "openrouter": {
                    "context_limit": settings.openrouter_context_limit,
                    "models": {
                        # Use exact model names as they appear in OpenRouter
                        "deepseek/deepseek-r1-0528:free": 65536,
                        "qwen/qwen3-235b-a22b-2507:free": 32768,
                        "x-ai/grok-4": 131072,
                        "anthropic/claude-3.5-sonnet": 200000,
                        "meta-llama/llama-3.1-8b-instruct:free": 131072
                    }
                },
                "lmstudio": {
                    "context_limit": settings.lmstudio_context_limit,
                    "models": {
                        # LMStudio uses the configured context limit from .env
                        # The actual model name doesn't matter for context limit lookup
                        # since LMStudio models all use the same configured limit
                    }
                }
            },
            "management": {
                "summarization_threshold": settings.summarization_threshold,
                "response_reserve": settings.response_reserve
            },
            "fallback_limit": 50000  # Used when no specific model match is found
        }
    except Exception as e:
        logger.error(f"Error getting context limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context limits: {str(e)}",
        )
