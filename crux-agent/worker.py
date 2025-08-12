"""
Celery worker for asynchronous task processing.
"""
import asyncio
import json
import time
from datetime import datetime

from celery import Celery
import logging

from celery.utils.log import get_task_logger

from app.core.orchestrators.basic import BasicRunner
from app.core.orchestrators.enhanced import EnhancedRunner
from app.core.providers.factory import create_provider
from app.schemas.response import JobStatus
from app.settings import settings

# Initialize Celery app
app = Celery(
    settings.app_name,
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configure Celery
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=10800,  # 3 hours hard limit
    task_soft_time_limit=10000,  # 2 hours 46 minutes soft limit
    worker_prefetch_multiplier=1,  # For fair task distribution
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    # Suppress stdout/stderr noise (e.g., token-by-token prints) unless ERROR or higher
    worker_redirect_stdouts=True,
    worker_redirect_stdouts_level="ERROR",
)

logger = get_task_logger(__name__)

# Reduce noisy provider logs at standard log level (INFO)
# OpenRouter SSE/keep-alive handling can emit verbose diagnostics; clamp to WARNING
logging.getLogger("app.core.providers.openrouter").setLevel(logging.DEBUG)

def get_redis_sync():
    """Get synchronous Redis client for Celery tasks."""
    import redis
    return redis.from_url(settings.redis_url, decode_responses=True)


