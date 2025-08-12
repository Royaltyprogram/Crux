"""
OpenRouter provider implementation.
"""
import json
from typing import Any, Dict, List, Optional, Tuple
import re
import ast
from datetime import datetime

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    RetryCallState,
)

from app.core.providers.base import BaseProvider, ProviderError, get_current_job_id
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
            wait=wait_random_exponential(min=0.2, max=2),
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
            wait=wait_random_exponential(min=0.2, max=2),
            before_sleep=before_sleep,
            reraise=True
        )
        async def retry_func():
            return await fn(*args, **kwargs)

        return await retry_func()
    
    def _persist_raw_response_to_redis(self, raw_text: str, reason: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """Persist the raw provider response to Redis under the current job hash.
        
        Stores two fields on the job hash if job_id context is present:
        - openrouter_last_raw_response: the raw response body (string)
        - openrouter_last_raw_meta: JSON with meta like model, reason, timestamp, and extras
        """
        try:
            job_id = get_current_job_id()
            if not job_id:
                return
            # Lazy import to avoid hard dependency during module import
            import redis  # type: ignore
            from app.settings import settings
            r = redis.from_url(settings.redis_url, decode_responses=True)
            r.hset(f"job:{job_id}", "openrouter_last_raw_response", raw_text or "")
            meta: Dict[str, Any] = {
                "model": self.model,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            if extra and isinstance(extra, dict):
                try:
                    meta.update(extra)
                except Exception:
                    pass
            r.hset(f"job:{job_id}", "openrouter_last_raw_meta", json.dumps(meta))
        except Exception as _e:
            # Never fail primary flow due to diagnostics
            logger.debug(f"Failed to persist raw OpenRouter response: {_e}")

    def _persist_parse_mode_to_redis(self, mode: str) -> None:
        """Persist the parse mode used for function-calling (strict/tolerant/fallback)."""
        try:
            job_id = get_current_job_id()
            if not job_id:
                return
            # Lazy import to avoid hard dependency during module import
            import redis  # type: ignore
            from app.settings import settings
            r = redis.from_url(settings.redis_url, decode_responses=True)
            r.hset(f"job:{job_id}", "openrouter_parse_mode", mode)
        except Exception as _e:
            logger.debug(f"Failed to persist OpenRouter parse mode: {_e}")

    def _relaxed_parse_arguments(self, raw: Any) -> Tuple[Dict[str, Any], str]:
        """Attempt to parse function-call arguments with relaxed strategies.
        
        Returns (parsed_dict, note). note describes which strategy succeeded or 'failed'.
        """
        if isinstance(raw, dict):
            return raw, "dict"
        if not isinstance(raw, str):
            return {}, "failed:not_string"
        s = raw.strip()
        # 1) Strict JSON first
        try:
            return json.loads(s), "json"
        except Exception:
            pass
        # 2) Remove trailing commas
        try:
            s2 = re.sub(r",\s*([}\]])", r"\1", s)
            return json.loads(s2), "json:trailing_commas_removed"
        except Exception:
            pass
        # 3) Replace single quotes with double quotes
        try:
            s3 = s2 if 's2' in locals() else s
            s3 = s3.replace("'", '"')
            return json.loads(s3), "json:single_quotes_swapped"
        except Exception:
            pass
        # 4) Python literal eval
        try:
            obj = ast.literal_eval(s)
            if isinstance(obj, dict):
                return obj, "ast.literal_eval"
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                return obj[0], "ast.literal_eval:list_first_dict"
        except Exception:
            pass
        return {}, "failed"

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers including authentication and optional metadata."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            # Hint providers to return aggregated JSON for non-streaming requests
            "Accept": "application/json",
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
        stream: bool = True,
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

            def _log_info_summary(src: str, content_text: str, usage: Optional[Dict[str, Any]] = None):
                """Emit a concise INFO summary: model, stream mode, usage tokens, reasoning tokens, preview."""
                try:
                    import re
                    compact_reason = re.sub(r"\s+", " ", (self.last_reasoning_summary or "")).strip()
                    reason_preview = (compact_reason[:500] + "...") if len(compact_reason) > 500 else compact_reason
                    pt = ct = tt = rt = None
                    if usage:
                        pt = usage.get("prompt_tokens") or usage.get("input_tokens")
                        ct = usage.get("completion_tokens") or usage.get("output_tokens")
                        tt = usage.get("total_tokens")
                        rt = (
                            usage.get("reasoning_tokens") or
                            usage.get("reasoning_completion_tokens") or
                            usage.get("cached_reasoning_tokens") or
                            (usage.get("completion_tokens_details", {}) or {}).get("reasoning_tokens")
                        )
                    logger.info(
                        f"OpenRouter summary model={self.model} stream={payload.get('stream', False)} src={src} "
                        f"usage(prompt={pt}, completion={ct}, total={tt}, reasoning={rt}) "
                        f"reasoning_tokens={self.last_reasoning_tokens} "
                        f"reasoning_preview(len={len(compact_reason)}): {reason_preview}"
                    )
                except Exception as _e:
                    logger.debug(f"Failed to log provider summary: {_e}")

            # If streaming requested, use SSE stream and aggregate content incrementally
            if payload.get("stream"):
                await self._ensure_client()
                content_parts: List[str] = []
                reasoning_accum: List[str] = []
                try:
                    async with self._client.stream(
                        "POST",
                        self.BASE_URL,
                        headers=self._get_headers(),
                        json=payload,
                    ) as stream_resp:
                        ctype = stream_resp.headers.get("content-type", "")
                        is_sse = "text/event-stream" in ctype or True  # Many providers use SSE for stream

                        async for raw_line in stream_resp.aiter_lines():
                            if not raw_line:
                                continue
                            line = raw_line.strip()
                            # SSE comments start with ':' per spec
                            if line.startswith(":"):
                                continue
                            if not line.lower().startswith("data:"):
                                continue
                            data_part = line[5:].strip()
                            # Skip empty or keepalive heartbeat chunks
                            if not data_part:
                                continue
                            if data_part == "[DONE]":
                                break
                            low = data_part.lower()
                            if low in ("[keepalive]", "keepalive", "[heartbeat]", "heartbeat"):
                                continue
                            # Many providers send only JSON payloads; skip non-JSON data chunks
                            if not (data_part.startswith("{") or data_part.startswith("[")):
                                continue
                            try:
                                evt = json.loads(data_part)
                            except json.JSONDecodeError:
                                # Some providers may chunk JSON across lines; skip partials
                                continue
                            # Standard OpenAI-style streaming schema
                            choices = evt.get("choices") or []
                            for ch in choices:
                                delta = ch.get("delta") or {}
                                piece = delta.get("content") or ""
                                if not piece:
                                    # Some providers send full message objects
                                    msg = ch.get("message") or {}
                                    piece = msg.get("content") or ""
                                    rtxt = msg.get("reasoning") if isinstance(msg.get("reasoning"), str) else None
                                    if rtxt:
                                        reasoning_accum.append(rtxt)
                                # Optional: non-standard fields
                                rtxt2 = delta.get("reasoning") if isinstance(delta.get("reasoning"), str) else None
                                if rtxt2:
                                    reasoning_accum.append(rtxt2)
                                if piece:
                                    content_parts.append(piece)
                                # Detect finish
                                if ch.get("finish_reason"):
                                    # let the loop drain remaining lines
                                    pass
                        # After stream ends, compute reasoning tokens
                        if reasoning_accum:
                            self.last_reasoning_summary = "\n".join(reasoning_accum)
                            self.last_reasoning_tokens = max(1, len(self.last_reasoning_summary) // 4)
                        else:
                            # Approx using generated content
                            generated = "".join(content_parts)
                            self.last_reasoning_tokens = len(generated) // 4 if generated else 0
                        generated = "".join(content_parts)
                        # If stream yielded no content, but we captured reasoning, return reasoning as content
                        if not generated.strip():
                            if reasoning_accum:
                                generated = "\n".join(reasoning_accum)
                                _log_info_summary("stream-reasoning-fallback", generated, None)
                                return generated
                            # Otherwise force fallback to non-stream path
                            raise ProviderError("Empty streamed content from OpenRouter")
                        _log_info_summary("stream", generated, None)
                        return generated
                except Exception as e:
                    logger.warning(f"Streaming parse failed, falling back to non-stream: {e}")
                    # Fall through to non-stream request below

            response = await self._make_request(
                "POST",
                self.BASE_URL,
                json=payload,
                headers=self._get_headers(),
            )
            
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                # If server returned SSE but not in streaming mode, attempt to parse buffered SSE
                ctype = response.headers.get("content-type", "")
                raw_text = response.text or ""
                # Guard: treat blank/whitespace bodies as empty content to avoid noisy retries (log at DEBUG)
                if not raw_text.strip():
                    logger.debug("OpenRouter returned empty/blank response body; raising to trigger retry")
                    raise ProviderError("Empty response body from OpenRouter")
                if "text/event-stream" in ctype or raw_text.strip().startswith("data:"):
                    content_parts: List[str] = []
                    reasoning_accum: List[str] = []
                    for raw_line in raw_text.splitlines():
                        line = raw_line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if not line.lower().startswith("data:"):
                            continue
                        data_part = line[5:].strip()
                        # Skip empty or keepalive heartbeat chunks
                        if not data_part:
                            continue
                        if data_part == "[DONE]":
                            break
                        low = data_part.lower()
                        if low in ("[keepalive]", "keepalive", "[heartbeat]", "heartbeat"):
                            continue
                        # Skip non-JSON data chunks to avoid parsing noise
                        if not (data_part.startswith("{") or data_part.startswith("[")):
                            continue
                        try:
                            evt = json.loads(data_part)
                        except json.JSONDecodeError:
                            continue
                        choices = evt.get("choices") or []
                        for ch in choices:
                            delta = ch.get("delta") or {}
                            piece = delta.get("content") or ""
                            if not piece:
                                msg = ch.get("message") or {}
                                piece = msg.get("content") or ""
                                rtxt = msg.get("reasoning") if isinstance(msg.get("reasoning"), str) else None
                                if rtxt:
                                    reasoning_accum.append(rtxt)
                            rtxt2 = delta.get("reasoning") if isinstance(delta.get("reasoning"), str) else None
                            if rtxt2:
                                reasoning_accum.append(rtxt2)
                            if piece:
                                content_parts.append(piece)
                    if content_parts:
                        if reasoning_accum:
                            self.last_reasoning_summary = "\n".join(reasoning_accum)
                            self.last_reasoning_tokens = max(1, len(self.last_reasoning_summary) // 4)
                        generated = "".join(content_parts)
                        _log_info_summary("sse-buffered", generated, None)
                        return generated
                    # No content parts: if we have reasoning, use it as fallback
                    if reasoning_accum:
                        self.last_reasoning_summary = "\n".join(reasoning_accum)
                        self.last_reasoning_tokens = max(1, len(self.last_reasoning_summary) // 4)
                        generated = self.last_reasoning_summary
                        _log_info_summary("sse-buffered-reasoning-fallback", generated, None)
                        return generated
                # Persist the raw response body for post-mortem and log a preview, then re-raise
                try:
                    self._persist_raw_response_to_redis(
                        response.text or "",
                        reason="json_decode_error",
                        extra={"content_type": response.headers.get("content-type", "")},
                    )
                except Exception:
                    pass
                raw_content = response.text[:500] + "..." if len(response.text) > 500 else response.text
                logger.debug(f"JSON parsing failed. Raw response preview: {raw_content}")
                raise
            
            if "choices" not in data or not data["choices"]:
                raise ProviderError("Invalid response format from OpenRouter")
            
            message_obj = data["choices"][0]["message"]
            content = message_obj["content"]
            # If content empty but reasoning exists, use reasoning as content
            if not (isinstance(content, str) and content.strip()):
                reasoning_text = message_obj.get("reasoning")
                if isinstance(reasoning_text, str) and reasoning_text.strip():
                    content = reasoning_text
                else:
                    # Treat empty content as an error to trigger retry
                    raise ProviderError("Empty content in OpenRouter response")
            
            # Extract and track reasoning tokens
            self.last_reasoning_tokens = 0
            self.last_reasoning_summary = ""
            
            # Prefer explicit reasoning field in OpenRouter spec
            message = data["choices"][0]["message"]
            reasoning_text = message.get("reasoning")
            if isinstance(reasoning_text, str) and reasoning_text.strip():
                self.last_reasoning_summary = reasoning_text
                # Estimate reasoning tokens (rough approximation: 1 token ≈ 4 characters)
                self.last_reasoning_tokens = max(1, len(reasoning_text) // 4)
                logger.debug(f"OpenRouter reasoning field found, estimated {self.last_reasoning_tokens} reasoning tokens")
            else:
                # Optional: Anthropic-style reasoning_details -> try to stringify
                rd = message.get("reasoning_details")
                extracted = ""
                try:
                    if isinstance(rd, dict):
                        content_blocks = rd.get("content")
                        if isinstance(content_blocks, list):
                            parts = []
                            for b in content_blocks:
                                if isinstance(b, dict):
                                    t = b.get("text") or b.get("content")
                                    if isinstance(t, str):
                                        parts.append(t)
                            extracted = "\n".join([p.strip() for p in parts if p])
                    elif isinstance(rd, str):
                        extracted = rd
                except Exception as e:
                    logger.debug(f"Could not parse reasoning_details: {e}")
                if extracted:
                    self.last_reasoning_summary = extracted
                    self.last_reasoning_tokens = max(1, len(extracted) // 4)
                    logger.debug(f"Parsed reasoning_details, estimated {self.last_reasoning_tokens} reasoning tokens")
                else:
                    # Fallback: extract reasoning from <think>, <thinking>, or <reasoning> tags inside regular content
                    import re
                    tag_pattern = re.compile(r"<(?:think|thinking|reasoning)[^>]*>(.*?)</(?:think|thinking|reasoning)>", re.IGNORECASE | re.DOTALL)
                    matches = tag_pattern.findall(content or "")
                    if matches:
                        extracted = "\n".join(m.strip() for m in matches)
                        self.last_reasoning_summary = extracted
                        self.last_reasoning_tokens = max(1, len(extracted) // 4)
                        logger.debug(f"Extracted reasoning from tags, estimated {self.last_reasoning_tokens} reasoning tokens")
            
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
            
            usage_for_log = data.get("usage") if isinstance(data, dict) else None
            _log_info_summary("json", content, usage_for_log)
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
            
            messages: List[Dict[str, Any]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "tools": [{"type": "function", "function": func} for func in functions],
                "tool_choice": "auto",
            }
            # Prefer aggregated JSON for function-calling to avoid SSE/keepalives
            payload["stream"] = False
            if max_tokens:
                payload["max_tokens"] = max_tokens
            payload.update(kwargs)
            
            try:
                response = await self._make_request(
                    "POST",
                    self.BASE_URL,
                    json=payload,
                    headers=self._get_headers(),
                )
                
                def parse_function_response(response):
                    # Try strict JSON first
                    try:
                        data = response.json()
                        # Strict mode succeeded
                        try:
                            self._persist_parse_mode_to_redis("strict")
                        except Exception:
                            pass
                        logger.info("OpenRouter function-calling parse mode: strict")
                    except Exception:
                        # Persist raw for post-mortem
                        try:
                            self._persist_raw_response_to_redis(
                                getattr(response, "text", "") or "",
                                reason="function_json_decode_error",
                                extra={"content_type": response.headers.get("content-type", "")},
                            )
                        except Exception:
                            pass
                        # Tolerant parse: ignore keepalives/SSE markers and collect last valid JSON object
                        txt = getattr(response, "text", "") or ""
                        last_evt = None
                        for line in txt.splitlines():
                            s = line.strip()
                            if not s:
                                continue
                            if s == "[DONE]" or s.lower() in ("[keepalive]", "keepalive", "[heartbeat]", "heartbeat"):
                                continue
                            if s.startswith("data:"):
                                s = s[5:].strip()
                            if not (s.startswith("{") or s.startswith("[")):
                                continue
                            try:
                                evt = json.loads(s)
                                if isinstance(evt, dict) and ("choices" in evt):
                                    last_evt = evt
                            except Exception:
                                continue
                        if last_evt is None:
                            raise ProviderError("Invalid response format from OpenRouter (no JSON payload)")
                        data = last_evt
                        # Tolerant mode used
                        try:
                            self._persist_parse_mode_to_redis("tolerant")
                        except Exception:
                            pass
                        logger.info("OpenRouter function-calling parse mode: tolerant")
                    if "choices" not in data or not data["choices"]:
                        raise ProviderError("Invalid response format from OpenRouter")
                    choice = data["choices"][0]
                    message = choice["message"]
                    
                    # Reasoning extraction
                    self.last_reasoning_summary = ""
                    self.last_reasoning_tokens = 0
                    reasoning_text = message.get("reasoning")
                    if isinstance(reasoning_text, str) and reasoning_text.strip():
                        self.last_reasoning_summary = reasoning_text
                        self.last_reasoning_tokens = max(1, len(reasoning_text) // 4)
                    else:
                        extracted = ""
                        rd = message.get("reasoning_details")
                        try:
                            if isinstance(rd, dict):
                                blocks = rd.get("content")
                                if isinstance(blocks, list):
                                    parts = []
                                    for b in blocks:
                                        if isinstance(b, dict):
                                            t = b.get("text") or b.get("content")
                                            if isinstance(t, str):
                                                parts.append(t)
                                    extracted = "\n".join(p.strip() for p in parts if p)
                            elif isinstance(rd, str):
                                extracted = rd
                        except Exception:
                            pass
                        if not extracted:
                            import re
                            tag_pattern = re.compile(r"<(?:think|thinking|reasoning)[^>]*>(.*?)</(?:think|thinking|reasoning)>", re.IGNORECASE | re.DOTALL)
                            matches = tag_pattern.findall(message.get("content", "") or "")
                            if matches:
                                extracted = "\n".join(m.strip() for m in matches)
                        if extracted:
                            self.last_reasoning_summary = extracted
                            self.last_reasoning_tokens = max(1, len(extracted) // 4)
                    
                    class FunctionResponse:
                        def __init__(self, content: str, function_calls: List[Any]):
                            self.content = content
                            self.function_calls = function_calls
                    
                    function_calls: List[Any] = []
                    # OpenAI-style tool_calls
                    if message.get("tool_calls"):
                        for tool_call in message["tool_calls"]:
                            if tool_call.get("type") == "function" and tool_call.get("function"):
                                fn = tool_call["function"]
                                raw_args = fn.get("arguments", {})
                                parsed_args, note = self._relaxed_parse_arguments(raw_args)
                                if note.startswith("failed"):
                                    # Persist the raw provider response to aid debugging
                                    try:
                                        self._persist_raw_response_to_redis(
                                            getattr(response, "text", "") or "",
                                            reason="function_args_parse_failed",
                                            extra={
                                                "raw_args_preview": (
                                                    (
                                                        (raw_args if isinstance(raw_args, str) else json.dumps(raw_args))[:500]
                                                        + "..."
                                                    )
                                                    if len(raw_args if isinstance(raw_args, str) else json.dumps(raw_args)) > 500
                                                    else (raw_args if isinstance(raw_args, str) else json.dumps(raw_args))
                                                )
                                            },
                                        )
                                    except Exception:
                                        pass
                                elif note != "json":
                                    logger.debug(f"Relaxed parsing used for function args: {note}")
                                function_calls.append(type('FunctionCall', (), {
                                    'name': fn.get("name", ""),
                                    'arguments': parsed_args
                                })())
                    # Legacy function_call
                    elif message.get("function_call"):
                        fc = message["function_call"]
                        raw_args = fc.get("arguments", {})
                        parsed_args, note = self._relaxed_parse_arguments(raw_args)
                        if note.startswith("failed"):
                            try:
                                self._persist_raw_response_to_redis(
                                    getattr(response, "text", "") or "",
                                    reason="function_args_parse_failed",
                                    extra={
                                        "raw_args_preview": (
                                            (
                                                (raw_args if isinstance(raw_args, str) else json.dumps(raw_args))[:500]
                                                + "..."
                                            )
                                            if len(raw_args if isinstance(raw_args, str) else json.dumps(raw_args)) > 500
                                            else (raw_args if isinstance(raw_args, str) else json.dumps(raw_args))
                                        )
                                    },
                                )
                            except Exception:
                                pass
                        elif note != "json":
                            logger.debug(f"Relaxed parsing used for legacy function args: {note}")
                        function_calls.append(type('FunctionCall', (), {
                            'name': fc.get("name", ""),
                            'arguments': parsed_args
                        })())
                    
                    content = message.get("content", "")
                    # If no content but reasoning exists, use reasoning as content
                    if not (isinstance(content, str) and content.strip()):
                        if isinstance(self.last_reasoning_summary, str) and self.last_reasoning_summary.strip():
                            content = self.last_reasoning_summary
                    # If still no content and no function calls, raise to trigger fallback
                    if not (isinstance(content, str) and content.strip()) and not function_calls:
                        raise ProviderError("Empty content in OpenRouter function-calling response")
                    
                    # Usage reasoning tokens
                    usage = data.get("usage", {}) if isinstance(data, dict) else {}
                    rt = (
                        usage.get("reasoning_tokens")
                        or usage.get("reasoning_completion_tokens")
                        or usage.get("cached_reasoning_tokens")
                        or (usage.get("completion_tokens_details", {}) or {}).get("reasoning_tokens")
                        or 0
                    )
                    if isinstance(rt, int) and rt > 0:
                        self.last_reasoning_tokens = rt
                    
                    logger.debug(f"OpenRouter function calling completed, {len(function_calls)} function calls")
                    return FunctionResponse(content, function_calls)
                
                # Do not retry here; tolerant parsing already applied and fallback below handles unsupported cases
                return parse_function_response(response)
            except Exception as e:
                logger.warning(f"Function calling failed, falling back to regular generation: {e}")
                try:
                    self._persist_parse_mode_to_redis("fallback")
                except Exception:
                    pass
                fallback_response = await self.complete(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    **kwargs
                )
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
