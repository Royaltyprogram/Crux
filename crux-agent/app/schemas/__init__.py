"""Request and response schemas for Tooliense SE-Agents API."""

from .request import (
    BasicSolveRequest,
    EnhancedSolveRequest,
    JobStatusRequest,
    SolveRequest,
)
from .response import (
    AsyncJobResponse,
    ErrorResponse,
    HealthResponse,
    JobStatus,
    JobStatusResponse,
    SolutionResponse,
    solution_to_response,
)

__all__ = [
    # Request schemas
    "SolveRequest",
    "BasicSolveRequest", 
    "EnhancedSolveRequest",
    "JobStatusRequest",
    
    # Response schemas
    "SolutionResponse",
    "AsyncJobResponse",
    "JobStatusResponse", 
    "ErrorResponse",
    "HealthResponse",
    "JobStatus",
    
    # Helper functions
    "solution_to_response",
] 