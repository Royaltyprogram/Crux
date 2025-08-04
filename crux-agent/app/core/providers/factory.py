"""
Provider factory for creating LLM provider instances.
"""
from typing import Optional

from app.core.providers.base import BaseProvider
from app.core.providers.openai import OpenAIProvider
from app.core.providers.openrouter import OpenRouterProvider
from app.core.providers.lmstudio import LMStudioProvider
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
    elif provider_name == "lmstudio":
        # Get the API key from parameters or settings
        # If api_key is explicitly passed (including empty string), use it
        if api_key is not None:
            final_api_key = api_key
        else:
            final_api_key = settings.lmstudio_api_key.get_secret_value() if settings.lmstudio_api_key else None
        
        # For LMStudio, allow empty key when host is localhost (local instances often don't require keys)
        # Check if we're connecting to localhost by examining the base_url from settings
        base_url = f"{settings.lmstudio_base_url}/v1/chat/completions"
        is_localhost = "localhost" in settings.lmstudio_base_url or "127.0.0.1" in settings.lmstudio_base_url
        
        # Raise error if key is missing and not connecting to localhost
        # Only raise error if api_key was not explicitly provided and no key configured
        # Allow empty API key if explicitly provided (for no-auth servers)
        if final_api_key is None and not is_localhost and api_key is None:
            raise ValueError("LMStudio API key not configured")
        
        return LMStudioProvider(
            api_key=final_api_key or "",  # Use empty string for localhost when no key provided
            model=model or settings.model_lmstudio,
            timeout=settings.lmstudio_timeout,
            max_retries=settings.lmstudio_max_retries,
            base_url=base_url,
        )
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


# Export provider classes and factory
__all__ = [
    "BaseProvider",
    "OpenAIProvider", 
    "OpenRouterProvider",
    "LMStudioProvider",
    "create_provider",
]
