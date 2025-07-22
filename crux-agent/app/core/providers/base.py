"""
Base provider interface for LLM interactions.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.utils.logging import get_logger

logger = get_logger(__name__)


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class RateLimitError(ProviderError):
    """Rate limit exceeded error."""
    pass


class TimeoutError(ProviderError):
    """Request timeout error."""
    pass


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: int = 60,
        max_retries: int = 3,
    ):
        """
        Initialize provider.
        
        Args:
            api_key: API key for authentication
            model: Model name to use
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        # Store reasoning summary from the most recent API call
        self.last_reasoning_summary: str = ""
    
    async def __aenter__(self) -> "BaseProvider":
        """Async context manager entry."""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request arguments
            
        Returns:
            HTTP response
            
        Raises:
            TimeoutError: If request times out
            ProviderError: For other HTTP errors
        """
        await self._ensure_client()
        
        try:
            response = await self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise TimeoutError(f"Request timed out after {self.timeout}s") from e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Rate limit exceeded")
                raise RateLimitError("Rate limit exceeded") from e
            logger.error(f"HTTP error: {e}")
            raise ProviderError(f"HTTP {e.response.status_code}: {e.response.text}") from e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise ProviderError(f"Unexpected error: {str(e)}") from e
    
    @abstractmethod
    async def complete(
        self,
        *,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate completion for the given prompt.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt to prepend
            **kwargs: Provider-specific parameters
            
        Returns:
            Generated text completion
        """
        pass
    
    @abstractmethod
    async def complete_json(
        self,
        *,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate JSON completion for the given prompt.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt to prepend
            **kwargs: Provider-specific parameters
            
        Returns:
            Generated JSON object
        """
        pass
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Default implementation uses character-based estimation.
        Subclasses should override with provider-specific tokenization.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token
        return len(text) // 4 
    
    def get_last_reasoning_summary(self) -> str:
        """Get the reasoning summary from the most recent API call."""
        return getattr(self, 'last_reasoning_summary', '')

 