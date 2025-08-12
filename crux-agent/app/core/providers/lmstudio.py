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

from app.core.providers.base import (
    BaseProvider,
    ProviderError,
    TimeoutError,
    RateLimitError,
    get_current_job_id,
)
from app.settings import settings
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
        # Lazy async Redis client for generation locks
        self._redis_client = None
        # TTL slightly longer than request timeout to avoid stale locks (cap at 2h)
        base_timeout = timeout if timeout is not None else settings.lmstudio_timeout
        self._gen_lock_ttl = max(60, min(7200, int(base_timeout) + 30))
        
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
    
    async def _get_redis(self):
        """Get or create an async Redis client."""
        if self._redis_client is None:
            try:
                import redis.asyncio as redis
                self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            except Exception as e:
                logger.error(f"Failed to initialize Redis client for LMStudioProvider: {e}")
                self._redis_client = None
        return self._redis_client

    async def _acquire_generation_lock(self, job_id: str) -> bool:
        """Attempt to acquire a generation lock for a job_id. Returns True on success."""
        redis_client = await self._get_redis()
        if not redis_client:
            # If Redis unavailable, proceed without lock
            logger.warning("Redis unavailable; proceeding without generation lock")
            return True
        lock_key = f"job:{job_id}:gen_lock"
        try:
            # NX + EX to acquire lock only if not exists with TTL
            acquired = await redis_client.set(lock_key, "1", ex=self._gen_lock_ttl, nx=True)
            if acquired:
                logger.info(f"[GenLock] Acquired lock for job_id={job_id} ttl={self._gen_lock_ttl}s")
                return True
            logger.info(f"[GenLock] Lock already held for job_id={job_id}; skipping duplicate generation")
            return False
        except Exception as e:
            logger.error(f"[GenLock] Error acquiring lock for job_id={job_id}: {e}")
            # Fail-open to avoid hard failure; proceed without lock
            return True

    async def _release_generation_lock(self, job_id: str) -> None:
        """Release the generation lock for a job_id if held."""
        redis_client = await self._get_redis()
        if not redis_client:
            return
        lock_key = f"job:{job_id}:gen_lock"
        try:
            await redis_client.delete(lock_key)
            logger.info(f"[GenLock] Released lock for job_id={job_id}")
        except Exception as e:
            logger.error(f"[GenLock] Error releasing lock for job_id={job_id}: {e}")
    
    async def _wait_for_generation_lock_release(self, job_id: str, timeout_s: Optional[int] = None) -> None:
        """Wait briefly for an existing generation lock to be released instead of returning empty output."""
        redis_client = await self._get_redis()
        if not redis_client:
            return
        lock_key = f"job:{job_id}:gen_lock"
        # Default wait up to 10s but never exceed lock TTL
        max_wait = min(self._gen_lock_ttl, int(timeout_s) if timeout_s is not None else 10)
        if max_wait <= 0:
            return
        try:
            import asyncio as _asyncio
            waited = 0.0
            interval = 0.5
            while waited < max_wait:
                try:
                    exists = await redis_client.exists(lock_key)
                except Exception:
                    # If we cannot check, fail-open
                    break
                if not exists:
                    break
                await _asyncio.sleep(interval)
                waited += interval
        except Exception as e:
            logger.warning(f"[GenLock] Error while waiting for lock release job_id={job_id}: {e}")
    
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
            job_id = get_current_job_id()
            acquired = False
            if job_id:
                acquired = await self._acquire_generation_lock(job_id)
                if not acquired:
                    # Wait for in-flight generation to complete
                    logger.warning(f"[GenLock] Lock held for job_id={job_id}; waiting up to 30s before aborting")
                    await self._wait_for_generation_lock_release(job_id, timeout_s=30)
                    # Attempt to acquire once more; if still held, abort to prevent duplicate request
                    acquired = await self._acquire_generation_lock(job_id)
                    if not acquired:
                        logger.warning(f"[GenLock] Lock still held for job_id={job_id}; aborting request to prevent duplicate generation")
                        raise ProviderError(f"Generation locked for job_id={job_id}")

            # Ensure we release the lock after generation or on error
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
                    except json.JSONDecodeError:
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

                    message_dict = data["choices"][0]
                    message = message_dict.get("message", {})
                    content = message.get("content", "")

                    # Capture finish_reason to set truncation flag
                    finish_reason = message_dict.get("finish_reason")
                    truncated = bool(finish_reason and str(finish_reason).lower() not in ("stop", "eosfound"))
                    self.last_truncated = truncated

                    # Handle reasoning content if available (LMStudio reasoning separation feature)
                    reasoning_content = message.get("reasoning_content", "")
                    if reasoning_content:
                        # Store reasoning summary for later access
                        self.last_reasoning_summary = reasoning_content
                        # Calculate reasoning tokens from content
                        self.last_reasoning_tokens = self.count_tokens(reasoning_content)
                        logger.debug(f"Captured reasoning content: {len(reasoning_content)} chars, {self.last_reasoning_tokens} tokens")
                    else:
                        # Fallback: extract reasoning from <think>, <thinking>, or <reasoning> tags
                        import re
                        tag_pattern = re.compile(r"<(?:think|thinking|reasoning)[^>]*>(.*?)</(?:think|thinking|reasoning)>", re.IGNORECASE | re.DOTALL)
                        matches = tag_pattern.findall(content or "")
                        if matches:
                            extracted = "\n".join(m.strip() for m in matches)
                            self.last_reasoning_summary = extracted
                            self.last_reasoning_tokens = self.count_tokens(extracted)
                            logger.debug(f"Extracted reasoning from tags: {self.last_reasoning_tokens} tokens")
                        else:
                            self.last_reasoning_summary = ""
                            self.last_reasoning_tokens = 0

                    # Extract reasoning tokens from usage if available (alternative approach)
                    if isinstance(data, dict) and "usage" in data:
                        usage = data["usage"]
                        logger.debug(f"LMStudio usage: {usage}")

                        # Check for reasoning tokens in usage details
                        if isinstance(usage, dict) and "reasoning_tokens" in usage:
                            self.last_reasoning_tokens = usage["reasoning_tokens"]
                            logger.debug(f"Extracted reasoning tokens from usage: {self.last_reasoning_tokens}")
                        elif isinstance(usage, dict) and "completion_tokens_details" in usage:
                            details = usage["completion_tokens_details"]
                            if isinstance(details, dict) and "reasoning_tokens" in details:
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

            finally:
                if job_id and acquired:
                    await self._release_generation_lock(job_id)
        except Exception as e:
            logger.error(f"LMStudio API error: {e}")
            raise ProviderError(f"LMStudio API error: {str(e)}") from e
    
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
        Generate a response with tool/function calling using LMStudio's OpenAI-compatible API.
        Mirrors OpenAI-style tools/tool_calls format so ProfessorAgent and others can use specialists.
        """
        try:
            job_id = get_current_job_id()
            acquired = False
            if job_id:
                acquired = await self._acquire_generation_lock(job_id)
                if not acquired:
                    logger.warning(f"[GenLock] Lock held for job_id={job_id}; waiting up to 30s before aborting (functions)")
                    await self._wait_for_generation_lock_release(job_id, timeout_s=30)
                    acquired = await self._acquire_generation_lock(job_id)
                    if not acquired:
                        logger.warning(f"[GenLock] Lock still held for job_id={job_id}; aborting function-call request to prevent duplicate generation")
                        raise ProviderError(f"Generation locked for job_id={job_id}")
            try:
                # Build messages
                messages: List[Dict[str, Any]] = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                # OpenAI-compatible tools payload
                tools_payload = [{"type": "function", "function": func} for func in functions]

                payload: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "tools": tools_payload,
                    "tool_choice": "auto",
                    "stream": False,
                }
                if max_tokens:
                    payload["max_tokens"] = max_tokens
                payload.update(kwargs)

                response = await self._make_request(
                    "POST",
                    self.base_url,
                    json=payload,
                    headers=self._get_headers(),
                )

                def parse_function_response(resp):
                    data = resp.json()
                    if "choices" not in data or not data["choices"]:
                        # Check for error shape
                        if isinstance(data, dict) and "error" in data:
                            err = data["error"]
                            err_msg = err if isinstance(err, str) else err.get("message", str(err))
                            raise ProviderError(f"LMStudio API error: {err_msg}")
                        raise ProviderError("Invalid response format from LMStudio")

                    choice = data["choices"][0]
                    message = choice.get("message", {})
                    content = message.get("content", "") or ""

                    # Reasoning capture: prefer explicit reasoning_content, else fallback to tags
                    self.last_reasoning_summary = ""
                    self.last_reasoning_tokens = 0

                    reasoning_content = message.get("reasoning_content", "")
                    if isinstance(reasoning_content, str) and reasoning_content.strip():
                        self.last_reasoning_summary = reasoning_content
                        self.last_reasoning_tokens = self.count_tokens(reasoning_content)
                    else:
                        # Fallback: extract from <think>/<thinking>/<reasoning> tags in content
                        import re
                        tag_pattern = re.compile(r"<(?:think|thinking|reasoning)[^>]*>(.*?)</(?:think|thinking|reasoning)>", re.IGNORECASE | re.DOTALL)
                        matches = tag_pattern.findall(content or "")
                        if matches:
                            extracted = "\n".join(m.strip() for m in matches)
                            self.last_reasoning_summary = extracted
                            self.last_reasoning_tokens = self.count_tokens(extracted)

                    # Also consider usage metadata if present
                    usage = data.get("usage")
                    if isinstance(usage, dict):
                        if "reasoning_tokens" in usage:
                            self.last_reasoning_tokens = usage["reasoning_tokens"]
                        elif "completion_tokens_details" in usage and isinstance(usage["completion_tokens_details"], dict):
                            det = usage["completion_tokens_details"]
                            if "reasoning_tokens" in det:
                                self.last_reasoning_tokens = det["reasoning_tokens"]

                    # Build function call response objects
                    class FunctionCall:
                        def __init__(self, name: str, arguments: Any):
                            self.name = name
                            self.arguments = arguments

                    class FunctionResponse:
                        def __init__(self, content: str, function_calls: List[Any]):
                            self.content = content
                            self.function_calls = function_calls

                    function_calls: List[Any] = []

                    # New tool_calls format
                    if message.get("tool_calls"):
                        for tool_call in message["tool_calls"]:
                            if isinstance(tool_call, dict) and tool_call.get("type") == "function" and tool_call.get("function"):
                                fn = tool_call["function"]
                                name = fn.get("name") if isinstance(fn, dict) else None
                                raw_args = fn.get("arguments", {}) if isinstance(fn, dict) else {}

                                parsed_args: Dict[str, Any] = {}
                                if isinstance(raw_args, str):
                                    try:
                                        parsed_args = self._with_json_retry(json.loads, raw_args)
                                    except Exception:
                                        parsed_args = {}
                                elif isinstance(raw_args, dict):
                                    parsed_args = raw_args

                                if name:
                                    function_calls.append(FunctionCall(name=name, arguments=parsed_args))

                    # Legacy function_call format
                    elif message.get("function_call"):
                        fc = message["function_call"]
                        if isinstance(fc, dict):
                            name = fc.get("name")
                            raw_args = fc.get("arguments", {})
                            parsed_args: Dict[str, Any] = {}
                            if isinstance(raw_args, str):
                                try:
                                    parsed_args = self._with_json_retry(json.loads, raw_args)
                                except Exception:
                                    parsed_args = {}
                            elif isinstance(raw_args, dict):
                                parsed_args = raw_args
                            if name:
                                function_calls.append(FunctionCall(name=name, arguments=parsed_args))

                    return FunctionResponse(content=content, function_calls=function_calls)

                # Use resilient JSON parsing wrapper
                return self._with_json_retry(parse_function_response, response)

            finally:
                if job_id and acquired:
                    await self._release_generation_lock(job_id)
        except Exception as e:
            logger.error(f"LMStudio function-calling error: {e}")
            # Fallback: try regular completion and return with no function calls
            try:
                text = await self.complete(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    stream=False,
                    **kwargs,
                )

                class FunctionResponseFallback:
                    def __init__(self, content: str):
                        self.content = content
                        self.function_calls = []

                return FunctionResponseFallback(content=text)
            except Exception:
                raise ProviderError(f"LMStudio function-calling error: {str(e)}") from e

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
                    # Fallback: extract reasoning from <think>, <thinking>, or <reasoning> tags
                    import re
                    tag_pattern = re.compile(r"<(?:think|thinking|reasoning)[^>]*>(.*?)</(?:think|thinking|reasoning)>", re.IGNORECASE | re.DOTALL)
                    matches = tag_pattern.findall(content or "")
                    if matches:
                        extracted = "\n".join(m.strip() for m in matches)
                        self.last_reasoning_summary = extracted
                        self.last_reasoning_tokens = self.count_tokens(extracted)
                        logger.debug(f"Extracted reasoning from tags: {self.last_reasoning_tokens} tokens")
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
                                content += delta.get("content", "")
                            # Track finish_reason if present (end of stream chunk)
                            if "finish_reason" in data["choices"][0]:
                                finish_reason_stream = data["choices"][0]["finish_reason"]
                                if finish_reason_stream:
                                    last_finish_reason = finish_reason_stream
                    except json.JSONDecodeError:
                        # Skip invalid JSON lines
                        continue
            
            if not content:
                raise ProviderError("Empty streaming response from LMStudio")
            
            # Attempt fallback extraction from <think>/<thinking>/<reasoning> tags inside streamed content
            import re
            tag_pattern = re.compile(r"<(?:think|thinking|reasoning)[^>]*>(.*?)</(?:think|thinking|reasoning)>", re.IGNORECASE | re.DOTALL)
            matches = tag_pattern.findall(content or "")
            if matches:
                extracted = "\n".join(m.strip() for m in matches)
                self.last_reasoning_summary = extracted
                self.last_reasoning_tokens = self.count_tokens(extracted)
                logger.debug(f"Extracted reasoning from tags (stream): {self.last_reasoning_tokens} tokens")
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
