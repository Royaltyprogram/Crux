"""
Response schemas for API endpoints.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration."""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SolutionResponse(BaseModel):
    """Response containing solution."""
    
    output: str = Field(..., description="The final answer/solution")
    iterations: int = Field(..., description="Number of iterations performed")
    total_tokens: int = Field(..., description="Total tokens consumed")
    processing_time: float = Field(..., description="Processing time in seconds")
    converged: bool = Field(..., description="Whether the solution converged (evaluator issued <stop> token)")
    stop_reason: str = Field(..., description="Reason for stopping (evaluator_stop or max_iterations)")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="""Additional metadata containing detailed execution information:
        - runner: 'basic' or 'enhanced'
        - approach: 'professor_function_calling' for enhanced mode
        - specialist_consultations: Number of specialist consultations
        - specialist_results: List of specialist consultation results
        - evolution_history: Detailed history of each Self-Evolve iteration
        - function_calling_used: Whether Professor used function calling
        - problem: Original problem details
        """
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "output": "The solution to your problem is...",
                "iterations": 3,
                "total_tokens": 1250,
                "processing_time": 5.23,
                "converged": True,
                "stop_reason": "evaluator_stop",
                "metadata": {
                    "runner": "enhanced",
                    "approach": "professor_function_calling",
                    "specialist_consultations": 2,
                    "function_calling_used": True,
                    "specialist_results": [
                        {
                            "specialization": "symbolic integration expert with advanced techniques",
                            "task": "Evaluate the integral ∫x²sin(x)dx using the most rigorous approach",
                            "output": "Using integration by parts twice: Let u = x², dv = sin(x)dx...",
                            "iterations": 3,
                            "converged": True,
                            "total_tokens": 856
                        }
                    ],
                    "evolution_history": [
                        {
                            "iteration": 1,
                            "prompt": "Solve: ∫x²sin(x)dx",
                            "output": "I need to analyze this integral and possibly consult specialists...",
                            "feedback": "Good starting approach but needs specialist consultation for rigor...",
                            "should_stop": False
                        }
                    ]
                }
            }
        }


def solution_to_response(solution, processing_time: float) -> SolutionResponse:
    """
    Convert Self-Evolve Solution to API SolutionResponse.
    
    Args:
        solution: Solution object from Self-Evolve engine
        processing_time: Processing time in seconds
        
    Returns:
        SolutionResponse for API
    """
    # Extract convergence information
    converged = solution.metadata.get("converged", False)
    stop_reason = solution.metadata.get("stop_reason", "unknown")
    
    # Prepare metadata with evolution_history included
    metadata = solution.metadata.copy()
    metadata["evolution_history"] = solution.evolution_history
    
    return SolutionResponse(
        output=solution.output,
        iterations=solution.iterations,
        total_tokens=solution.total_tokens,
        processing_time=processing_time,
        converged=converged,
        stop_reason=stop_reason,
        metadata=metadata,
    )


class AsyncJobResponse(BaseModel):
    """Response when job is submitted asynchronously."""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    message: str = Field(..., description="Status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "created_at": "2025-01-23T10:00:00Z",
                "message": "Job submitted successfully",
            }
        }


class JobStatusResponse(BaseModel):
    """Response for job status check."""
    
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current job status")
    created_at: Optional[datetime] = Field(None, description="Job creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Progress percentage")
    current_phase: Optional[str] = Field(None, description="Current processing phase")
    result: Optional[SolutionResponse] = Field(None, description="Final result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    partial_results: Optional[List[Dict[str, Any]]] = Field(None, description="Partial results if available")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "created_at": "2025-01-23T10:00:00Z",
                "started_at": "2025-01-23T10:00:01Z",
                "completed_at": "2025-01-23T10:00:06Z",
                "progress": 1.0,
                "current_phase": "Finalizing solution",
                "result": {
                    "output": "The solution is...",
                    "iterations": 3,
                    "total_tokens": 1250,
                    "processing_time": 5.0,
                    "converged": True,
                    "stop_reason": "evaluator_stop",
                    "metadata": {
                        "runner": "enhanced",
                        "specialist_consultations": 1,
                    },
                },
            }
        }


class ErrorResponse(BaseModel):
    """Error response."""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[Any] = Field(None, description="Additional error details")
    request_id: Optional[str] = Field(None, description="Request ID for debugging")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Question cannot be empty",
                "detail": {"field": "question", "type": "value_error"},
                "request_id": "req_123456",
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current timestamp")
    providers: Dict[str, bool] = Field(..., description="Provider availability")
    redis: bool = Field(..., description="Redis connectivity")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2025-01-23T10:00:00Z",
                "providers": {
                    "openai": True,
                    "openrouter": True,
                },
                "redis": True,
            }
        } 