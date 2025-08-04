"""
Service for fetching available models from different LLM providers.
"""
from typing import List, Dict, Any
import asyncio

from app.core.providers.factory import create_provider
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


async def get_dynamic_models(provider: str) -> List[str]:
    """
    Get available models dynamically from the specified provider.
    
    Args:
        provider: Provider name ("openai", "openrouter", "lmstudio")
        
    Returns:
        List of model names, fallback to static list if dynamic fetch fails
    """
    try:
        if provider == "lmstudio":
            return await _get_lmstudio_models()
        elif provider == "openrouter":
            return await _get_openrouter_models()
        elif provider == "openai":
            # OpenAI doesn't provide dynamic model listing in this implementation
            # Fall back to static list
            return settings.get_available_models("openai")
        else:
            logger.warning(f"Unknown provider: {provider}")
            return []
    except Exception as e:
        logger.warning(f"Failed to fetch dynamic models for {provider}: {e}")
        # Fall back to static configuration
        return settings.get_available_models(provider)


async def _get_lmstudio_models() -> List[str]:
    """Get available models from LMStudio server."""
    try:
        # Create a temporary provider instance to fetch models
        # For localhost instances, we can use an empty API key
        provider = create_provider("lmstudio", api_key="")
        
        # Use the list_models method
        models_data = await provider.list_models()
        
        # Extract model IDs from the response
        model_names = []
        for model in models_data:
            if isinstance(model, dict) and "id" in model:
                model_names.append(model["id"])
        
        if not model_names:
            logger.warning("No models found from LMStudio server, using fallback")
            return settings.get_available_models("lmstudio")
        
        logger.info(f"Found {len(model_names)} models from LMStudio: {model_names}")
        return model_names
        
    except Exception as e:
        logger.warning(f"Failed to fetch LMStudio models: {e}")
        return settings.get_available_models("lmstudio")


async def _get_openrouter_models() -> List[str]:
    """Get available models from OpenRouter API."""
    try:
        # Create a temporary provider instance to fetch models
        provider = create_provider("openrouter")
        
        # Use the list_models method
        models_data = await provider.list_models()
        
        # Extract model IDs from the response
        model_names = []
        for model in models_data:
            if isinstance(model, dict) and "id" in model:
                model_names.append(model["id"])
        
        if not model_names:
            logger.warning("No models found from OpenRouter API, using fallback")
            return settings.get_available_models("openrouter")
        
        logger.info(f"Found {len(model_names)} models from OpenRouter")
        return model_names
        
    except Exception as e:
        logger.warning(f"Failed to fetch OpenRouter models: {e}")
        return settings.get_available_models("openrouter")


async def get_all_dynamic_models() -> Dict[str, List[str]]:
    """
    Get available models for all providers dynamically.
    
    Returns:
        Dictionary mapping provider names to their available models
    """
    results = {}
    
    # Fetch models for all providers concurrently
    tasks = {
        "openai": get_dynamic_models("openai"),
        "openrouter": get_dynamic_models("openrouter"), 
        "lmstudio": get_dynamic_models("lmstudio"),
    }
    
    # Wait for all tasks to complete
    completed = await asyncio.gather(*tasks.values(), return_exceptions=True)
    
    # Process results
    for provider_name, result in zip(tasks.keys(), completed):
        if isinstance(result, Exception):
            logger.warning(f"Failed to fetch models for {provider_name}: {result}")
            results[provider_name] = settings.get_available_models(provider_name)
        else:
            results[provider_name] = result
    
    return results
