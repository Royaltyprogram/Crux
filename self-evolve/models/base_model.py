"""
Base model interface for LLM interactions
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import openai
import time
from ..config import ModelConfig
from ..utils.logger import get_logger
from openai import OpenAI

CODE_INTERPRETER_TOOL = {
    "type": "code_interpreter",
    "container": { "type": "auto" }
}

class BaseModel(ABC):
    """Abstract base class for LLM models"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
        # Holds the most recent reasoning summary text (detailed) returned by the model
        self.last_reasoning_summary: str = ""
        self._setup_client()
    
    def _setup_client(self):
        """Setup OpenAI client to use chat completions only"""
        if self.config.api_key:
            openai.api_key = self.config.api_key
        if self.config.api_base:
            openai.api_base = self.config.api_base
        # responses API 관련 클라이언트는 더 이상 사용하지 않음
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response from the model"""
        pass
    
    def _make_api_call(self, messages: list, **kwargs) -> str:
        """Dispatcher that selects between chat completions API (default) and
        the newer responses API which is required for the `o3-pro` model.

        All arguments and retry / continuation logic remain identical from the
        caller's perspective.
        """

        # 먼저 deepseek 계열 모델 여부를 체크하여 전용 호출 경로로 분기
        model_lc = str(self.config.model_name).lower()
        if model_lc.startswith("deepseek") or model_lc.startswith("deepseek-reasoner"):
            return self._make_deepseek_api_call(messages, **kwargs)
        
        # responses API (o3-pro 등) 기본 경로
        try:
            return self._make_response_api_call(messages, **kwargs)
        except Exception as err:
            self.logger.error(f"Responses API call failed: {err}")
            raise

    def _make_response_api_call(self, messages: list, **kwargs) -> str:
        """Dedicated call path for `o3-pro` models using the `responses` API.

        The `responses` endpoint expects `instructions` (equivalent to the
        traditional system prompt) and a single `input` string (the latest user
        prompt).  Optional parameters such as `reasoning` and `truncation`
        (introduced in recent OpenAI updates) are also forwarded when
        provided.  A small retry loop similar to the chat-completions path is
        implemented for robustness.
        """

        client = OpenAI(timeout=self.config.timeout)  # Relies on api_key/api_base already configured via _setup_client

        retry_count = 0
        max_retries = 3

        # Extract the system instruction(s) and last user input
        instructions = "\n".join([m["content"] for m in messages if m["role"] == "system"])
        user_contents = [m["content"] for m in messages if m["role"] == "user"]
        input_text = user_contents[-1] if user_contents else ""
        # Save prompt for logging (include system + user)
        prompt_for_log = f"{instructions}\n{input_text}" if instructions else input_text

        full_response_content = ""
        reasoning_summary_content = ""  # Collect reasoning summary text
        continuation_count = 0
        max_continuation = 5  # maximum automatic follow-up calls

        while True:
            try:
                params: Dict[str, Any] = {
                    "model": self.config.model_name,
                    "instructions": instructions,
                    "input": input_text,
                }

                # ------------------------------------------------------------
                # Optional: include the built-in code execution tool
                # This is disabled by default.  It can be turned on via:
                #   1) Passing enable_code_interpreter=True in **kwargs when
                #      calling generate/evaluate, OR
                #   2) Setting ModelConfig.enable_code_interpreter = True.
                # ------------------------------------------------------------
                if "tools" in kwargs:
                    params["tools"] = kwargs["tools"]
                    if "tool_choice" in kwargs:
                         params["tool_choice"] = kwargs["tool_choice"]
                else:
                    include_code_tool = kwargs.get(
                        "enable_code_interpreter",
                        getattr(self.config, "enable_code_interpreter", False),
                    )

                    if include_code_tool:
                        params["tools"] = [CODE_INTERPRETER_TOOL]
                        # Respect explicit tool_choice in kwargs first, then config
                        params["tool_choice"] = kwargs.get(
                            "tool_choice", getattr(self.config, "tool_choice", "auto")
                        )

                # Attach reasoning parameter (effort / summary) if available
                reasoning_effort = kwargs.get("reasoning_effort", getattr(self.config, "reasoning_effort", None))
                reasoning_summary = kwargs.get("reasoning_summary", getattr(self.config, "reasoning_summary", None))

                reasoning_dict: Dict[str, Any] = {}
                # gpt 계열에서는 reasoning 파라미터 무시
                if not str(self.config.model_name).lower().startswith("gpt"):
                    if reasoning_effort is not None:
                        reasoning_dict["effort"] = reasoning_effort
                    if reasoning_summary is not None:
                        reasoning_dict["summary"] = reasoning_summary

                if reasoning_dict:
                    params["reasoning"] = reasoning_dict

                # Attach truncation parameter ("auto" / "disabled") if provided
                truncation_val = kwargs.get("truncation", getattr(self.config, "truncation", None))
                if truncation_val is not None:
                    params["truncation"] = truncation_val

                # 모델명이 'gpt'로 시작하면 temperature 파라미터를 전달
                if str(self.config.model_name).lower().startswith("gpt"):
                    temperature_val = kwargs.get("temperature", getattr(self.config, "temperature", 0.7))
                    if temperature_val is not None:
                        params["temperature"] = temperature_val

                # Forward any additional kwargs except those we explicitly managed
                for k, v in kwargs.items():
                    if k not in [
                        "temperature",
                        "max_tokens",
                        "max_completion_tokens",
                        "reasoning_effort",
                        "truncation",
                        "tool_choice",
                        "tools",
                        "stream",
                        "enable_code_interpreter",  # Filter out this parameter
                    ]:
                        params[k] = v

                # stream 기본값을 True 로 설정하여 별도 지정이 없더라도 스트리밍으로 동작
                stream_requested = kwargs.get("stream", getattr(self.config, "stream", True))
                if stream_requested:
                    params["stream"] = True
                else:
                    params["stream"] = False

                self.logger.info(
                    f"Calling responses API with model {self.config.model_name}, reasoning_effort={reasoning_effort}, stream={params['stream']}"
                )

                # === 스트리밍 및 비-스트리밍 호출을 분기 ===
                if params["stream"]:
                    # NOTE: stream 플래그는 responses.create 인자로 전달되어야 하므로, pop 사용해 아래 호출 시 확실히 포함
                    stream_flag = params.pop("stream")
                    # 스트림 생성
                    stream_events = client.responses.create(**params, stream=stream_flag)

                    for event in stream_events:
                        event_type = getattr(event, "type", "")

                        # 텍스트 델타 이벤트 수집 (output_text.delta 타입만)
                        if event_type == "response.output_text.delta" and hasattr(event, "delta"):
                            token = str(event.delta)
                            full_response_content += token
                            # 터미널에 즉시 출력하여 진행 상황을 보여줌
                            print(token, end="", flush=True)

                        # === Reasoning summary delta 이벤트 수집 ===
                        if (
                            event_type == "response.reasoning_summary_part.added" and hasattr(event, "part")
                        ):
                            # Legacy event style – part.text may contain the delta
                            reasoning_summary_content += getattr(event.part, "text", str(event.part))

                        # Newer event styles – delta is carried in event.delta, sometimes under different type names
                        if (
                            event_type in (
                                "response.reasoning_summary.delta",
                                "response.reasoning_summary_text.delta",
                                "assistant.reasoning_summary.delta",
                                "assistant.reasoning_summary_text.delta",
                            )
                            and hasattr(event, "delta")
                        ):
                            reasoning_summary_content += getattr(event.delta, "text", str(event.delta))

                        # Handle final reasoning summary "done" events which may contain the full summary text
                        if event_type in (
                            "response.reasoning_summary.done",
                            "response.reasoning_summary_text.done",
                            "assistant.reasoning_summary.done",
                            "assistant.reasoning_summary_text.done",
                        ):
                            summary_piece = None
                            for _attr in ("summary_text", "text", "summary", "content"):
                                if hasattr(event, _attr):
                                    val = getattr(event, _attr)
                                    if isinstance(val, list):
                                        summary_piece = " ".join([
                                            getattr(seg, "text", str(seg)) for seg in val
                                        ])
                                    else:
                                        summary_piece = str(val)
                                    break
                            if summary_piece is None:
                                summary_piece = str(event)
                            reasoning_summary_content += summary_piece

                        # 완료 이벤트 감지
                        if event_type == "response.completed":
                            break  # 전체 응답 완료

                    # 한 줄 개행하여 프롬프트 복원
                    print()

                    # 종료 후 reasoning summary 저장
                    self.last_reasoning_summary = reasoning_summary_content.strip()

                    # 완료 후 로그 기록
                    self._log_interaction(prompt_for_log, full_response_content)
                    return full_response_content

                # ---- 기존 (비-스트리밍) 코드 경로 ----
                response = client.responses.create(**params)
                self.logger.info("Response received from API")

                # ----- Non-streaming: Collect assistant answer text -----
                output_segment = getattr(response, "output_text", "")
                full_response_content += output_segment

                # ----- Non-streaming: Extract reasoning summary if present -----
                current_reasoning_content = ""  # Track reasoning for this response chunk
                try:
                    reasoning_content_parts = []
                    response_output = getattr(response, "output", [])
                    self.logger.debug(f"Non-streaming: Processing {len(response_output)} output items")
                    
                    for item in response_output:
                        if getattr(item, "type", "") == "reasoning":
                            self.logger.debug("Non-streaming: Found reasoning item in output")
                            summary_field = getattr(item, "summary", None)
                            if summary_field:
                                if isinstance(summary_field, list):
                                    reasoning_content_parts.append(" ".join([
                                        getattr(seg, "text", str(seg)) for seg in summary_field
                                    ]))
                                else:
                                    reasoning_content_parts.append(str(summary_field))
                        # New API may include summary_text string instead of summary list
                        if not reasoning_content_parts and hasattr(item, "summary_text"):
                            reasoning_content_parts.append(str(getattr(item, "summary_text")))
                    if reasoning_content_parts:
                        current_reasoning_content = "\n".join(reasoning_content_parts)
                        self.logger.debug(f"Non-streaming: Extracted reasoning from output: {len(current_reasoning_content)} chars")
                except Exception as e:
                    self.logger.debug(f"Failed to extract reasoning content from output: {e}")

                # Fallback: check top-level `reasoning` field (new API schema)
                if not current_reasoning_content:
                    try:
                        reasoning_obj = getattr(response, "reasoning", None)
                        if reasoning_obj is not None:
                            self.logger.debug("Non-streaming: Found reasoning object at top level")
                            summary_field = getattr(reasoning_obj, "summary", None)
                            # Newer schema may use summary_text instead of summary
                            summary_text_field = getattr(reasoning_obj, "summary_text", None)
                            if summary_field:
                                # summary_field may be list of segments or plain string
                                if isinstance(summary_field, list):
                                    current_reasoning_content = " ".join([
                                        getattr(seg, "text", str(seg)) for seg in summary_field
                                    ])
                                else:
                                    current_reasoning_content = str(summary_field)
                                self.logger.debug(f"Non-streaming: Extracted reasoning from top-level: {len(current_reasoning_content)} chars")
                            elif summary_text_field:
                                current_reasoning_content = str(summary_text_field)
                    except Exception as e:
                        self.logger.debug(f"Failed to extract reasoning content from top-level reasoning: {e}")
                
                # Accumulate the reasoning content from this chunk
                if current_reasoning_content:
                    if reasoning_summary_content:
                        reasoning_summary_content += "\n" + current_reasoning_content
                    else:
                        reasoning_summary_content = current_reasoning_content
                    self.logger.debug(f"Non-streaming: Total reasoning content now {len(reasoning_summary_content)} chars")

                response_status = getattr(response, "status", "completed")
                incomplete_details = getattr(response, "incomplete_details", None)
                
                is_truncated = (
                    response_status != "completed"
                    or (incomplete_details is not None)
                )

                if is_truncated and continuation_count < max_continuation:
                    continuation_count += 1
                    self.logger.info(
                        "Responses API output was incomplete (status=%s). Requesting continuation...",
                        response_status,
                    )
                    # For continuation, we keep instructions identical. Sending a simple "continue" cue.
                    input_text = "continue"
                    continue  # loop again to fetch the next chunk

                # Loop finished, store final reasoning summary for caller access
                self.last_reasoning_summary = reasoning_summary_content.strip()

                self._log_interaction(prompt_for_log, full_response_content)
                return full_response_content

            except openai.APIConnectionError as e:
                self.logger.error(f"API connection error: {e}")
                # Save any reasoning summary we might have collected before the error
                if reasoning_summary_content:
                    self.last_reasoning_summary = reasoning_summary_content.strip()
            except Exception as e:
                retry_count += 1
                self.logger.warning(
                    f"Responses API call failed (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    time.sleep(2 ** retry_count)
                    # After waiting, try again with same input_text and accumulated state
                    continue
                else:
                    # Save any reasoning summary we collected before giving up
                    if reasoning_summary_content:
                        self.last_reasoning_summary = reasoning_summary_content.strip()
                    # log prompt + partial content we might have
                    self._log_interaction(prompt_for_log, full_response_content)
                    raise

        # Should not reach here normally
        return full_response_content 

    def _log_interaction(self, prompt_text: str, response_text: str):
        """Log prompt and response in fenced markdown blocks for later review."""
        self.logger.info("PROMPT_START")
        for line in prompt_text.splitlines():
            self.logger.info(line)
        self.logger.info("PROMPT_END")

        self.logger.info("MODEL_RESPONSE_START")
        for line in response_text.splitlines():
            self.logger.info(line)
        self.logger.info("MODEL_RESPONSE_END") 

    def _make_deepseek_api_call(self, messages: list, **kwargs) -> str:
        """전용 DeepSeek Reasoner 호출 경로."""
        return  