@app.task(name="app.worker.solve_basic_task", bind=True)
def solve_basic_task(self, job_id: str, request_data: dict):
    """
    Celery task for basic mode solving.
    
    Args:
        job_id: Unique job identifier
        request_data: Request data dictionary
    """
    logger.info(f"Starting basic solve task: {job_id}")
    redis_client = get_redis_sync()
    # Single-flight guard: prevent duplicate execution across workers/restarts
    lock_key = f"lock:job:{job_id}"
    have_lock = False
    try:
        # Acquire lock with TTL slightly above soft limit
        have_lock = bool(redis_client.set(lock_key, self.request.id or "worker", nx=True, ex=10800))
        if not have_lock:
            current_status = redis_client.hget(f"job:{job_id}", "status")
            logger.info(f"Duplicate basic task detected for {job_id}; status={current_status}. Skipping.")
            # Early return without changing status/result
            return {"message": "Duplicate basic task skipped", "job_id": job_id, "status": current_status}
    except Exception as e:
        logger.warning(f"Failed to acquire single-flight lock for {job_id}: {e}")
    
    try:
        # Update job status to running (only by the lock holder)
        if have_lock:
            redis_client.hset(
                f"job:{job_id}",
                mapping={
                    "status": JobStatus.RUNNING.value,
                    "started_at": datetime.utcnow().isoformat(),
                },
            )
        
        # Run async solve in sync context
        result = asyncio.run(_solve_basic_async(job_id, request_data, self))
        
        # Store result
        if have_lock:
            redis_client.hset(
                f"job:{job_id}",
                mapping={
                    "status": JobStatus.COMPLETED.value,
                    "completed_at": datetime.utcnow().isoformat(),
                    "result": json.dumps(result),
                    "progress": 1.0,
                },
            )
        
        logger.info(f"Basic solve task completed: {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Basic solve task failed: {job_id} - {e}")
        
        # Update job status to failed
        if have_lock:
            redis_client.hset(
                f"job:{job_id}",
                mapping={
                    "status": JobStatus.FAILED.value,
                    "completed_at": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            )
        
        raise
    finally:
        # Release lock if held
        try:
            if have_lock:
                redis_client.delete(lock_key)
        except Exception:
            pass


@app.task(name="app.worker.solve_enhanced_task", bind=True)
def solve_enhanced_task(self, job_id: str, request_data: dict):
    """
    Celery task for enhanced mode solving.
    
    Args:
        job_id: Unique job identifier
        request_data: Request data dictionary
    """
    logger.info(f"Starting enhanced solve task: {job_id}")
    redis_client = get_redis_sync()
    # Single-flight guard: prevent duplicate execution across workers/restarts
    lock_key = f"lock:job:{job_id}"
    have_lock = False
    try:
        have_lock = bool(redis_client.set(lock_key, self.request.id or "worker", nx=True, ex=10800))
        if not have_lock:
            current_status = redis_client.hget(f"job:{job_id}", "status")
            logger.info(f"Duplicate enhanced task detected for {job_id}; status={current_status}. Skipping.")
            return {"message": "Duplicate enhanced task skipped", "job_id": job_id, "status": current_status}
    except Exception as e:
        logger.warning(f"Failed to acquire single-flight lock for {job_id}: {e}")
    
    try:
        # Update job status to running (only by the lock holder)
        if have_lock:
            redis_client.hset(
                f"job:{job_id}",
                mapping={
                    "status": JobStatus.RUNNING.value,
                    "started_at": datetime.utcnow().isoformat(),
                },
            )
        
        # Run async solve in sync context
        result = asyncio.run(_solve_enhanced_async(job_id, request_data, self))
        
        # Store result
        if have_lock:
            redis_client.hset(
                f"job:{job_id}",
                mapping={
                    "status": JobStatus.COMPLETED.value,
                    "completed_at": datetime.utcnow().isoformat(),
                    "result": json.dumps(result),
                    "progress": 1.0,
                },
            )
        
        logger.info(f"Enhanced solve task completed: {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Enhanced solve task failed: {job_id} - {e}")
        
        # Update job status to failed
        if have_lock:
            redis_client.hset(
                f"job:{job_id}",
                mapping={
                    "status": JobStatus.FAILED.value,
                    "completed_at": datetime.utcnow().isoformat(),
                    "error": str(e),
                },
            )
        
        raise
    finally:
        # Release lock if held
        try:
            if have_lock:
                redis_client.delete(lock_key)
        except Exception:
            pass


async def _solve_basic_async(job_id: str, request_data: dict, task):
    """
    Async implementation of basic solve.
    
    Args:
        job_id: Job ID
        request_data: Request data
        task: Celery task instance for progress updates
        
    Returns:
        Solution response data
    """
    start_time = time.time()
    
    # Create provider using request settings or defaults
    llm_provider = request_data.get("llm_provider")
    
    # Handle LMStudio no-auth case
    api_key = None
    if llm_provider == "lmstudio":
        # For LMStudio, explicitly pass empty string to allow no-auth servers
        api_key = ""
    
    provider = create_provider(
        provider_name=llm_provider,
        model=request_data.get("model_name"),
        api_key=api_key,
    )
    
    # Create runner
    runner = BasicRunner(
        provider=provider,
        max_iters=request_data.get("n_iters") or settings.max_iters,
    )
    
    # Setup progress tracking
    redis_client = get_redis_sync()
    
    def update_progress(progress: float, phase: str = "", metadata: dict = None):
        """Update progress in Redis and Celery with optional metadata."""
        # Build meta dict with progress and phase
        meta = {"progress": progress, "phase": phase}
        
        # Add reasoning tokens and other metadata if available
        if metadata:
            meta.update(metadata)
        
        task.update_state(
            state="PROGRESS",
            meta=meta,
        )
        redis_client.hset(f"job:{job_id}", "progress", progress)
        if phase:
            redis_client.hset(f"job:{job_id}", "current_phase", phase)
        
        # Store reasoning tokens in Redis if available
        if metadata and "reasoning_tokens" in metadata:
            redis_client.hset(f"job:{job_id}", "reasoning_tokens", metadata["reasoning_tokens"])
        
        # Log progress updates with reasoning tokens if available
        reasoning_info = f" (reasoning: {metadata.get('reasoning_tokens', 0)})" if metadata and "reasoning_tokens" in metadata else ""
        logger.info(f"[{job_id}] Progress update: {progress:.1%} - {phase}{reasoning_info}")
    
    # Solve with real-time progress tracking
    solution = await runner.solve(
        question=request_data["question"],
        context=request_data.get("context"),
        constraints=request_data.get("constraints"),
        metadata={"job_id": job_id},
        progress_callback=update_progress,
    )
    
    processing_time = time.time() - start_time
    
    # Prepare metadata with evolution_history included
    metadata = solution.metadata.copy()
    metadata["evolution_history"] = solution.evolution_history
    
    # Return solution data
    return {
        "output": solution.output,
        "iterations": solution.iterations,
        "total_tokens": solution.total_tokens,
        "processing_time": processing_time,
        "converged": solution.metadata.get("converged", False),
        "stop_reason": solution.metadata.get("stop_reason", "unknown"),
        "metadata": metadata,
    }


async def _solve_enhanced_async(job_id: str, request_data: dict, task):
    """
    Async implementation of enhanced solve.
    
    Args:
        job_id: Job ID
        request_data: Request data
        task: Celery task instance for progress updates
        
    Returns:
        Solution response data
    """
    start_time = time.time()
    redis_client = get_redis_sync()
    
    def update_progress(progress: float, phase: str = "", metadata: dict = None):
        """Update progress in Redis and Celery with optional metadata."""
        # Build meta dict with progress and phase
        meta = {"progress": progress, "phase": phase}
        
        # Add reasoning tokens and other metadata if available
        if metadata:
            meta.update(metadata)
        
        task.update_state(
            state="PROGRESS",
            meta=meta,
        )
        redis_client.hset(f"job:{job_id}", "progress", progress)
        if phase:
            redis_client.hset(f"job:{job_id}", "current_phase", phase)
        
        # Store reasoning tokens in Redis if available
        if metadata and "reasoning_tokens" in metadata:
            redis_client.hset(f"job:{job_id}", "reasoning_tokens", metadata["reasoning_tokens"])
    
    # Create provider using request settings or defaults
    llm_provider = request_data.get("llm_provider")
    
    # Handle LMStudio no-auth case
    api_key = None
    if llm_provider == "lmstudio":
        # For LMStudio, explicitly pass empty string to allow no-auth servers
        api_key = ""
    
    provider = create_provider(
        provider_name=llm_provider,
        model=request_data.get("model_name"),
        api_key=api_key,
    )
    
    # Create runner
    runner = EnhancedRunner(
        provider=provider,
        max_iters_per_specialist=request_data.get("specialist_max_iters") or settings.specialist_max_iters,
        professor_max_iters=request_data.get("professor_max_iters") or settings.professor_max_iters,
    )
    
    # Solve with real-time progress tracking
    solution = await runner.solve(
        question=request_data["question"],
        metadata={"job_id": job_id},
        progress_callback=update_progress,
    )
    
    processing_time = time.time() - start_time
    
    # Prepare metadata with evolution_history included
    metadata = solution.metadata.copy()
    metadata["evolution_history"] = solution.evolution_history
    
    # Return solution data
    return {
        "output": solution.output,
        "iterations": solution.iterations,
        "total_tokens": solution.total_tokens,
        "processing_time": processing_time,
        "converged": solution.metadata.get("converged", False),
        "stop_reason": solution.metadata.get("stop_reason", "unknown"),
        "metadata": metadata,
    }


async def _continue_basic_async(job_id: str, original_request_data: dict, evolution_history: list, additional_iterations: int, task):
    """
    Async implementation of continue basic solve.
    
    Args:
        job_id: Job ID
        original_request_data: Original request data
        evolution_history: Previous evolution history
        additional_iterations: Number of additional iterations to run
        task: Celery task instance for progress updates
        
    Returns:
        Solution response data
    """
    start_time = time.time()
    
    # Create provider using original request settings or defaults
    llm_provider = original_request_data.get("llm_provider")
    
    # Handle LMStudio no-auth case
    api_key = None
    if llm_provider == "lmstudio":
        # For LMStudio, explicitly pass empty string to allow no-auth servers
        api_key = ""
    
    provider = create_provider(
        provider_name=llm_provider,
        model=original_request_data.get("model_name"),
        api_key=api_key,
    )
    
    # Create runner
    runner = BasicRunner(
        provider=provider,
        max_iters=original_request_data.get("n_iters") or settings.max_iters,  # This will be overridden in resume_solve
    )
    
    # Setup progress tracking
    redis_client = get_redis_sync()
    
    def update_progress(progress: float, phase: str = "", metadata: dict = None):
        """Update progress in Redis and Celery with optional metadata."""
        # Build meta dict with progress and phase
        meta = {"progress": progress, "phase": phase}
        
        # Add reasoning tokens and other metadata if available
        if metadata:
            meta.update(metadata)
        
        task.update_state(
            state="PROGRESS",
            meta=meta,
        )
        redis_client.hset(f"job:{job_id}", "progress", progress)
        if phase:
            redis_client.hset(f"job:{job_id}", "current_phase", phase)
        
        # Store reasoning tokens in Redis if available
        if metadata and "reasoning_tokens" in metadata:
            redis_client.hset(f"job:{job_id}", "reasoning_tokens", metadata["reasoning_tokens"])
    
    # Resume solve with additional iterations
    solution = await runner.resume_solve(
        question=original_request_data["question"],
        evolution_history=evolution_history,
        additional_iterations=additional_iterations,
        context=original_request_data.get("context"),
        constraints=original_request_data.get("constraints"),
        metadata={"job_id": job_id, "continued_from_iterations": len(evolution_history)},
        progress_callback=update_progress,
    )
    
    processing_time = time.time() - start_time
    
    # Prepare metadata with evolution_history included
    metadata = solution.metadata.copy()
    metadata["evolution_history"] = solution.evolution_history
    
    # Return solution data
    return {
        "output": solution.output,
        "iterations": solution.iterations,
        "total_tokens": solution.total_tokens,
        "processing_time": processing_time,
        "converged": solution.metadata.get("converged", False),
        "stop_reason": solution.metadata.get("stop_reason", "unknown"),
        "metadata": metadata,
    }


@app.task(name="app.worker.continue_basic_task", bind=True)
def continue_basic_task(self, job_id: str, original_request_data: dict, evolution_history: list, additional_iterations: int):
    """
    Celery task for continuing basic mode solving with additional iterations.
    
    Args:
        job_id: New job ID for the continuation
        original_request_data: Original request data dictionary
        evolution_history: Previous evolution history
        additional_iterations: Number of additional iterations to run
    """
    logger.info(f"Starting continue basic solve task: {job_id} (+{additional_iterations} iterations)")
    redis_client = get_redis_sync()
    
    try:
        # Update job status to running
        redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.RUNNING.value,
                "started_at": datetime.utcnow().isoformat(),
            },
        )
        
        # Run async solve in sync context
        result = asyncio.run(_continue_basic_async(job_id, original_request_data, evolution_history, additional_iterations, self))
        
        # Store result
        redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.COMPLETED.value,
                "completed_at": datetime.utcnow().isoformat(),
                "result": json.dumps(result),
                "progress": 1.0,
            },
        )
        
        logger.info(f"Continue basic solve task completed: {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Continue basic solve task failed: {job_id} - {e}")
        
        # Update job status to failed
        redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.FAILED.value,
                "completed_at": datetime.utcnow().isoformat(),
                "error": str(e),
            },
        )
        
        raise


