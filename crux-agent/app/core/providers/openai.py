"""
OpenAI provider implementation.
"""
import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletionMessageParam
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


class OpenAIProvider(BaseProvider):
    """OpenAI API provider implementation."""
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: int = 60,
        max_retries: int = 3,
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Model name (default: gpt-4o-mini)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
        """
        super().__init__(api_key, model, timeout, max_retries)
        self.client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
        )
        # Response API conversation continuation (o-series only)
        self.current_response_id: Optional[str] = None
    
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
    
    async def complete(
        self,
        *,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        stream: bool = False,
        truncation: Optional[str] = "auto",
        **kwargs: Any,
    ) -> str:
        """
        Generate completion using OpenAI API.
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt
            stream: Whether to stream the response (not supported for o-series models)
            truncation: Truncation strategy ("auto" or "disabled")
            **kwargs: Additional OpenAI-specific parameters
                reasoning_effort: Reasoning effort level for o-series models ("low", "medium", "high")
                reasoning_summary: Whether to include reasoning summary for o-series models (True/False)
            
        Returns:
            Generated text
        """
        try:
            logger.debug(f"Calling OpenAI API with model={self.model}, temperature={temperature}, stream={stream}")
            
            # Use responses API for o-series models (o1, o3, etc.)
            if self.model.lower().startswith('o'):
                if stream:
                    logger.warning("Streaming not supported for o-series models, falling back to non-streaming")
                
                params: Dict[str, Any] = {
                    "model": self.model,
                    "instructions": system_prompt or "",
                    "input": prompt,
                }
                
                # Add reasoning parameters for o-series models
                reasoning_effort = kwargs.pop("reasoning_effort", "high")  # 기본값 설정하고 kwargs에서 제거
                reasoning_summary = kwargs.pop("reasoning_summary", "detailed")  # 기본값 설정하고 kwargs에서 제거
                
                reasoning_dict: Dict[str, Any] = {
                    "effort": reasoning_effort,
                    "summary": reasoning_summary
                }
                
                params["reasoning"] = reasoning_dict
                logger.debug(f"Added reasoning parameters: {reasoning_dict}")
                
                response = await self.client.responses.create(**params)
                
                # Store response ID for Response API continuation (o-series only)
                self.current_response_id = getattr(response, "id", None)
                
                content = getattr(response, "output_text", "")
                
                # Extract and store reasoning summary
                self._extract_and_store_reasoning_summary(response)
                
                if not content:
                    raise ProviderError("Empty response from OpenAI responses API")
                
                logger.debug(f"OpenAI responses API completed, response length: {len(content)}")
                return content
            
            # Use chat completions API for other models
            messages: List[ChatCompletionMessageParam] = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            # Prepare parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": stream,
                "store": True,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            # Note: truncation parameter is not supported by OpenAI chat completions API
            # It's handled internally by the provider if needed
            
            if stream:
                # Handle streaming response
                content = ""
                async for chunk in await self.client.chat.completions.create(**params):
                    if chunk.choices and chunk.choices[0].delta.content:
                        content += chunk.choices[0].delta.content
                
                if not content:
                    raise ProviderError("Empty streaming response from OpenAI")
                
                logger.debug(f"OpenAI streaming completed, response length: {len(content)}")
                return content
            else:
                # Handle non-streaming response
                response = await self.client.chat.completions.create(**params)
                
                content = response.choices[0].message.content
                if content is None:
                    raise ProviderError("Empty response from OpenAI")
                
                logger.debug(f"OpenAI response received, tokens used: {response.usage}")
                return content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise ProviderError(f"OpenAI API error: {str(e)}") from e
        
    # TODO: needed  test
    def _extract_and_store_reasoning_summary(self, response) -> None:
        """Extract and store reasoning summary from responses API response."""
        reasoning_parts = []
        
        try:
            # Check output array for reasoning items
            output_items = getattr(response, "output", [])
            for item in output_items:
                if getattr(item, "type", "") == "reasoning":
                    summary_field = getattr(item, "summary", None)
                    if summary_field:
                        if isinstance(summary_field, list):
                            reasoning_parts.append(" ".join([
                                getattr(seg, "text", str(seg)) for seg in summary_field
                            ]))
                        else:
                            reasoning_parts.append(str(summary_field))
                    
                    # Check for summary_text field (newer API)
                    summary_text = getattr(item, "summary_text", None)
                    if summary_text:
                        reasoning_parts.append(str(summary_text))
        except Exception as e:
            logger.debug(f"Failed to extract reasoning from output array: {e}")
        
        # Check top-level reasoning object if no reasoning found in output
        if not reasoning_parts:
            try:
                reasoning_obj = getattr(response, "reasoning", None)
                if reasoning_obj:
                    summary_field = getattr(reasoning_obj, "summary", None)
                    summary_text_field = getattr(reasoning_obj, "summary_text", None)
                    
                    if summary_field:
                        if isinstance(summary_field, list):
                            reasoning_parts.append(" ".join([
                                getattr(seg, "text", str(seg)) for seg in summary_field
                            ]))
                        else:
                            reasoning_parts.append(str(summary_field))
                    elif summary_text_field:
                        reasoning_parts.append(str(summary_text_field))
            except Exception as e:
                logger.debug(f"Failed to extract reasoning from top-level object: {e}")
        
        # Store the reasoning summary
        self.last_reasoning_summary = "\n".join(reasoning_parts) if reasoning_parts else ""
        
        if self.last_reasoning_summary:
            logger.debug(f"Extracted reasoning summary: {len(self.last_reasoning_summary)} chars")
    
    async def _complete_with_functions_responses_api(
        self,
        *,
        prompt: str,
        functions: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Function calling using OpenAI Responses API for o-series models."""
        try:
            # Convert functions to tools format for Responses API
            tools = []
            for func in functions:
                tools.append({
                    "type": "function",
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                    "strict": func.get("strict", False)
                })
            
            # Add code interpreter tool by default for o-series models
            tools.append({
                "type": "code_interpreter",
                "container": {
                    "type": "auto",
                    "file_ids": []
                }
            })
            
            # Initial parameters
            params: Dict[str, Any] = {
                "model": self.model,
                "instructions": system_prompt or "",
                "input": prompt,
                "tools": tools,
            }
            
            # Add reasoning parameters
            reasoning_effort = kwargs.pop("reasoning_effort", "high")  # 기본값 설정하고 kwargs에서 제거
            reasoning_summary = kwargs.pop("reasoning_summary", "detailed")  # 기본값 설정하고 kwargs에서 제거
            
            reasoning_dict: Dict[str, Any] = {
                "effort": reasoning_effort,
                "summary": reasoning_summary
            }
            
            params["reasoning"] = reasoning_dict
            
            # Debug: Log registered tools
            try:
                logger.info(f"TOOLS_DEBUG: Registered tools for Responses API call: {json.dumps(params['tools'], ensure_ascii=False)}")
            except Exception:
                pass
            
            # Enhanced Function calling loop with 30-iteration limit and error recovery
            max_iterations = 30
            iteration_count = 0
            
            while iteration_count < max_iterations:
                iteration_count += 1
                
                try:
                    response = await self.client.responses.create(**params)
                    
                    # Store response ID for potential conversation continuation
                    self.current_response_id = getattr(response, "id", None)
                    
                    # Extract reasoning summary
                    self._extract_and_store_reasoning_summary(response)
                    
                    # Check for function calls in the response
                    function_calls = []
                    output_items = getattr(response, "output", [])
                    
                    for item in output_items:
                        if hasattr(item, 'type') and getattr(item, 'type') == 'function_call':
                            function_calls.append(item)
                    

                    
                    if function_calls:
                        # Return function calls for execution by calling code (e.g., Professor)
                        # This allows proper function execution and result handling
                        class FunctionResponse:
                            def __init__(self, content: str, function_calls: List[Any]):
                                self.content = content
                                self.function_calls = function_calls
                                self.response_id = getattr(response, "id", None)
                        
                        return FunctionResponse("", function_calls)
                    else:
                        # No function calls - return final response
                        content = getattr(response, "output_text", "")
                        
                        if not content:
                            # Try to extract content from output items
                            for item in output_items:
                                if hasattr(item, 'type') and getattr(item, 'type') == 'message':
                                    for content_item in getattr(item, 'content', []):
                                        if hasattr(content_item, 'type') and getattr(content_item, 'type') == 'output_text':
                                            content += getattr(content_item, 'text', '')
                        
                        if not content:
                            raise ProviderError("Empty response from OpenAI responses API")
                        

                        
                        # Return compatible response format
                        class FunctionResponse:
                            def __init__(self, content: str, function_calls: List[Any]):
                                self.content = content
                                self.function_calls = function_calls
                        
                        return FunctionResponse(content, [])
                
                except Exception as e:
                    logger.error(f"Error in function calling iteration {iteration_count}: {e}")
                    
                    # Try to return any partial content from previous iterations
                    if iteration_count > 1 and 'response' in locals():
                        partial_content = getattr(response, "output_text", "")
                        if partial_content:
                            logger.info(f"Returning partial content after error in iteration {iteration_count}")
                            return type('FunctionResponse', (), {
                                'content': partial_content,
                                'function_calls': []
                            })()
                    
                    # Re-raise if no partial content available
                    raise ProviderError(f"Function calling failed in iteration {iteration_count}: {str(e)}") from e
            
            # Exceeded max iterations - return last available content or error
            logger.warning(f"Function calling exceeded maximum iterations ({max_iterations})")
            
            final_content = getattr(locals().get('response'), "output_text", "") if 'response' in locals() else ""
            if final_content:
                return type('FunctionResponse', (), {'content': final_content, 'function_calls': []})()
            else:
                raise ProviderError(f"Function calling exceeded maximum iterations ({max_iterations})")
        
        except Exception as e:
            logger.error(f"OpenAI Responses API function calling error: {e}")
            raise ProviderError(f"OpenAI Responses API function calling error: {str(e)}") from e
    
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
            logger.debug(f"Calling OpenAI API with functions, model={self.model}, temperature={temperature}")
            
            # o-series models use Responses API for function calling
            if self.model.lower().startswith('o'):
                logger.debug("Using Responses API for function calling with o-series model")
                return await self._complete_with_functions_responses_api(
                    prompt=prompt,
                    functions=functions,
                    system_prompt=system_prompt,
                    **kwargs
                )
            
            # Use chat completions API with functions
            messages: List[ChatCompletionMessageParam] = []
            
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            messages.append({"role": "user", "content": prompt})
            
            # Prepare parameters with functions
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "tools": [{"type": "function", "function": func} for func in functions],
                "tool_choice": "auto",  # Let the model decide when to use functions
                "store": True,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            response = await self.client.chat.completions.create(**params)
            
            # Parse response and extract function calls
            choice = response.choices[0]
            message = choice.message
            
            # Create response object
            class FunctionResponse:
                def __init__(self, content: str, function_calls: List[Any]):
                    self.content = content
                    self.function_calls = function_calls
            
            function_calls = []
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.type == "function":
                        # Use retry wrapper for parsing function arguments
                        arguments = self._with_json_retry(
                            json.loads, tool_call.function.arguments
                        )
                        function_calls.append(type('FunctionCall', (), {
                            'name': tool_call.function.name,
                            'arguments': arguments
                        })())
            
            content = message.content or ""
            
            logger.debug(f"OpenAI function calling completed, {len(function_calls)} function calls")
            
            return FunctionResponse(content, function_calls)
            
        except Exception as e:
            logger.error(f"OpenAI function calling error: {e}")
            raise ProviderError(f"OpenAI function calling error: {str(e)}") from e
    
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
        Generate JSON completion using OpenAI API.
        
        Uses JSON mode to ensure valid JSON output with built-in retry resilience:
        - Automatically retries on JSON parsing failures (json.JSONDecodeError)
        - Retries on provider errors during completion
        - Fetches fresh responses on each retry attempt for better success rate
        - Maximum retry attempts controlled by max_retries parameter
        - Uses exponential backoff with random jitter (1-5 seconds)
        
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
        # Ensure system prompt includes JSON instruction
        json_system_prompt = (
            f"{system_prompt or ''}\n\n"
            "You must respond with valid JSON only. Do not include any text outside the JSON object."
        ).strip()
        
        # Use JSON mode if available (GPT-4 Turbo and newer)
        if self.model in ["gpt-4-turbo-preview", "gpt-4o", "gpt-4o-mini"]:
            kwargs["response_format"] = {"type": "json_object"}
        
        async def _complete_and_parse_json() -> Dict[str, Any]:
            """
            Fetch a fresh response and attempt JSON parsing.
            This function will be retried if JSON parsing fails.
            """
            # Get a fresh response on each attempt
            response = await self.complete(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=json_system_prompt,
                truncation=truncation,
                **kwargs,
            )
            
            # Parse the JSON response
            return json.loads(response)
        
        try:
            # Use the retry wrapper for both completion and JSON parsing
            return await self._with_json_retry_async(_complete_and_parse_json)
                
        except Exception as e:
            logger.error(f"JSON completion error: {e}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens using tiktoken for accurate estimation.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Token count
        """
        try:
            import tiktoken
            
            # Get encoding for the model
            if self.model.startswith("gpt-4"):
                encoding = tiktoken.encoding_for_model("gpt-4")
            else:
                encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
            
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Failed to use tiktoken, falling back to estimation: {e}")
            # Fallback to base estimation
            return super().count_tokens(text)

    async def continue_conversation(
        self,
        follow_up: str,
        **kwargs: Any,
    ) -> str:
        """
        Continue an existing conversation using stored response ID.
        Overrides base class to implement OpenAI-specific conversation continuation.
        
        Args:
            follow_up: Follow-up message
            **kwargs: Additional parameters
            
        Returns:
            Generated response
        """
        if not self.current_response_id:
            # No existing conversation, start new one
            logger.warning("No existing response_id - falling back to new conversation")
            return await self.complete(prompt=follow_up, **kwargs)

        # Use o-series models with Responses API for conversation continuation
        if self.model.lower().startswith('o'):
            try:
                # Continue conversation with previous_response_id
                params: Dict[str, Any] = {
                    "model": self.model,
                    "input": follow_up,
                    "previous_response_id": self.current_response_id,
                }

                # Add reasoning parameters for o-series models
                reasoning_effort = kwargs.pop("reasoning_effort", "high")
                reasoning_summary = kwargs.pop("reasoning_summary", "detailed")
                
                reasoning_dict: Dict[str, Any] = {
                    "effort": reasoning_effort,
                    "summary": reasoning_summary
                }
                params["reasoning"] = reasoning_dict

                response = await self.client.responses.create(**params)
                
                # Update response ID for further continuation
                self.current_response_id = getattr(response, "id", None)
                
                content = getattr(response, "output_text", "")
                
                # Extract and store reasoning summary
                self._extract_and_store_reasoning_summary(response)
                
                if not content:
                    raise ProviderError("Empty response from OpenAI conversation continuation")
                
                logger.debug(f"OpenAI conversation continuation completed, response length: {len(content)}")
                return content

            except Exception as e:
                logger.error(f"Conversation continuation failed: {e}")
                # Fallback to new conversation
                self.current_response_id = None
                return await self.complete(prompt=follow_up, **kwargs)
        else:
            # For non-o-series models, fallback to regular completion
            logger.warning("Conversation continuation not supported for non-o-series models, starting new conversation")
            self.current_response_id = None
            return await self.complete(prompt=follow_up, **kwargs)

    async def continue_function_calling(
        self,
        function_outputs: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        """
        Continue Response API conversation after function calling execution.
        This is used to continue the conversation after function calls are executed.
        
        Args:
            function_outputs: Results from executed function calls
            **kwargs: Additional parameters
            
        Returns:
            Generated response continuing the conversation
        """
        if not self.current_response_id:
            raise ProviderError("No response ID available for function calling continuation")

        if not self.model.lower().startswith('o'):
            raise ProviderError("Function calling continuation only supported for o-series models")

        try:
            # Continue conversation with function results using Response API
            params: Dict[str, Any] = {
                "model": self.model,
                "input": function_outputs,
                "previous_response_id": self.current_response_id,
            }

            # Add reasoning parameters for o-series models
            reasoning_effort = kwargs.pop("reasoning_effort", "high")
            reasoning_summary = kwargs.pop("reasoning_summary", "detailed")
            
            reasoning_dict: Dict[str, Any] = {
                "effort": reasoning_effort,
                "summary": reasoning_summary
            }
            params["reasoning"] = reasoning_dict

            response = await self.client.responses.create(**params)
            
            # Update response ID for further continuation
            self.current_response_id = getattr(response, "id", None)
            
            content = getattr(response, "output_text", "")
            
            # Extract and store reasoning summary
            self._extract_and_store_reasoning_summary(response)
            
            if not content:
                raise ProviderError("Empty response from function calling continuation")
            
            logger.debug(f"Function calling continuation completed, response length: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"Function calling continuation failed: {e}")
            raise ProviderError(f"Function calling continuation failed: {str(e)}") from e 