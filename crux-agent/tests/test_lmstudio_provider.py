"""
Unit tests for LMStudio provider with mocked local server responses.

Tests success, timeout, and rate-limit scenarios for the LMStudioProvider.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.core.providers.lmstudio import LMStudioProvider
from app.core.providers.base import ProviderError, TimeoutError, RateLimitError


class TestLMStudioProvider:
    """Test cases for LMStudio provider with mocked responses."""

    @pytest.fixture
    def provider(self):
        """Create LMStudio provider instance for testing."""
        return LMStudioProvider(
            api_key="test-api-key",
            model="test-model",
            timeout=60,
            max_retries=3,
            base_url="http://localhost:1234/v1/chat/completions"
        )

    @pytest.fixture
    def mock_success_response(self):
        """Mock successful response from LMStudio server."""
        return {
            "choices": [
                {
                    "message": {
                        "content": "This is a successful response from LMStudio local server."
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15,
                "total_tokens": 25
            }
        }

    @pytest.fixture
    def mock_streaming_response(self):
        """Mock streaming response data."""
        return [
            "data: {\"choices\":[{\"delta\":{\"content\":\"This\"}}]}",
            "data: {\"choices\":[{\"delta\":{\"content\":\" is\"}}]}",
            "data: {\"choices\":[{\"delta\":{\"content\":\" a\"}}]}",
            "data: {\"choices\":[{\"delta\":{\"content\":\" streaming\"}}]}",
            "data: {\"choices\":[{\"delta\":{\"content\":\" response\"}}]}",
            "data: [DONE]"
        ]

    @pytest.mark.asyncio
    async def test_complete_success(self, provider, mock_success_response):
        """Test successful completion request."""
        with patch.object(provider, '_make_request') as mock_request:
            # Mock successful HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = mock_success_response
            mock_request.return_value = mock_response

            result = await provider.complete(
                prompt="Test prompt",
                temperature=0.7,
                max_tokens=100,
                system_prompt="You are a helpful assistant"
            )

            assert result == "This is a successful response from LMStudio local server."
            mock_request.assert_called_once()

            # Verify request payload
            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"  # method
            assert call_args[0][1] == provider.base_url  # URL
            
            # Check payload structure
            payload = call_args[1]["json"]
            assert payload["model"] == "test-model"
            assert payload["temperature"] == 0.7
            assert payload["max_tokens"] == 100
            assert len(payload["messages"]) == 2  # system + user message
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_complete_timeout(self, provider):
        """Test timeout handling."""
        with patch.object(provider, '_make_request') as mock_request:
            # Mock timeout exception
            mock_request.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(ProviderError) as exc_info:
                await provider.complete(prompt="Test prompt")

            assert "timeout" in str(exc_info.value).lower() or "LMStudio API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_rate_limit(self, provider):
        """Test rate limit handling."""
        with patch.object(provider, '_make_request') as mock_request:
            # Mock HTTP 429 response
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.text = "Rate limit exceeded"
            
            http_error = httpx.HTTPStatusError(
                "Rate limit exceeded",
                request=MagicMock(),
                response=mock_response
            )
            mock_request.side_effect = http_error

            with pytest.raises(ProviderError) as exc_info:
                await provider.complete(prompt="Test prompt")

            assert "rate limit" in str(exc_info.value).lower() or "LMStudio API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_server_error(self, provider):
        """Test server error handling."""
        with patch.object(provider, '_make_request') as mock_request:
            # Mock HTTP 500 response
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal server error"
            
            http_error = httpx.HTTPStatusError(
                "Internal server error",
                request=MagicMock(),
                response=mock_response
            )
            mock_request.side_effect = http_error

            with pytest.raises(ProviderError) as exc_info:
                await provider.complete(prompt="Test prompt")

            assert "LMStudio API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_invalid_response_format(self, provider):
        """Test handling of invalid response format."""
        with patch.object(provider, '_make_request') as mock_request:
            # Mock response missing choices
            mock_response = MagicMock()
            mock_response.json.return_value = {"error": "Invalid format"}
            mock_request.return_value = mock_response

            with pytest.raises(ProviderError) as exc_info:
                await provider.complete(prompt="Test prompt")

            assert "Invalid response format" in str(exc_info.value) or "LMStudio API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_json_decode_error(self, provider):
        """Test handling of JSON decode errors with retry."""
        with patch.object(provider, '_make_request') as mock_request:
            # Mock response that fails JSON parsing
            mock_response = MagicMock()
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.text = "Invalid JSON response"
            mock_request.return_value = mock_response

            with pytest.raises(ProviderError) as exc_info:
                await provider.complete(prompt="Test prompt")

            assert "LMStudio API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_streaming_success(self, provider, mock_streaming_response):
        """Test successful streaming completion."""
        with patch.object(provider, '_make_request') as mock_request:
            # Mock streaming response
            mock_response = MagicMock()
            
            async def mock_aiter_lines():
                for line in mock_streaming_response:
                    yield line
            
            mock_response.aiter_lines = mock_aiter_lines
            mock_request.return_value = mock_response

            result = await provider.complete(
                prompt="Test prompt",
                stream=True
            )

            assert result == "This is a streaming response"

    @pytest.mark.asyncio
    async def test_complete_streaming_fallback(self, provider, mock_success_response):
        """Test streaming fallback to non-streaming on error."""
        with patch.object(provider, '_make_request') as mock_request:
            # First call (streaming) fails, second call (non-streaming) succeeds
            def side_effect(*args, **kwargs):
                payload = kwargs.get("json", {})
                if payload.get("stream", False):
                    raise ProviderError("Streaming not supported")
                else:
                    mock_response = MagicMock()
                    mock_response.json.return_value = mock_success_response
                    return mock_response
            
            mock_request.side_effect = side_effect

            result = await provider.complete(
                prompt="Test prompt",
                stream=True
            )

            assert result == "This is a successful response from LMStudio local server."
            assert mock_request.call_count == 2  # streaming attempt + fallback

    @pytest.mark.asyncio
    async def test_complete_json_success(self, provider):
        """Test successful JSON completion."""
        json_response = {"result": "success", "data": {"key": "value"}}
        
        with patch.object(provider, 'complete') as mock_complete:
            mock_complete.return_value = json.dumps(json_response)

            result = await provider.complete_json(
                prompt="Generate JSON response",
                temperature=0.0
            )

            assert result == json_response
            mock_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_json_retry_on_invalid_json(self, provider):
        """Test JSON completion retry on invalid JSON with eventual success."""
        json_response = {"result": "success"}
        
        with patch.object(provider, 'complete') as mock_complete:
            # First call returns invalid JSON, second call returns valid JSON
            mock_complete.side_effect = [
                "This is not valid JSON",
                json.dumps(json_response)
            ]

            result = await provider.complete_json(
                prompt="Generate JSON response",
                temperature=0.0
            )

            assert result == json_response
            assert mock_complete.call_count == 2  # retry happened

    @pytest.mark.asyncio
    async def test_complete_json_extract_from_text(self, provider):
        """Test JSON extraction from text response."""
        json_response = {"result": "success"}
        text_with_json = f"Here is the JSON: {json.dumps(json_response)} - end of response"
        
        with patch.object(provider, 'complete') as mock_complete:
            mock_complete.return_value = text_with_json

            result = await provider.complete_json(
                prompt="Generate JSON response",
                temperature=0.0
            )

            assert result == json_response

    def test_count_tokens_fallback(self, provider):
        """Test token counting fallback when tiktoken is not available."""
        # Since tiktoken is not available in test environment, this should use fallback
        count = provider.count_tokens("Hello world")
        # Fallback uses character-based estimation (len / 4)
        assert count == len("Hello world") // 4

    def test_get_last_reasoning_summary(self, provider):
        """Test reasoning summary retrieval (should be empty for LMStudio)."""
        summary = provider.get_last_reasoning_summary()
        assert summary == ""

    def test_get_headers_with_api_key(self, provider):
        """Test header generation with API key."""
        headers = provider._get_headers()
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test-api-key"

    def test_get_headers_without_api_key(self):
        """Test header generation without API key."""
        provider = LMStudioProvider(api_key="", model="test-model")
        headers = provider._get_headers()
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    def test_sdk_not_available(self, provider):
        """Test behavior when SDK is not available (default case)."""
        # In our test environment, SDK is not available, so client should be None
        assert provider.client is None

    @pytest.mark.asyncio
    async def test_retry_logic_with_json_errors(self, provider, mock_success_response):
        """Test retry logic specifically for JSON parsing errors."""
        with patch.object(provider, '_make_request') as mock_request:
            # First call fails with JSON error, second succeeds
            call_count = 0
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                mock_response = MagicMock()
                if call_count == 1:
                    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
                    mock_response.text = "Invalid JSON"
                else:
                    mock_response.json.return_value = mock_success_response
                return mock_response
            
            mock_request.side_effect = side_effect

            result = await provider.complete(prompt="Test prompt")
            
            assert result == "This is a successful response from LMStudio local server."
            assert mock_request.call_count == 2  # retry happened

    def test_provider_initialization_defaults(self):
        """Test provider initialization with default values."""
        provider = LMStudioProvider(api_key="test-key", model="test-model")
        
        assert provider.api_key == "test-key"
        assert provider.model == "test-model"
        assert provider.timeout == 60
        assert provider.max_retries == 3
        assert provider.base_url == "http://localhost:1234/v1/chat/completions"

    def test_provider_initialization_custom_values(self):
        """Test provider initialization with custom values."""
        provider = LMStudioProvider(
            api_key="custom-key",
            model="custom-model",
            timeout=120,
            max_retries=5,
            base_url="http://custom-host:5678/v1/chat/completions"
        )
        
        assert provider.api_key == "custom-key"
        assert provider.model == "custom-model"
        assert provider.timeout == 120
        assert provider.max_retries == 5
        assert provider.base_url == "http://custom-host:5678/v1/chat/completions"
