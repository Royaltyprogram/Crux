"""
OpenRouter provider implementation.
"""
import json
from typing import Any, Dict, List, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    RetryCallState,
)

from app.core.providers.base import BaseProvider, ProviderError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OpenRouterProvider(BaseProvider):
    """OpenRouter API provider implementation."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "mistralai/mistral-7b-instruct",
        timeout: int = 60,
        max_retries: int = 3,
        site_url: Optional[str] = None,
        app_name: Optional[str] = None,
    ):
        """
        Initialize OpenRouter provider.
        
        Args:
            api_key: OpenRouter API key
            model: Model identifier (e.g., "mistralai/mistral-7b-instruct")
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            site_url: Your site URL (optional, for better rate limits)
            app_name: Your app name (optional, for analytics)
        """
        super().__init__(api_key, model, timeout, max_retries)
        self.site_url = site_url
        self.app_name = app_name
        self.last_reasoning_tokens = 0
        self.last_reasoning_summary = ""

    def _with_json_retry(self, fn, *args, **kwargs):
        """
        Helper method to perform retries for JSON parsing using tenacity.

        Args:
            fn: The parsing function to retry.
            *args: Positional arguments to pass to the parsing function.
            **kwargs: Keyword arguments to pass to the parsing function.

        Returns:
            The result of the parsing function if successful.

        Raises:
            The last error encountered during retries.
        """
        attempt_count = 0
        
        def before_sleep(retry_state: RetryCallState):
            nonlocal attempt_count
            attempt_count += 1
            if retry_state.outcome and retry_state.outcome.failed:
                error = retry_state.outcome.exception()
                error_type = type(error).__name__
                error_msg = str(error)
                logger.warning(
                    f"JSON retry - method: _with_json_retry, "
                    f"attempt: {attempt_count}/{self.max_retries}, "
                    f"error_type: {error_type}, "
                    f"error: {error_msg}"
                )
                logger.debug(
                    f"Retrying JSON parsing in {retry_state.next_action.sleep if retry_state.next_action else 0:.2f}s"
                )

        @retry(
            retry=retry_if_exception_type((json.JSONDecodeError, ProviderError)),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_random_exponential(min=1, max=5),
            before_sleep=before_sleep,
            reraise=True
        )
        def retry_func():
            return fn(*args, **kwargs)

        return retry_func()
    
    async def _with_json_retry_async(self, fn, *args, **kwargs):
        """
        Async version of helper method to perform retries for JSON parsing using tenacity.

        Args:
            fn: The async parsing function to retry.
            *args: Positional arguments to pass to the parsing function.
            **kwargs: Keyword arguments to pass to the parsing function.

        Returns:
            The result of the parsing function if successful.

        Raises:
            The last error encountered during retries.
        """
        attempt_count = 0
        
        def before_sleep(retry_state: RetryCallState):
            nonlocal attempt_count
            attempt_count += 1
            if retry_state.outcome and retry_state.outcome.failed:
                error = retry_state.outcome.exception()
                error_type = type(error).__name__
                error_msg = str(error)
                logger.warning(
                    f"Async JSON retry - method: _with_json_retry_async, "
                    f"attempt: {attempt_count}/{self.max_retries}, "
                    f"error_type: {error_type}, "
                    f"error: {error_msg}"
                )
                logger.debug(
                    f"Retrying async JSON parsing in {retry_state.next_action.sleep if retry_state.next_action else 0:.2f}s"
                )

        @retry(
            retry=retry_if_exception_type((json.JSONDecodeError, ProviderError)),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_random_exponential(min=1, max=5),
            before_sleep=before_sleep,
            reraise=True
        )
        async def retry_func():
            return await fn(*args, **kwargs)

        return await retry_func()
    
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers including authentication and optional metadata."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Add optional headers for better rate limits and analytics
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
            
        return headers
    
    async def complete(
        self,
        *,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        stream: bool = False, #not supported yet
        truncation: Optional[str] = "auto",
        **kwargs: Any,
    ) -> str:
        """
        Generate completion using OpenRouter API.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt
            stream: Whether to stream the response
            truncation: Truncation strategy ("auto" or "disabled")
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream,
        }
        # Ensure reasoning and usage tracking are enabled by default unless caller overrides
        payload.setdefault("reasoning", {"effort": "high"})
        payload.setdefault("usage", {"include": True})
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        # Add truncation parameter for continuation support
        if truncation:
            payload["truncation"] = truncation
            
        # Add any additional parameters
        payload.update(kwargs)
        
        async def _make_request_and_parse():
            """Make API request and parse response. This will be retried on JSON errors."""
            logger.debug(f"Calling OpenRouter API with model={self.model}")
            
            response = await self._make_request(
                "POST",
                self.BASE_URL,
                json=payload,
                headers=self._get_headers(),
            )
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                # Log the raw response content for debugging
                raw_content = response.text[:500] + "..." if len(response.text) > 500 else response.text
                logger.warning(f"JSON parsing failed. Raw response preview: {raw_content}")
                raise
            
            if "choices" not in data or not data["choices"]:
                raise ProviderError("Invalid response format from OpenRouter")
            
            content = data["choices"][0]["message"]["content"]
            
            # Extract and track reasoning tokens
            self.last_reasoning_tokens = 0
            self.last_reasoning_summary = ""
            
            # Check for reasoning content in the message
            message = data["choices"][0]["message"]
            if "reasoning_content" in message and message["reasoning_content"]:
                reasoning_content = message["reasoning_content"]
                self.last_reasoning_summary = reasoning_content
                # Estimate reasoning tokens (rough approximation: 1 token ≈ 4 characters)
                self.last_reasoning_tokens = max(1, len(reasoning_content) // 4)
                logger.debug(f"OpenRouter reasoning content found, estimated {self.last_reasoning_tokens} reasoning tokens")
            
            # Check for reasoning tokens in usage metadata
            # If usage missing, fetch it via /generation/<id> endpoint (OpenRouter feature)
            if "usage" not in data and "id" in data:
                gen_id = data["id"]
                try:
                    usage_resp = await self._make_request(
                        "GET",
                        f"https://openrouter.ai/api/v1/generation/{gen_id}",
                        headers=self._get_headers(),
                    )
                    usage_data = usage_resp.json()
                    if "usage" in usage_data:
                        data["usage"] = usage_data["usage"]
                        logger.debug(f"Fetched usage for gen {gen_id}: {data['usage']}")
                except Exception as fetch_err:
                    logger.warning(f"Failed to fetch usage info for generation {gen_id}: {fetch_err}")
            if "usage" in data:
                usage = data["usage"]
                logger.debug(f"OpenRouter usage: {usage}")
                
                # Look for reasoning tokens in usage (various possible field names)
                # New: check nested completion_tokens_details.reasoning_tokens per OpenRouter docs
                reasoning_tokens_from_usage = (
                    usage.get("reasoning_tokens", 0) or
                    usage.get("reasoning_completion_tokens", 0) or
                    usage.get("cached_reasoning_tokens", 0) or
                    usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                )
                
                if reasoning_tokens_from_usage > 0:
                    self.last_reasoning_tokens = reasoning_tokens_from_usage
                    logger.debug(f"OpenRouter reasoning tokens from usage: {reasoning_tokens_from_usage}")
                # Fallback: if provider did not supply explicit reasoning tokens, approximate using completion_tokens
                elif self.last_reasoning_tokens == 0 and usage.get("completion_tokens"):
                    self.last_reasoning_tokens = usage.get("completion_tokens")
                    logger.debug(f"Approximated reasoning tokens using completion_tokens: {self.last_reasoning_tokens}")
            
            return content

        try:
            # Use the retry wrapper for the entire request and parsing process
            return await self._with_json_retry_async(_make_request_and_parse)
            
        except Exception as e:
            logger.error(f"OpenRouter API error: {e}")
            raise ProviderError(f"OpenRouter API error: {str(e)}") from e
    
    async def complete_json(
        self,
        *,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        truncation: Optional[str] = "auto",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate JSON completion using OpenRouter API.
        
        Includes built-in retry resilience for JSON parsing:
        - Automatically retries on JSON parsing failures (json.JSONDecodeError)
        - Retries on provider errors during completion
        - Fetches fresh responses on each retry attempt for better success rate
        - Maximum retry attempts controlled by max_retries parameter
        - Uses exponential backoff with random jitter (1-5 seconds)
        - Attempts to extract JSON from partial responses when possible
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt
            truncation: Truncation strategy ("auto" or "disabled")
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON object
            
        Raises:
            json.JSONDecodeError: If JSON parsing fails after all retries
            ProviderError: If API request fails after all retries
        """
        # Modify prompt to ensure JSON output
        json_prompt = f"{prompt}\n\nRespond with valid JSON only."
        
        # Add JSON instruction to system prompt
        json_system_prompt = (
            f"{system_prompt or ''}\n\n"
            "You must respond with valid JSON only. Do not include any text outside the JSON object."
        ).strip()
        
        def _attempt_json_parse(response: str) -> Dict[str, Any]:
            """
            Attempt to parse a JSON string.
            """
            response = response.strip()

            # Find JSON boundaries
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
            else:
                # Try array format
                start_idx = response.find("[")
                end_idx = response.rfind("]") + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                else:
                    json_str = response

            return json.loads(json_str)

        async def _complete_and_parse_json() -> Dict[str, Any]:
            """
            Fetch a fresh response and attempt JSON parsing.
            This function will be retried if JSON parsing fails.
            """
            # Get a fresh response on each attempt
            response = await self.complete(
                prompt=json_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=json_system_prompt,
                truncation=truncation,
                **kwargs,
            )
            
            # Parse the JSON response
            return _attempt_json_parse(response)

        try:
            # Use the retry wrapper for both completion and JSON parsing
            return await self._with_json_retry_async(_complete_and_parse_json)
        except Exception as e:
            logger.error(f"JSON completion error: {e}")
            raise

    async def complete_with_functions(
        self,
        *,
        prompt: str,
        functions: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """
        Generate completion with function calling capability.
        
        Note: Function calling support varies by model on OpenRouter.
        Falls back to regular generation if not supported.
        
        Args:
            prompt: User prompt
            functions: List of available functions
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt
            **kwargs: Additional parameters
            
        Returns:
            Response object with content and possible function calls
        """
        try:
            logger.debug(f"Attempting function calling with OpenRouter model={self.model}")
            
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            # Prepare parameters with functions
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "tools": [{"type": "function", "function": func} for func in functions],
                "tool_choice": "auto",
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
            
            # Add any additional parameters
            payload.update(kwargs)
            
            try:
                response = await self._make_request(
                    "POST",
                    self.BASE_URL,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                def parse_function_response(response):
                    data = response.json()
                    
                    if "choices" not in data or not data["choices"]:
                        raise ProviderError("Invalid response format from OpenRouter")
                    
                    # Parse response and extract function calls
                    choice = data["choices"][0]
                    message = choice["message"]
                    
                    # Create response object
                    class FunctionResponse:
                        def __init__(self, content: str, function_calls: List[Any]):
                            self.content = content
                            self.function_calls = function_calls
                    
                    function_calls = []
                    if "tool_calls" in message and message["tool_calls"]:
                        for tool_call in message["tool_calls"]:
                            if tool_call["type"] == "function":
                                # Use retry helper for parsing function arguments
                                arguments = self._with_json_retry(
                                    json.loads, tool_call["function"]["arguments"]
                                )
                                function_calls.append(type('FunctionCall', (), {
                                    'name': tool_call["function"]["name"],
                                    'arguments': arguments
                                })())
                    
                    content = message.get("content", "")
                    
                    logger.debug(f"OpenRouter function calling completed, {len(function_calls)} function calls")
                    
                    return FunctionResponse(content, function_calls)

                # Use the retry wrapper for JSON parsing  
                return self._with_json_retry(parse_function_response, response)
                
            except Exception as e:
                logger.warning(f"Function calling failed, falling back to regular generation: {e}")
                
                # Fallback to regular generation
                fallback_response = await self.complete(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    **kwargs
                )
                
                # Return as if it were a function response with no function calls
                class FunctionResponse:
                    def __init__(self, content: str, function_calls: List[Any]):
                        self.content = content
                        self.function_calls = function_calls
                
                return FunctionResponse(fallback_response, [])
                
        except Exception as e:
            logger.error(f"OpenRouter function calling error: {e}")
            raise ProviderError(f"OpenRouter function calling error: {str(e)}") from e

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models from OpenRouter.
        
        Returns:
            List of model information
        """
        try:
            response = await self._make_request(
                "GET",
                "https://openrouter.ai/api/v1/models",
                headers=self._get_headers(),
            )
            
            def parse_models_response(response):
                data = response.json()
                return data.get("data", [])

            # Use the retry wrapper for JSON parsing
            return self._with_json_retry(parse_models_response, response)
            
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            raise ProviderError(f"Failed to list models: {str(e)}") from e
