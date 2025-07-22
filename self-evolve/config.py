"""
Configuration settings for the Iterative LLM Framework
"""

import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
import copy as _copy


@dataclass
class ModelConfig:
    """Configuration for individual models (Generator and Evaluator)
    
    Generator Model: 대화의 주요 스트림을 담당하는 모델 (Professor 역할)
    Evaluator Model: 답변을 평가하고 피드백을 제공하는 모델
    """
    api_key: Optional[str] = None
    model_name: str = "o3"
    temperature: float = 0.7
    timeout: Optional[int] = 1200  # Default timeout of 10 minutes
    reasoning_effort: str = "high"  # Responses API reasoning effort
    reasoning_summary: str | None = "detailed"  # default to detailed summary for reasoning models
    truncation: str = "auto"  # "auto" or "disabled"
    tool_choice: str = "auto"  # "auto" | "none" | "required" | function spec
    api_base: Optional[str] = None
    # Whether to include the built-in code interpreter tool when making
    # responses API calls. Disabled by default; can be enabled per-call via
    # kwargs or globally via this config flag.
    enable_code_interpreter: bool = False
    # Whether to request streaming responses by default (Responses API)
    # Streaming is preferred for reliable reasoning summary extraction
    stream: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "reasoning_effort": self.reasoning_effort,
            "reasoning_summary": self.reasoning_summary,
            "truncation": self.truncation,
            "tool_choice": self.tool_choice
        }


@dataclass
class WorkerConfig:
    """Configuration for Worker models
    
    Worker Model: Function call 호출 시 특정 작업을 수행하는 전문가 모델 (Graduate Worker 역할)
    - 수학 계산, 코드 실행, 특정 도메인 문제 해결 등의 전문적인 작업 담당
    - Generator(Professor)의 요청에 따라 독립적으로 작업 수행
    """
    api_key: Optional[str] = None
    model_name: str = "o3"  # Worker도 강력한 모델 사용 가능
    temperature: float = 0.5  # Worker는 더 일관된 답변을 위해 낮은 temperature
    timeout: Optional[int] = 1200  # Worker는 더 짧은 timeout (10분)
    reasoning_effort: str = "high"  # 복잡한 작업을 위한 높은 추론 능력
    reasoning_summary: str | None = "detailed"  # 상세 요약을 기본값으로 설정
    truncation: str = "auto"
    tool_choice: str = "auto"
    api_base: Optional[str] = None
    enable_code_interpreter: bool = True  # Worker는 기본적으로 코드 인터프리터 활성화
    max_self_evolve_iterations: int = 5  # Worker의 self-evolve 최대 반복 횟수
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model_name,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "reasoning_effort": self.reasoning_effort,
            "reasoning_summary": self.reasoning_summary,
            "truncation": self.truncation,
            "tool_choice": self.tool_choice,
            "enable_code_interpreter": self.enable_code_interpreter
        }


@dataclass
class FrameworkConfig:
    """Main configuration for the framework
    
    세 가지 주요 모델 역할:
    1. Generator (Professor): 대화의 주요 흐름을 관리하고 전체적인 문제 해결 전략 수립
    2. Evaluator: Worker의 답변을 평가하고 개선 방향 제시  
    3. Worker (Graduate): Function call을 통해 호출되어 특정 작업을 수행하는 전문가
    """
    # Model configurations
    generator_config: ModelConfig = None  # Professor 역할
    evaluator_config: ModelConfig = None  # Evaluator 역할
    worker_config: WorkerConfig = None    # Graduate Worker 역할
    refiner_config: ModelConfig | None = None  # Prompt Refiner 역할
    
    # Iteration settings
    max_iterations: int = 5  # Generator의 최대 반복 횟수
    
    # Logging settings
    log_level: str = "INFO"
    log_file: Optional[str] = "iterative_llm.log"
    
    # API settings
    api_timeout: int = 60
    retry_attempts: int = 3
    
    def __post_init__(self):
        if self.generator_config is None:
            self.generator_config = ModelConfig()
        if self.evaluator_config is None:
            self.evaluator_config = ModelConfig(
                model_name="gpt-4",
                temperature=0.3
            )
        if self.worker_config is None:
            self.worker_config = WorkerConfig()  # WorkerConfig 사용

        # If refiner_config is not provided, default to evaluator_config (creates a copy)
        if self.refiner_config is None:
            # Deep copy to avoid mutation side effects
            self.refiner_config = _copy.deepcopy(self.evaluator_config)

# Default configuration
default_config = FrameworkConfig() 