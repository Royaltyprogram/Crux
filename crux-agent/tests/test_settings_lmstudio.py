"""
Integration tests for settings with LMStudio support.

Tests the settings module's ability to handle LMStudio configuration properly.
"""
import pytest
from unittest.mock import patch

from app.settings import Settings


class TestLMStudioSettings:
    """Test LMStudio-related settings functionality."""

    def test_lmstudio_provider_validation(self):
        """Test that LMStudio is accepted as a valid provider."""
        settings = Settings(llm_provider="lmstudio")
        assert settings.llm_provider == "lmstudio"

    def test_lmstudio_models_parsing(self):
        """Test that LMStudio models are properly parsed from comma-separated string."""
        settings = Settings(
            lmstudio_models="phi-3-mini-4k-instruct,mistral-7b-instruct,llama-2-7b-chat"
        )
        models = settings.get_available_models("lmstudio")
        expected_models = ["phi-3-mini-4k-instruct", "mistral-7b-instruct", "llama-2-7b-chat"]
        assert models == expected_models

    def test_lmstudio_models_whitespace_handling(self):
        """Test that whitespace in model names is properly handled."""
        settings = Settings(
            lmstudio_models=" phi-3-mini-4k-instruct , mistral-7b-instruct , llama-2-7b-chat "
        )
        models = settings.get_available_models("lmstudio")
        expected_models = ["phi-3-mini-4k-instruct", "mistral-7b-instruct", "llama-2-7b-chat"]
        assert models == expected_models

    def test_lmstudio_single_model(self):
        """Test LMStudio with single model configuration."""
        settings = Settings(lmstudio_models="phi-3-mini-4k-instruct")
        models = settings.get_available_models("lmstudio")
        assert models == ["phi-3-mini-4k-instruct"]

    def test_lmstudio_empty_models(self):
        """Test LMStudio with empty models configuration."""
        settings = Settings(lmstudio_models="")
        models = settings.get_available_models("lmstudio")
        assert models == [""]  # Empty string results in one empty element

    def test_get_model_name_lmstudio(self):
        """Test that get_model_name returns correct model for LMStudio provider."""
        settings = Settings(
            llm_provider="lmstudio",
            model_lmstudio="phi-3-mini-4k-instruct"
        )
        assert settings.get_model_name() == "phi-3-mini-4k-instruct"

    def test_lmstudio_api_key_optional(self):
        """Test that LMStudio API key is optional and returns empty string when not set."""
        settings = Settings(
            llm_provider="lmstudio",
            lmstudio_api_key=None
        )
        api_key = settings.get_llm_api_key()
        assert api_key == ""

    def test_lmstudio_api_key_when_set(self):
        """Test that LMStudio API key is returned when set."""
        from pydantic import SecretStr
        
        settings = Settings(
            llm_provider="lmstudio",
            lmstudio_api_key=SecretStr("test-api-key")
        )
        api_key = settings.get_llm_api_key()
        assert api_key == "test-api-key"

    def test_lmstudio_timeout_settings(self):
        """Test LMStudio-specific timeout and retry settings."""
        settings = Settings(
            lmstudio_timeout=300,
            lmstudio_max_retries=5
        )
        assert settings.lmstudio_timeout == 300
        assert settings.lmstudio_max_retries == 5

    def test_available_providers_includes_lmstudio(self):
        """Test that LMStudio is included in available providers through validation."""
        # This tests the field validator that checks supported providers
        settings = Settings(llm_provider="lmstudio")
        # If this doesn't raise a ValueError, then lmstudio is in the supported list
        assert settings.llm_provider == "lmstudio"

    def test_lmstudio_provider_switching(self):
        """Test switching between different providers including LMStudio."""
        # Test OpenAI provider
        openai_settings = Settings(
            llm_provider="openai",
            model_openai="gpt-4"
        )
        assert openai_settings.get_model_name() == "gpt-4"
        
        # Test LMStudio provider
        lmstudio_settings = Settings(
            llm_provider="lmstudio", 
            model_lmstudio="mistral-7b-instruct"
        )
        assert lmstudio_settings.get_model_name() == "mistral-7b-instruct"
        
        # Test OpenRouter provider
        openrouter_settings = Settings(
            llm_provider="openrouter",
            model_openrouter="nous-hermes-3b"
        )
        assert openrouter_settings.get_model_name() == "nous-hermes-3b"

    def test_lmstudio_models_with_special_characters(self):
        """Test LMStudio models with special characters in names."""
        settings = Settings(
            lmstudio_models="phi-3-mini-4k-instruct,model-v2.1-beta,test_model_123"
        )
        models = settings.get_available_models("lmstudio")
        expected_models = ["phi-3-mini-4k-instruct", "model-v2.1-beta", "test_model_123"]
        assert models == expected_models

    def test_settings_defaults_include_lmstudio(self):
        """Test that default settings include reasonable LMStudio configuration."""
        settings = Settings()
        
        # Check that default LMStudio models are set
        lmstudio_models = settings.get_available_models("lmstudio")
        assert len(lmstudio_models) > 0
        assert "phi-3-mini-4k-instruct" in lmstudio_models
        
        # Check default model
        assert settings.model_lmstudio == "phi-3-mini-4k-instruct"
        
        # Check default timeout and retry settings
        assert settings.lmstudio_timeout == 600  # 10 minutes
        assert settings.lmstudio_max_retries == 3

    def test_invalid_provider_rejected(self):
        """Test that invalid providers are rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(llm_provider="invalid-provider")
        
        assert "LLM provider must be one of" in str(exc_info.value)
        assert "lmstudio" in str(exc_info.value)

    def test_lmstudio_configuration_complete(self):
        """Test a complete LMStudio configuration."""
        from pydantic import SecretStr
        
        settings = Settings(
            llm_provider="lmstudio",
            model_lmstudio="phi-3-mini-4k-instruct",
            lmstudio_models="phi-3-mini-4k-instruct,mistral-7b-instruct",
            lmstudio_api_key=SecretStr("test-key"),
            lmstudio_timeout=300,
            lmstudio_max_retries=5
        )
        
        # Verify all settings
        assert settings.llm_provider == "lmstudio"
        assert settings.get_model_name() == "phi-3-mini-4k-instruct"
        assert settings.get_llm_api_key() == "test-key"
        assert settings.lmstudio_timeout == 300
        assert settings.lmstudio_max_retries == 5
        
        # Verify available models
        models = settings.get_available_models("lmstudio")
        assert models == ["phi-3-mini-4k-instruct", "mistral-7b-instruct"]

    def test_get_available_models_explicit_provider(self):
        """Test get_available_models with explicit provider parameter."""
        settings = Settings(
            llm_provider="openai",  # Different from the provider we're querying
            lmstudio_models="phi-3-mini-4k-instruct,mistral-7b-instruct"
        )
        
        # Should return LMStudio models even though current provider is OpenAI
        models = settings.get_available_models("lmstudio")
        assert models == ["phi-3-mini-4k-instruct", "mistral-7b-instruct"]

    def test_openai_flex_mode_settings(self):
        """Test OpenAI flex mode settings are properly configured."""
        settings = Settings(
            service_tier="flex",
            reasoning_effort="high"
        )
        
        assert settings.service_tier == "flex"
        assert settings.reasoning_effort == "high"