async def _continue_enhanced_async(job_id: str, original_request_data: dict, evolution_history: list, additional_iterations: int, task):
    """
    Async implementation of continue enhanced solve.
    
    Args:
        job_id: Job ID
        original_request_data: Original request data
        evolution_history: Previous evolution history
        additional_iterations: Number of additional iterations to run
        task: Celery task instance for progress updates
        
    Returns:
        Solution response data
    """
    start_time = time.time()
    
    # Create provider using original request settings or defaults
    llm_provider = original_request_data.get("llm_provider")
    
    # Handle LMStudio no-auth case
    api_key = None
    if llm_provider == "lmstudio":
        # For LMStudio, explicitly pass empty string to allow no-auth servers
        api_key = ""
    
    provider = create_provider(
        provider_name=llm_provider,
        model=original_request_data.get("model_name"),
        api_key=api_key,
    )
    
    # Create runner
    runner = EnhancedRunner(
        provider=provider,
        max_iters_per_specialist=original_request_data.get("specialist_max_iters") or settings.specialist_max_iters,
        professor_max_iters=original_request_data.get("professor_max_iters") or settings.professor_max_iters,
    )
    
    # Setup progress tracking
    redis_client = get_redis_sync()
    
    def update_progress(progress: float, phase: str = "", metadata: dict = None):
        """Update progress in Redis and Celery with optional metadata."""
        # Build meta dict with progress and phase
        meta = {"progress": progress, "phase": phase}
        
        # Add reasoning tokens and other metadata if available
        if metadata:
            meta.update(metadata)
        
        task.update_state(
            state="PROGRESS",
            meta=meta,
        )
        redis_client.hset(f"job:{job_id}", "progress", progress)
        if phase:
            redis_client.hset(f"job:{job_id}", "current_phase", phase)
        
        # Store reasoning tokens in Redis if available
        if metadata and "reasoning_tokens" in metadata:
            redis_client.hset(f"job:{job_id}", "reasoning_tokens", metadata["reasoning_tokens"])
    
    # Resume solve with additional iterations
    solution = await runner.resume_solve(
        question=original_request_data["question"],
        evolution_history=evolution_history,
        additional_iterations=additional_iterations,
        metadata={"job_id": job_id, "continued_from_iterations": len(evolution_history)},
        progress_callback=update_progress,
    )
    
    processing_time = time.time() - start_time
    
    # Prepare metadata with evolution_history included
    metadata = solution.metadata.copy()
    metadata["evolution_history"] = solution.evolution_history
    
    # Return solution data
    return {
        "output": solution.output,
        "iterations": solution.iterations,
        "total_tokens": solution.total_tokens,
        "processing_time": processing_time,
        "converged": solution.metadata.get("converged", False),
        "stop_reason": solution.metadata.get("stop_reason", "unknown"),
        "metadata": metadata,
    }


