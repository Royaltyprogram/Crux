"""
SelfEvolveMixin
===============
본 믹스인은 **IterationManager** 를 활용하여 (Question → Answer → 평가 → 프롬프트 리파인) *Self-Evolve* 루프를 간단하게 재사용할 수 있게 해준다.

프레임워크 내부에서 **ProfessorModel** 과 **GraduateWorker** 모두 동일한 개선 루프가 필요하지만, 구현을 중복하지 않기 위해 Mixin 으로 모듈화하였다.

필요 조건
---------
1. 상속 클래스는 `BaseModel` (즉, `generate()` 메서드가 존재) 여야 한다.
2. `self.framework_config` 속성에 `FrameworkConfig` 인스턴스를 보유해야 한다.
3. `self.logger` 속성이 존재해야 한다 (대부분 BaseModel 에 의해 자동 생성).

사용 방법
---------
```python
class ProfessorModel(SelfEvolveMixin, BaseModel):
    ...

professor = ProfessorModel(cfg)
session   = professor.self_evolve(question)
print(session.final_answer)
```
"""

from __future__ import annotations

from typing import Optional

from ..orchestrator.iteration_manager import IterationManager, IterationSession
from .evaluator_model import EvaluatorModel
from ..config import FrameworkConfig

# NOTE: 상대 경로 import를 위해 패키지 구조와 동일하게 작성

class SelfEvolveMixin:
    """Mixin providing a *self-evolve* iterative refinement loop.

    이 믹스인은 기존 `IterationManager` 를 그대로 활용한다. 호출 모델 스스로가
    *generator* 역할을 수행하고, `FrameworkConfig.evaluator_config` 로부터 생성한
    Evaluator 가 *evaluator* 역할을 맡는다.
    """

    # Professor 와 Graduate 가 공유할 기본 성공 임계값(평가 모델이 <stop> 포함)
    success_token: str = "<stop>"

    def self_evolve(
        self,
        question: str,
        *,
        max_iterations: Optional[int] = None,
        use_ai_refiner: bool = True,
    ) -> IterationSession:
        """Run the self-evolve loop and return the full `IterationSession`.

        Parameters
        ----------
        question : str
            원본 문제/프롬프트.
        max_iterations : Optional[int]
            루프 반복 한도를 임시로 덮어쓰고 싶을 때 사용.
        use_ai_refiner : bool
            IterationManager 에서 AI-기반 PromptRefiner 사용 여부.
        """
        # 프레임워크 설정이 필요하다.
        if not hasattr(self, "framework_config"):
            raise AttributeError(
                "SelfEvolveMixin requires `self.framework_config` on the host class."
            )

        cfg: FrameworkConfig = self.framework_config

        # evaluator 인스턴스 준비 (Professor 용 별도 Evaluator-P 로 간주)
        # Pass through provider from host model if available
        provider = getattr(self, "_provider", None)
        evaluator = EvaluatorModel(cfg.evaluator_config, provider=provider)

        # max_iterations 동적 override (원본 값 백업 후 복원)
        original_max_iter = cfg.max_iterations
        if max_iterations is not None:
            cfg.max_iterations = max_iterations

        # IterationManager 실행
        manager = IterationManager(
            generator=self,  # 현재 모델이 곧 generator 역할
            evaluator=evaluator,
            config=cfg,
            use_ai_refiner=use_ai_refiner,
        )

        session: IterationSession = manager.run_iterative_improvement(question)

        # max_iterations 원복
        cfg.max_iterations = original_max_iter

        # 호스트 객체에 결과 캐싱 (optional)
        try:
            setattr(self, "_last_self_evolve_session", session)
        except Exception:
            pass

        # 로그
        if hasattr(self, "logger"):
            self.logger.info(
                f"Self-Evolve loop completed after {session.total_iterations} iterations"
            )

        return session

    # 편의 함수: 바로 최종 답변만 가져오기
    def solve(self, question: str, **kwargs) -> str:
        """Self-Evolve 후 최종 답변 문자열만 반환."""
        session = self.self_evolve(question, **kwargs)
        return session.final_answer 
    