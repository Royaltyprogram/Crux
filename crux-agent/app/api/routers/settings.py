"""
Settings endpoints to expose current configuration.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.settings import settings


router = APIRouter(
    prefix="/settings",
    tags=["settings"],
)


class SettingsResponse(BaseModel):
    """Response containing current settings."""
    
    llm_provider: str
    model_name: str
    max_iters: int
    specialist_max_iters: int
    professor_max_iters: int
    available_providers: list[str] = ["openai", "openrouter"]
    openai_models: list[str]
    openrouter_models: list[str]


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """
    Get current system settings.
    
    Returns current configuration including model provider, iteration limits, etc.
    """
    return SettingsResponse(
        llm_provider=settings.llm_provider,
        model_name=settings.get_model_name(),
        max_iters=settings.max_iters,
        specialist_max_iters=settings.specialist_max_iters,
        professor_max_iters=settings.professor_max_iters,
        openai_models=settings.get_available_models("openai"),
        openrouter_models=settings.get_available_models("openrouter"),
    )
