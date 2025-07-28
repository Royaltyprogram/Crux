"""
Base agent interface and models.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.core.providers.base import BaseProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AgentResult(BaseModel):
    """Result from agent execution."""
    
    output: str = Field(..., description="Main output text")
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Quality score if applicable")
    feedback: Optional[str] = Field(None, description="Feedback or reasoning")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    raw_response: Optional[str] = Field(None, description="Raw LLM response")
    tokens_used: Optional[int] = Field(None, description="Number of tokens used")


class AgentContext(BaseModel):
    """Context passed to agent execution."""
    
    prompt: str = Field(..., description="Main prompt or question")
    output: Optional[str] = Field(None, description="Previous output to evaluate/refine")
    feedback: Optional[str] = Field(None, description="Feedback for refinement")
    additional_context: Dict[str, Any] = Field(default_factory=dict, description="Extra context")
    
    class Config:
        extra = "allow"  # Allow additional fields


class AbstractAgent(ABC):
    """Abstract base class for all agents."""
    
    def __init__(
        self,
        role: str,
        provider: BaseProvider,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        service_tier: Optional[str] = None,
    ):
        """
        Initialize agent.
        
        Args:
            role: Agent role/name
            provider: LLM provider instance
            system_prompt: Default system prompt
            temperature: Default temperature for generation
        """
        self.role = role
        self.provider = provider
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.service_tier = service_tier
        
    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """
        Execute agent logic.
        
        Args:
            context: Execution context
            
        Returns:
            Agent result
        """
        pass
    
    async def _generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate text using provider.
        
        Args:
            prompt: User prompt
            system_prompt: Override system prompt
            temperature: Override temperature
            **kwargs: Additional provider parameters
            
        Returns:
            Generated text
        """
        # Add service_tier if configured and provider supports it (OpenAI only)
        if self.service_tier and hasattr(self.provider, 'model') and self.provider.model.lower().startswith('o'):
            kwargs['service_tier'] = self.service_tier
        
        return await self.provider.complete(
            prompt=prompt,
            system_prompt=system_prompt or self.system_prompt,
            temperature=temperature if temperature is not None else self.temperature,
            **kwargs,
        )
    
    async def _generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate JSON using provider.
        
        Args:
            prompt: User prompt
            system_prompt: Override system prompt
            temperature: Override temperature
            **kwargs: Additional provider parameters
            
        Returns:
            Generated JSON object
        """
        return await self.provider.complete_json(
            prompt=prompt,
            system_prompt=system_prompt or self.system_prompt,
            temperature=temperature if temperature is not None else self.temperature,
            **kwargs,
        )
    
    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(role='{self.role}', provider={self.provider.__class__.__name__})" 