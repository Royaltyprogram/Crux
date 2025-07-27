"""
Application settings using Pydantic BaseSettings for environment variable management.
"""
from typing import Optional
from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Application
    app_name: str = Field(default="crux-agent", description="Application name")
    env: str = Field(default="development", description="Environment (development/staging/production)")
    debug: bool = Field(default=False, description="Debug mode")
    
    # API Settings
    api_v1_str: str = Field(default="/api/v1", description="API version prefix")
    
    # LLM Provider Settings
    llm_provider: str = Field(default="openai", env="LLM_PROVIDER", description="LLM provider to use")
    model_openai: str = Field(default="o4-mini", description="OpenAI model name")
    model_openrouter: str = Field(default="nous-hermes-3b", description="OpenRouter model name")
    openai_models: str = Field(default="o4-mini,o3", env="OPENAI_MODELS", description="Available OpenAI models (comma-separated)")
    openrouter_models: str = Field(default="deepseek/deepseek-r1-0528:free,qwen/qwen3-235b-a22b-2507:free,x-ai/grok-4", env="OPENROUTER_MODELS", description="Available OpenRouter models (comma-separated)")
    openai_api_key: Optional[SecretStr] = Field(default=None, description="OpenAI API key")
    openrouter_api_key: Optional[SecretStr] = Field(default=None, description="OpenRouter API key")
    
    # Redis & Celery
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/0", description="Celery broker URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", description="Celery result backend")
    
    # Self-Evolve Settings
    max_iters: int = Field(default=6, ge=1, le=10, description="Maximum iterations for basic mode (Professor level)")
    
    # Enhanced Mode Settings
    specialist_max_iters: int = Field(default=6, ge=1, le=8, description="Maximum iterations for specialists in enhanced mode")
    professor_max_iters: int = Field(default=3, ge=1, le=10, description="Maximum iterations for professor in enhanced mode")
    
    # Advanced Features Settings
    max_function_call_iterations: int = Field(default=30, ge=1, le=50, description="Maximum function call iterations to prevent infinite loops")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json/plain)")
    
    # CORS Configuration
    cors_origins: str = Field(default="http://localhost:3000", description="CORS allowed origins (comma-separated)")
    
    # Provider-specific settings
    openai_max_retries: int = Field(default=3, description="Maximum retries for OpenAI API calls")
    openai_timeout: Optional[int] = Field(default=None, description="Timeout for OpenAI API calls in seconds (None = no timeout)")
    openrouter_max_retries: int = Field(default=3, description="Maximum retries for OpenRouter API calls")
    openrouter_timeout: int = Field(default=900, description="Timeout for OpenRouter API calls in seconds (15 minutes)")
    
    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider is supported."""
        supported = ["openai", "openrouter"]
        if v not in supported:
            raise ValueError(f"LLM provider must be one of {supported}")
        return v
    
    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        """Validate environment name."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    def get_llm_api_key(self) -> str:
        """Get the API key for the configured LLM provider."""
        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            return self.openai_api_key.get_secret_value()
        elif self.llm_provider == "openrouter":
            if not self.openrouter_api_key:
                raise ValueError("OpenRouter API key not configured")
            return self.openrouter_api_key.get_secret_value()
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
    
    def get_model_name(self) -> str:
        """Get the model name for the configured LLM provider."""
        if self.llm_provider == "openai":
            return self.model_openai
        elif self.llm_provider == "openrouter":
            return self.model_openrouter
        else:
            raise ValueError(f"Unknown LLM provider: {self.llm_provider}")
    
    def get_available_models(self, provider: str = None) -> list[str]:
        """Get available models for a provider."""
        provider = provider or self.llm_provider
        if provider == "openai":
            return [model.strip() for model in self.openai_models.split(",")]
        elif provider == "openrouter":
            return [model.strip() for model in self.openrouter_models.split(",")]
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")


# Global settings instance
settings = Settings() 