@app.task(name="app.worker.continue_enhanced_task", bind=True)
def continue_enhanced_task(self, job_id: str, original_request_data: dict, evolution_history: list, additional_iterations: int):
    """
    Celery task for continuing enhanced mode solving with additional iterations.
    
    Args:
        job_id: New job ID for the continuation
        original_request_data: Original request data dictionary
        evolution_history: Previous evolution history
        additional_iterations: Number of additional iterations to run
    """
    logger.info(f"Starting continue enhanced solve task: {job_id} (+{additional_iterations} iterations)")
    redis_client = get_redis_sync()
    
    try:
        # Update job status to running
        redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.RUNNING.value,
                "started_at": datetime.utcnow().isoformat(),
            },
        )
        
        # Run async solve in sync context
        result = asyncio.run(_continue_enhanced_async(job_id, original_request_data, evolution_history, additional_iterations, self))
        
        # Store result
        redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.COMPLETED.value,
                "completed_at": datetime.utcnow().isoformat(),
                "result": json.dumps(result),
                "progress": 1.0,
            },
        )
        
        logger.info(f"Continue enhanced solve task completed: {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Continue enhanced solve task failed: {job_id} - {e}")
        
        # Update job status to failed
        redis_client.hset(
            f"job:{job_id}",
            mapping={
                "status": JobStatus.FAILED.value,
                "completed_at": datetime.utcnow().isoformat(),
                "error": str(e),
            },
        )
        
        raise


# Health check task
@app.task(name="app.worker.health_check")
def health_check():
    """Simple health check task."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "celery",
    }


if __name__ == "__main__":
    # Run worker
    app.worker_main(
        argv=[
            "worker",
            "--loglevel=info",
            "--concurrency=100",
            "--pool=gevent",  # Use gevent for I/O-bound tasks
        ]
    ) 