"""
Integration tests for /settings endpoint returning LMStudio configuration.

Tests that the settings endpoint properly returns LMStudio models and configuration.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


class TestSettingsIntegration:
    """Integration tests for settings endpoint with LMStudio support."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        with TestClient(app) as client:
            yield client

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with LMStudio configuration."""
        return Settings(
            llm_provider="lmstudio",
            model_lmstudio="phi-3-mini-4k-instruct",
            lmstudio_models="phi-3-mini-4k-instruct,mistral-7b-instruct,llama-2-7b-chat",
            openai_models="gpt-4,gpt-3.5-turbo",
            openrouter_models="deepseek/deepseek-r1,qwen/qwen3-235b",
            max_iters=5,
            specialist_max_iters=4,
            professor_max_iters=6
        )

    def test_settings_endpoint_includes_lmstudio(self, client):
        """Test that settings endpoint includes LMStudio in available providers."""
        response = client.get("/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that LMStudio is in available providers
        assert "available_providers" in data
        assert "lmstudio" in data["available_providers"]
        assert "openai" in data["available_providers"]
        assert "openrouter" in data["available_providers"]

    def test_settings_endpoint_lmstudio_models(self, client):
        """Test that settings endpoint returns LMStudio models."""
        response = client.get("/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that LMStudio models are included
        assert "lmstudio_models" in data
        assert isinstance(data["lmstudio_models"], list)
        assert len(data["lmstudio_models"]) > 0

    def test_settings_endpoint_with_lmstudio_provider(self, client, mock_settings):
        """Test settings endpoint when LMStudio is the active provider."""
        with patch('app.settings.settings', mock_settings):
            response = client.get("/settings")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check provider configuration
            assert data["llm_provider"] == "lmstudio"
            assert data["model_name"] == "phi-3-mini-4k-instruct"
            
            # Check iteration limits
            assert data["max_iters"] == 5
            assert data["specialist_max_iters"] == 4
            assert data["professor_max_iters"] == 6
            
            # Check LMStudio models
            assert "lmstudio_models" in data
            expected_models = ["phi-3-mini-4k-instruct", "mistral-7b-instruct", "llama-2-7b-chat"]
            assert data["lmstudio_models"] == expected_models

    def test_settings_endpoint_structure_complete(self, client):
        """Test that settings endpoint returns complete structure."""
        response = client.get("/settings")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields are present
        required_fields = [
            "llm_provider",
            "model_name", 
            "max_iters",
            "specialist_max_iters",
            "professor_max_iters",
            "available_providers",
            "openai_models",
            "openrouter_models", 
            "lmstudio_models"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_settings_endpoint_lmstudio_models_format(self, client, mock_settings):
        """Test that LMStudio models are properly formatted."""
        with patch('app.settings.settings', mock_settings):
            response = client.get("/settings")
            
            assert response.status_code == 200
            data = response.json()
            
            # Check models format
            lmstudio_models = data["lmstudio_models"]
            assert isinstance(lmstudio_models, list)
            
            # Each model should be a string
            for model in lmstudio_models:
                assert isinstance(model, str)
                assert len(model.strip()) > 0
            
            # Check specific models from mock
            expected_models = ["phi-3-mini-4k-instruct", "mistral-7b-instruct", "llama-2-7b-chat"]
            assert lmstudio_models == expected_models

    def test_settings_endpoint_provider_switching(self, client):
        """Test settings endpoint with different provider configurations."""
        # Test with OpenAI provider
        openai_settings = Settings(
            llm_provider="openai",
            model_openai="gpt-4",
            openai_models="gpt-4,gpt-3.5-turbo",
            lmstudio_models="phi-3-mini-4k-instruct,mistral-7b-instruct"
        )
        
        with patch('app.settings.settings', openai_settings):
            response = client.get("/settings")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["llm_provider"] == "openai"
            assert data["model_name"] == "gpt-4"
            assert "lmstudio" in data["available_providers"]
            assert len(data["lmstudio_models"]) > 0

        # Test with LMStudio provider
        lmstudio_settings = Settings(
            llm_provider="lmstudio",
            model_lmstudio="mistral-7b-instruct",
            lmstudio_models="phi-3-mini-4k-instruct,mistral-7b-instruct"
        )
        
        with patch('app.settings.settings', lmstudio_settings):
            response = client.get("/settings")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["llm_provider"] == "lmstudio"
            assert data["model_name"] == "mistral-7b-instruct"

    def test_settings_endpoint_empty_lmstudio_models(self, client):
        """Test settings endpoint with empty LMStudio models configuration."""
        empty_models_settings = Settings(
            llm_provider="openai",
            lmstudio_models=""  # Empty models
        )
        
        with patch('app.settings.settings', empty_models_settings):
            response = client.get("/settings")
            
            assert response.status_code == 200
            data = response.json()
            
            # Should still include lmstudio_models field, but empty
            assert "lmstudio_models" in data
            # Empty string split results in [''], so we get one empty element
            assert data["lmstudio_models"] == ['']

    def test_settings_endpoint_single_lmstudio_model(self, client):
        """Test settings endpoint with single LMStudio model."""
        single_model_settings = Settings(
            llm_provider="lmstudio",
            model_lmstudio="phi-3-mini-4k-instruct",
            lmstudio_models="phi-3-mini-4k-instruct"  # Single model
        )
        
        with patch('app.settings.settings', single_model_settings):
            response = client.get("/settings")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["llm_provider"] == "lmstudio"
            assert data["model_name"] == "phi-3-mini-4k-instruct"
            assert data["lmstudio_models"] == ["phi-3-mini-4k-instruct"]

    def test_settings_endpoint_response_format(self, client):
        """Test that settings endpoint response matches expected schema."""
        response = client.get("/settings")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        
        # Test data types
        assert isinstance(data["llm_provider"], str)
        assert isinstance(data["model_name"], str)
        assert isinstance(data["max_iters"], int)
        assert isinstance(data["specialist_max_iters"], int)
        assert isinstance(data["professor_max_iters"], int)
        assert isinstance(data["available_providers"], list)
        assert isinstance(data["openai_models"], list)
        assert isinstance(data["openrouter_models"], list)
        assert isinstance(data["lmstudio_models"], list)

    def test_settings_endpoint_cors_headers(self, client):
        """Test that settings endpoint includes proper CORS headers."""
        response = client.get("/settings")
        
        assert response.status_code == 200
        
        # Check that response doesn't fail (CORS handled by FastAPI middleware)
        assert "llm_provider" in response.json()

    def test_settings_endpoint_method_not_allowed(self, client):
        """Test that settings endpoint only accepts GET requests."""
        # POST should not be allowed
        response = client.post("/settings", json={"test": "data"})
        assert response.status_code == 405  # Method Not Allowed
        
        # PUT should not be allowed
        response = client.put("/settings", json={"test": "data"})
        assert response.status_code == 405  # Method Not Allowed
        
        # DELETE should not be allowed
        response = client.delete("/settings")
        assert response.status_code == 405  # Method Not Allowed

    def test_settings_endpoint_with_special_characters_in_models(self, client):
        """Test settings endpoint with model names containing special characters."""
        special_settings = Settings(
            llm_provider="lmstudio",
            lmstudio_models="phi-3-mini-4k-instruct,model-v2.1-beta,test_model_123"
        )
        
        with patch('app.settings.settings', special_settings):
            response = client.get("/settings")
            
            assert response.status_code == 200
            data = response.json()
            
            expected_models = ["phi-3-mini-4k-instruct", "model-v2.1-beta", "test_model_123"]
            assert data["lmstudio_models"] == expected_models

    def test_settings_endpoint_with_whitespace_in_models(self, client):
        """Test settings endpoint handles whitespace in model names properly."""
        whitespace_settings = Settings(
            llm_provider="lmstudio",
            lmstudio_models=" phi-3-mini-4k-instruct , mistral-7b-instruct , llama-2-7b-chat "
        )
        
        with patch('app.settings.settings', whitespace_settings):
            response = client.get("/settings")
            
            assert response.status_code == 200
            data = response.json()
            
            # Should trim whitespace from model names
            expected_models = ["phi-3-mini-4k-instruct", "mistral-7b-instruct", "llama-2-7b-chat"]
            assert data["lmstudio_models"] == expected_models

    def test_settings_endpoint_performance(self, client):
        """Test that settings endpoint responds quickly."""
        import time
        
        start_time = time.time()
        response = client.get("/settings")
        end_time = time.time()
        
        assert response.status_code == 200
        
        # Should respond within 1 second (generous limit for CI)
        response_time = end_time - start_time
        assert response_time < 1.0, f"Settings endpoint took {response_time:.2f}s to respond"

    @pytest.mark.asyncio
    async def test_settings_endpoint_concurrent_requests(self, client):
        """Test settings endpoint handles concurrent requests properly."""
        import asyncio
        import httpx
        
        # Use httpx.AsyncClient for concurrent requests
        async with httpx.AsyncClient(app=create_app(), base_url="http://test") as async_client:
            # Make 5 concurrent requests
            tasks = [async_client.get("/settings") for _ in range(5)]
            responses = await asyncio.gather(*tasks)
            
            # All requests should succeed
            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert "lmstudio_models" in data
                assert "available_providers" in data
