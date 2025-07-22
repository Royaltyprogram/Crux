"""
OpenRouter provider implementation.
"""
import json
from typing import Any, Dict, List, Optional

from app.core.providers.base import BaseProvider, ProviderError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class OpenRouterProvider(BaseProvider):
    """OpenRouter API provider implementation."""
    
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    
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
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        # Add truncation parameter for continuation support
        if truncation:
            payload["truncation"] = truncation
            
        # Add any additional parameters
        payload.update(kwargs)
        
        try:
            logger.debug(f"Calling OpenRouter API with model={self.model}")
            
            response = await self._make_request(
                "POST",
                self.BASE_URL,
                json=payload,
                headers=self._get_headers(),
            )
            
            data = response.json()
            
            if "choices" not in data or not data["choices"]:
                raise ProviderError("Invalid response format from OpenRouter")
            
            content = data["choices"][0]["message"]["content"]
            
            # Log usage if available
            if "usage" in data:
                logger.debug(f"OpenRouter usage: {data['usage']}")
            
            return content
            
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
        
        Args:
            prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: System prompt
            truncation: Truncation strategy ("auto" or "disabled")
            **kwargs: Additional parameters
            
        Returns:
            Parsed JSON object
        """
        # Modify prompt to ensure JSON output
        json_prompt = f"{prompt}\n\nRespond with valid JSON only."
        
        # Add JSON instruction to system prompt
        json_system_prompt = (
            f"{system_prompt or ''}\n\n"
            "You must respond with valid JSON only. Do not include any text outside the JSON object."
        ).strip()
        
        try:
            response = await self.complete(
                prompt=json_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=json_system_prompt,
                truncation=truncation,
                **kwargs,
            )
            
            # Try to extract JSON from response
            # Some models might add explanation before/after JSON
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
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {response}")
                raise ProviderError(f"Invalid JSON response: {str(e)}") from e
                
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
                            function_calls.append(type('FunctionCall', (), {
                                'name': tool_call["function"]["name"],
                                'arguments': json.loads(tool_call["function"]["arguments"])
                            })())
                
                content = message.get("content", "")
                
                logger.debug(f"OpenRouter function calling completed, {len(function_calls)} function calls")
                
                return FunctionResponse(content, function_calls)
                
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
            
            data = response.json()
            return data.get("data", [])
            
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            raise ProviderError(f"Failed to list models: {str(e)}") from e 