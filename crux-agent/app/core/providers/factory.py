"""
Provider factory for creating LLM provider instances.
"""
from typing import Optional

from app.core.providers.base import BaseProvider
from app.core.providers.openai import OpenAIProvider
from app.core.providers.openrouter import OpenRouterProvider
from app.settings import settings


def create_provider(
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseProvider:
    """
    Create a provider instance based on configuration.
    
    Args:
        provider_name: Provider name (default from settings)
        model: Model name (default from settings)
        api_key: API key (default from settings)
        
    Returns:
        Provider instance
        
    Raises:
        ValueError: If provider is not supported
    """
    # Use defaults from settings if not provided
    provider_name = provider_name or settings.llm_provider
    
    if provider_name == "openai":
        if not api_key and not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        return OpenAIProvider(
            api_key=api_key or settings.openai_api_key.get_secret_value(),
            model=model or settings.model_openai,
            timeout=settings.openai_timeout,
            max_retries=settings.openai_max_retries,
        )
    elif provider_name == "openrouter":
        if not api_key and not settings.openrouter_api_key:
            raise ValueError("OpenRouter API key not configured")
        return OpenRouterProvider(
            api_key=api_key or settings.openrouter_api_key.get_secret_value(),
            model=model or settings.model_openrouter,
            timeout=settings.openrouter_timeout,
            max_retries=settings.openrouter_max_retries,
            app_name=settings.app_name,
        )
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


# Export provider classes and factory
__all__ = [
    "BaseProvider",
    "OpenAIProvider", 
    "OpenRouterProvider",
    "create_provider",
] 