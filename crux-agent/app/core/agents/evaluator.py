"""
Evaluator agent for quality assessment.
"""
from typing import Any, Dict, List, Optional

from app.core.agents.base import AbstractAgent, AgentContext, AgentResult
from app.core.agents.prompts.evaluate_prompt import get_evaluator_system_prompt, build_evaluation_prompt
from app.core.providers.base import BaseProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EvaluatorAgent(AbstractAgent):
    """
    Evaluator agent that assesses answer quality.
    """
    
    def __init__(
        self,
        provider: BaseProvider,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,  # Zero temperature for consistent evaluation
    ):
        """Initialize Evaluator agent."""
        super().__init__(
            role="evaluator",
            provider=provider,
            system_prompt=system_prompt or get_evaluator_system_prompt(),
            temperature=temperature,
        )

        # No custom tools for the evaluator – we rely on the provider's built-in code interpreter

    async def _generate_with_functions(
        self,
        *,
        prompt: str,
        functions: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> str:
        """Generate using function-calling interface (adds code interpreter automatically)."""

        try:
            if hasattr(self.provider, "complete_with_functions"):
                response = await self.provider.complete_with_functions(
                    prompt=prompt,
                    functions=functions,
                    system_prompt=self.system_prompt,
                    temperature=temperature if temperature is not None else self.temperature,
                )

                # Provider may return raw string or an object with a content attribute
                if isinstance(response, str):
                    return response
                if hasattr(response, "content"):
                    return response.content  # type: ignore[attr-defined]

                # Fallback – cast to string
                return str(response)

            # Provider does not support function calling – fallback
            return await self._generate(
                prompt=prompt,
                temperature=temperature if temperature is not None else self.temperature,
            )

        except Exception:
            # Any unexpected failure – fallback to regular generation
            return await self._generate(
                prompt=prompt,
                temperature=temperature if temperature is not None else self.temperature,
            )
    
    async def run(self, context: AgentContext) -> AgentResult:
        """
        Evaluate the quality of an answer.
        
        Args:
            context: Must contain 'prompt' (question) and 'output' (answer to evaluate)
            
        Returns:
            Evaluation result with score and feedback
        """
        if not context.output or context.output.strip() == "":
            logger.error("No output provided for evaluation")
            return AgentResult(
                output="Cannot evaluate: no answer provided",
                score=None,
                feedback="No answer to evaluate",
            )
        
        logger.info(f"Evaluating answer for: {context.prompt[:100]}...")
        
        # Extract constraints and previous reasoning if provided
        constraints = context.additional_context.get("constraints")
        generator_reasoning = context.additional_context.get("generator_reasoning_summary")
        
        # Build evaluation prompt using the prompts module
        evaluation_prompt = build_evaluation_prompt(
            question=context.prompt,
            answer=context.output,
            constraints=constraints,
            generator_reasoning=generator_reasoning,
        )
        
        try:
            # Generate evaluation allowing code execution via function-calling API
            evaluation_result = await self._generate_with_functions(
                prompt=evaluation_prompt,
                functions=[],  # No custom functions – enables built-in code interpreter
                temperature=self.temperature,
            )
            evaluation = evaluation_result.strip() if isinstance(evaluation_result, str) else str(evaluation_result).strip()

            # Prevent invalid empty evaluations from wrongly triggering stoppage
            if not evaluation or evaluation == "Cannot evaluate: no answer provided":
                logger.error("Invalid evaluation: empty or placeholder response")
                return AgentResult(
                    output="Evaluation failed",
                    score=None,  # No score - only feedback
                    feedback="Invalid evaluation: empty or placeholder response",
                    metadata={
                        "should_stop": False,
                    },
                    tokens_used=0,
                )

            # Count tokens for cost tracking
            tokens_used = self.provider.count_tokens(evaluation_prompt + evaluation)
            
            # Check for <stop> token to determine if iteration should stop
            # Be more conservative - don't stop if there are errors mentioned
            should_stop = "<stop>" in evaluation and "error" not in evaluation.lower()
            
            logger.info(f"Evaluation complete. Should stop: {should_stop}, tokens: {tokens_used}")
            
            return AgentResult(
                output=evaluation,
                score=None,  # No score - only feedback
                feedback=evaluation,
                metadata={
                    "should_stop": should_stop,
                    "constraints_checked": constraints is not None,
                    "evaluation_method": "detailed_analysis",
                    "reasoning_summary": self.provider.get_last_reasoning_summary() if hasattr(self.provider, "get_last_reasoning_summary") else "",
                },
                tokens_used=tokens_used,
            )
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            # Fallback to text evaluation
            try:
                fallback_prompt = f"Rate this answer from 0-1 and explain: Q: {context.prompt} A: {context.output}"
                text_eval = await self._generate(
                    prompt=fallback_prompt,
                    temperature=0.0,
                )
                
                tokens_used = self.provider.count_tokens(fallback_prompt + text_eval)
                
                return AgentResult(
                    output=text_eval,
                    score=None,  # No score - only feedback
                    feedback=text_eval,
                    metadata={
                        "fallback": True,
                        "error": str(e),
                        "reasoning_summary": self.provider.get_last_reasoning_summary() if hasattr(self.provider, "get_last_reasoning_summary") else "",
                    },
                    tokens_used=tokens_used,
                )
            except Exception as fallback_error:
                logger.error(f"Fallback evaluation also failed: {fallback_error}")
                return AgentResult(
                    output="Evaluation failed",
                    score=None,
                    feedback="Unable to evaluate answer",
                    metadata={
                        "error": str(e),
                        "fallback_error": str(fallback_error),
                        "reasoning_summary": self.provider.get_last_reasoning_summary() if hasattr(self.provider, "get_last_reasoning_summary") else "",
                    },
                    tokens_used=0,
                ) 