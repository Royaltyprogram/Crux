"""
Request schemas for API endpoints.

The new Tooliense SE-Agents framework supports two modes:

1. Basic Mode: Single Self-Evolve with context/constraints used directly
   - Generator receives context and constraints directly
   - Single Self-Evolve loop (default: 6 iterations)
   
2. Enhanced Mode: Professor with autonomous Function Calling + Specialist Self-Evolve
   - Professor autonomously decides what specialists to call via function calling
   - Each specialist runs their own Self-Evolve (default: 4 iterations)
   - Professor runs Self-Evolve for final synthesis (default: 2 iterations)
   - No manual task decomposition or specialist hints - fully autonomous

All evaluation is feedback-based using <stop> tokens (no numerical scores).
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SolveRequest(BaseModel):
    """Base request for solve endpoints."""
    
    question: str = Field(..., description="The question or problem to solve", min_length=1)
    context: Optional[str] = Field(None, description="Additional context - used in basic mode only")
    constraints: Optional[str] = Field(None, description="Constraints or requirements - used in basic mode only")
    n_iters: Optional[int] = Field(None, ge=1, le=10, description="Maximum iterations (overrides default for basic mode)")
    professor_max_iters: Optional[int] = Field(None, ge=1, le=10, description="Maximum iterations for Professor level (default: 2)")
    specialist_max_iters: Optional[int] = Field(None, ge=1, le=8, description="Maximum iterations for Specialist level (default: 4)")
    llm_provider: Optional[str] = Field(None, description="LLM provider to use (e.g., 'openai', 'openrouter')")
    model_name: Optional[str] = Field(None, description="Model name to use (e.g., 'gpt-4o', 'meta-llama/llama-3.3-70b-instruct')")
    async_mode: bool = Field(False, description="Whether to run asynchronously and return job ID")
    
    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Ensure question is not empty."""
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty")
        return v


class BasicSolveRequest(SolveRequest):
    """Request for basic solve mode."""
    pass


class EnhancedSolveRequest(SolveRequest):
    """Request for enhanced solve mode with Professor function calling."""
    pass


class JobStatusRequest(BaseModel):
    """Request for job status check."""
    
    include_partial_results: bool = Field(
        False,
        description="Whether to include partial results if job is still running",
    )
    include_evolution_history: bool = Field(
        False,
        description="Whether to include detailed evolution history in results",
    )
    include_specialist_details: bool = Field(
        False,
        description="Whether to include detailed specialist consultation results",
    ) 