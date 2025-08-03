"""
LMStudio provider implementation.
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

from app.core.providers.base import BaseProvider, ProviderError, TimeoutError, RateLimitError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LMStudioProvider(BaseProvider):
    """LMStudio API provider implementation."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "local-model",
        timeout: Optional[int] = 60,
        max_retries: int = 3,
        base_url: str = "http://localhost:1234/v1/chat/completions",
    ):
        """
        Initialize LMStudio provider.
        
        Args:
            api_key: LMStudio API key (may not be required for local instances)
            model: Model name to use
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            base_url: LMStudio server base URL (default: local instance)
        """
        super().__init__(api_key, model, timeout, max_retries)
        self.base_url = base_url
        # Track reasoning tokens separately
        self.last_reasoning_tokens: int = 0
        
        # Try to instantiate LMStudio client if available
        self.client = None
        try:
            from lmstudio import AsyncLMStudio
            self.client = AsyncLMStudio(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
                max_retries=max_retries,
            )
            logger.debug("Using official LMStudio SDK")
        except ImportError:
            logger.debug("LMStudio SDK not available, using HTTP client")
    
    def _with_json_retry(self, fn, *args, **kwargs):
        """
        Helper method to perform retries for JSON parsing using tenacity.
        
        Provides resilient JSON parsing with automatic retry on failures:
        - Retries on json.JSONDecodeError and ProviderError
        - Uses exponential backoff with random jitter (1-5 seconds)
        - Maximum attempts controlled by self.max_retries
        - Logs retry attempts for debugging

        Args:
            fn: The parsing function to retry.
            *args: Positional arguments to pass to the parsing function.
            **kwargs: Keyword arguments to pass to the parsing function.

        Returns:
            The result of the parsing function if successful.

        Raises:
            json.JSONDecodeError: If JSON parsing fails after all retries
            ProviderError: If provider error occurs after all retries
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
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers including authentication."""
        headers = {
            "Content-Type": "application/json",
        }
        
        # Add authorization header if API key is provided
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        return headers
    
    async def complete(
        self,
        *,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        stream: bool = True,  # Enable streaming by default for better responsiveness
        **kwargs: Any,
    ) -> str:
        """
        Generate completion using LMStudio API.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt
            stream: Whether to stream the response (fallback to non-stream if not supported)
            **kwargs: Additional LMStudio-specific parameters
            
        Returns:
            Generated text
        """
        try:
            logger.debug(f"Calling LMStudio API with model={self.model}, temperature={temperature}, stream={stream}")
            
            # If official SDK is available, use it
            if self.client:
                return await self._complete_with_sdk(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    stream=stream,
                    **kwargs
                )
            
            # Use HTTP client implementation
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
            
            if max_tokens:
                payload["max_tokens"] = max_tokens
                
            # Add any additional parameters
            payload.update(kwargs)
            
            async def _make_request_and_parse():
                """Make API request and parse response. This will be retried on JSON errors."""
                logger.debug(f"Making request to LMStudio API at {self.base_url}")
                
                response = await self._make_request(
                    "POST",
                    self.base_url,
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
                    # Check if it's an error response
                    if "error" in data:
                        error_info = data["error"]
                        error_msg = error_info if isinstance(error_info, str) else error_info.get("message", str(error_info))
                        logger.error(f"LMStudio API error: {error_msg}")
                        raise ProviderError(f"LMStudio API error: {error_msg}")
                    
                    logger.error(f"Invalid response structure. Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}, Choices: {data.get('choices', 'MISSING')}")
                    raise ProviderError("Invalid response format from LMStudio")
                
                message = data["choices"][0]["message"]
                content = message.get("content", "")
                
                # Handle reasoning content if available (LMStudio reasoning separation feature)
                reasoning_content = message.get("reasoning_content", "")
                if reasoning_content:
                    # Store reasoning summary for later access
                    self.last_reasoning_summary = reasoning_content
                    # Calculate reasoning tokens from content
                    self.last_reasoning_tokens = self.count_tokens(reasoning_content)
                    logger.debug(f"Captured reasoning content: {len(reasoning_content)} chars, {self.last_reasoning_tokens} tokens")
                else:
                    self.last_reasoning_summary = ""
                    self.last_reasoning_tokens = 0
                
                # Extract reasoning tokens from usage if available (alternative approach)
                if "usage" in data:
                    usage = data["usage"]
                    logger.debug(f"LMStudio usage: {usage}")
                    
                    # Check for reasoning tokens in usage details
                    if "reasoning_tokens" in usage:
                        self.last_reasoning_tokens = usage["reasoning_tokens"]
                        logger.debug(f"Extracted reasoning tokens from usage: {self.last_reasoning_tokens}")
                    elif "completion_tokens_details" in usage:
                        details = usage["completion_tokens_details"]
                        if "reasoning_tokens" in details:
                            self.last_reasoning_tokens = details["reasoning_tokens"]
                            logger.debug(f"Extracted reasoning tokens from completion details: {self.last_reasoning_tokens}")
                
                return content

            # Handle streaming if requested and supported
            if stream:
                try:
                    # Try streaming first
                    return await self._handle_streaming_response(payload)
                except (ProviderError, NotImplementedError) as e:
                    logger.warning(f"Streaming not supported, falling back to non-stream: {e}")
                    # Fallback to non-streaming
                    payload["stream"] = False
                    return await self._with_json_retry_async(_make_request_and_parse)
            else:
                # Use the retry wrapper for the entire request and parsing process
                return await self._with_json_retry_async(_make_request_and_parse)
            
        except Exception as e:
            logger.error(f"LMStudio API error: {e}")
            raise ProviderError(f"LMStudio API error: {str(e)}") from e
    
    async def _complete_with_sdk(
        self,
        *,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        Generate completion using official LMStudio SDK if available.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt
            stream: Whether to stream the response
            **kwargs: Additional parameters
            
        Returns:
            Generated text
        """
        try:
            messages = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": stream,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            # Add any additional parameters
            params.update(kwargs)
            
            if stream:
                # Handle streaming response
                content = ""
                stream_response = await self.client.chat.completions.create(**params)
                async for chunk in stream_response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content += chunk.choices[0].delta.content
                
                if not content:
                    raise ProviderError("Empty streaming response from LMStudio")
                
                logger.debug(f"LMStudio streaming completed, response length: {len(content)}")
                return content
            else:
                # Handle non-streaming response
                response = await self.client.chat.completions.create(**params)
                
                message = response.choices[0].message
                content = message.content
                if content is None:
                    raise ProviderError("Empty response from LMStudio")
                
                # Handle reasoning content if available (SDK path)
                reasoning_content = getattr(message, 'reasoning_content', None)
                if reasoning_content:
                    self.last_reasoning_summary = reasoning_content
                    # Calculate reasoning tokens from content
                    self.last_reasoning_tokens = self.count_tokens(reasoning_content)
                    logger.debug(f"Captured reasoning content via SDK: {len(reasoning_content)} chars, {self.last_reasoning_tokens} tokens")
                else:
                    self.last_reasoning_summary = ""
                    self.last_reasoning_tokens = 0
                
                # Extract reasoning tokens from usage if available (SDK path)
                usage = getattr(response, 'usage', None)
                if usage:
                    logger.debug(f"LMStudio response received, tokens used: {usage}")
                    
                    # Check for reasoning tokens in usage details
                    if hasattr(usage, 'reasoning_tokens') and usage.reasoning_tokens:
                        self.last_reasoning_tokens = usage.reasoning_tokens
                        logger.debug(f"Extracted reasoning tokens from SDK usage: {self.last_reasoning_tokens}")
                    elif hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details:
                        details = usage.completion_tokens_details
                        if hasattr(details, 'reasoning_tokens') and details.reasoning_tokens:
                            self.last_reasoning_tokens = details.reasoning_tokens
                            logger.debug(f"Extracted reasoning tokens from SDK completion details: {self.last_reasoning_tokens}")
                else:
                    logger.debug("LMStudio response received, no usage information available")
                return content
                
        except Exception as e:
            logger.error(f"LMStudio SDK error: {e}")
            raise ProviderError(f"LMStudio SDK error: {str(e)}") from e
    
    async def _handle_streaming_response(self, payload: Dict[str, Any]) -> str:
        """
        Handle streaming response from LMStudio API.
        
        Args:
            payload: Request payload
            
        Returns:
            Complete response content
        """
        try:
            response = await self._make_request(
                "POST",
                self.base_url,
                json=payload,
                headers=self._get_headers(),
            )
            
            content = ""
            
            # Process streaming response line by line
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                    
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    
                    if data_str.strip() == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and data["choices"]:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                content += delta["content"]
                    except json.JSONDecodeError:
                        # Skip invalid JSON lines
                        continue
            
            if not content:
                raise ProviderError("Empty streaming response from LMStudio")
            
            logger.debug(f"LMStudio streaming completed, response length: {len(content)}")
            return content
            
        except Exception as e:
            logger.error(f"LMStudio streaming error: {e}")
            raise ProviderError(f"LMStudio streaming error: {str(e)}") from e
    
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
        Generate JSON completion using LMStudio API.
        
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
    
    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Uses tiktoken for better estimation if available, otherwise falls back to
        character-based estimation.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        try:
            import tiktoken
            
            # Use a generic encoding for token estimation
            # LMStudio may use different tokenizers, but this provides a reasonable estimate
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Failed to use tiktoken, falling back to estimation: {e}")
            # Fallback to base estimation (character-based)
            return super().count_tokens(text)
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models from LMStudio server.
        
        Returns:
            List of model information
        """
        try:
            # Extract base URL from the chat completions URL
            if self.base_url.endswith("/chat/completions"):
                models_url = self.base_url.replace("/chat/completions", "/models")
            elif self.base_url.endswith("/v1/chat/completions"):
                models_url = self.base_url.replace("/chat/completions", "/models")
            else:
                # Assume base_url is the base URL
                models_url = f"{self.base_url.rstrip('/')}/v1/models"
            
            logger.debug(f"Fetching models from LMStudio at: {models_url}")
            
            response = await self._make_request(
                "GET",
                models_url,
                headers=self._get_headers(),
            )
            
            def parse_models_response(response):
                data = response.json()
                return data.get("data", [])

            # Use the retry wrapper for JSON parsing
            return self._with_json_retry(parse_models_response, response)
            
        except Exception as e:
            logger.error(f"Failed to list LMStudio models: {e}")
            raise ProviderError(f"Failed to list LMStudio models: {str(e)}") from e
    
    def get_last_reasoning_summary(self) -> str:
        """
        Get the reasoning summary from the most recent API call.
        
        With the "reasoning content separation" feature enabled in LMStudio,
        the reasoning_content field contains the model's internal thinking process.
        
        Returns:
            Reasoning summary from the last API call, or empty string if none available
        """
        return getattr(self, 'last_reasoning_summary', '')
