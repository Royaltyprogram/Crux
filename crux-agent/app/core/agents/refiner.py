"""
Refine prompts based on evaluation feedback
"""

from typing import Any, Dict, List, Optional
from app.core.agents.base import AbstractAgent, AgentContext, AgentResult
from app.core.agents.prompts.refiner_prompt import get_refiner_system_prompt, build_ai_refinement_prompt
from app.core.providers.base import BaseProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PromptRefiner:
    """Refine prompts based on evaluation feedback to improve answer quality"""
    
    def __init__(self, refiner_model: Optional[BaseProvider] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.refiner_model = refiner_model
        self.refinement_history: List[Dict] = []
        self.last_reasoning_summary: str = ""  # Store the last reasoning summary
    
    async def refine_prompt(
        self,
        original_question: str,
        current_answer: str,
        evaluation_feedback: str,
        iteration: int,
        evaluator_reasoning: str | None = None,
    ) -> str:
        """
        Refine the prompt based on evaluation feedback
        
        Args:
            original_question: The original user question
            current_answer: The latest answer generated
            evaluation_feedback: Feedback from the evaluator
            iteration: Current iteration number
            
        Returns:
            Refined prompt that addresses the issues found in evaluation
        """
        
        self.logger.info(f"Refining prompt for iteration {iteration}")
        
        if self.refiner_model:
            # Use AI model to refine the prompt
            refined_prompt = await self._ai_refine_prompt(
                original_question, current_answer, evaluation_feedback, evaluator_reasoning
            )
        else:
            # Rule-based refinement - no reasoning summary
            self.last_reasoning_summary = ""
            refined_prompt = self._rule_based_refine(
                original_question, current_answer, evaluation_feedback, iteration
            )
        
        # Store refinement history
        self.refinement_history.append({
            "iteration": iteration,
            "original": original_question,
            "refined": refined_prompt,
            "feedback": evaluation_feedback
        })
        
        self.logger.debug(f"Refined prompt: {refined_prompt[:300]}...")
        
        return refined_prompt
    
    async def _ai_refine_prompt(
        self,
        original_question: str,
        current_answer: str,
        evaluation_feedback: str,
        evaluator_reasoning: str | None = None,
    ) -> str:
        """Use AI model to refine the prompt"""
        
        refinement_prompt = build_ai_refinement_prompt(
            original_question=original_question,
            current_answer=current_answer,
            evaluation_feedback=evaluation_feedback,
            evaluator_reasoning=evaluator_reasoning or "",
        )

        try:
            # Prefer function-calling interface (enables code interpreter) if supported
            if hasattr(self.refiner_model, "complete_with_functions"):
                response = await self.refiner_model.complete_with_functions(
                    system_prompt="You are a prompt refinement expert. Output only the refined prompt.",
                    prompt=refinement_prompt,
                    temperature=0.3,
                    functions=[],  # No custom functions – built-in code interpreter will be available
                )

                refined = response if isinstance(response, str) else getattr(response, "content", str(response))
            else:
                # Fallback to basic completion
                refined = await self.refiner_model.complete(
                    system_prompt="You are a prompt refinement expert. Output only the refined prompt.",
                    prompt=refinement_prompt,
                    temperature=0.3
                )
            
            refined = refined + "\n\nsolve this problem with consulting the graduate_specialist and perfect mathematical rigor."
            
            # Store reasoning summary for later access
            if hasattr(self.refiner_model, 'last_reasoning_summary'):
                self.last_reasoning_summary = self.refiner_model.last_reasoning_summary
            else:
                self.last_reasoning_summary = ""
            
            # Log reasoning summary if available
            if self.last_reasoning_summary:
                self.logger.info("PROMPT_REFINER_REASONING_START")
                self.logger.info(self.last_reasoning_summary.strip())
                self.logger.info("PROMPT_REFINER_REASONING_END")
            
            return refined.strip()
            
        except Exception as e:
            self.logger.error(f"AI refinement failed: {e}")
            # Fallback to rule-based refinement
            return self._rule_based_refine(original_question, current_answer, evaluation_feedback, 1)
    
    def _rule_based_refine(
        self,
        original_question: str,
        current_answer: str,
        evaluation_feedback: str,
        iteration: int
    ) -> str:
        """Rule-based prompt refinement"""
        
        feedback_lower = evaluation_feedback.lower()
        refined_parts = []
        
        # Add clarifications based on common issues
        if "unclear" in feedback_lower or "ambiguous" in feedback_lower:
            refined_parts.append("Please provide a clear and detailed solution.")
        
        if "incomplete" in feedback_lower or "missing" in feedback_lower:
            refined_parts.append("Make sure to address ALL aspects of the problem completely.")
        
        if "calculation" in feedback_lower or "mathematical" in feedback_lower:
            refined_parts.append("Show all calculation steps clearly and verify your mathematical work.")
        
        if "logical" in feedback_lower or "reasoning" in feedback_lower:
            refined_parts.append("Explain your reasoning step-by-step with clear logical connections.")
        
        # Add iteration-specific guidance
        if iteration == 1:
            refined_parts.append("\nPrevious attempt had issues. Please read the problem more carefully and provide a comprehensive solution.")
        elif iteration == 2:
            refined_parts.append("\nThe previous attempts were incomplete. Please ensure you fully understand the problem and provide a complete, verified solution.")
        else:
            refined_parts.append("\nFocus on accuracy and completeness. Double-check your work before presenting the final answer.")
        
        # Add the feedback summary
        refined_parts.append(f"\nSpecific issues to address: {evaluation_feedback}")
        
        # Combine with original question
        refined_prompt = "\n".join(refined_parts) + "\n\n" + original_question
        
        return refined_prompt
    
    def get_refinement_history(self) -> List[Dict]:
        """Get the history of prompt refinements"""
        return self.refinement_history
    
    def clear_history(self):
        """Clear refinement history"""
        self.refinement_history = []


# Backward compatibility - keep the original RefinerAgent class
class RefinerAgent(AbstractAgent):
    """
    Refiner agent that improves prompts based on feedback.
    Wrapper around PromptRefiner for backward compatibility.
    """
    
    def __init__(
        self,
        provider: BaseProvider,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ):
        """Initialize Refiner agent."""
        super().__init__(
            role="refiner",
            provider=provider,
            system_prompt=system_prompt or get_refiner_system_prompt(),
            temperature=temperature,
        )
        self.prompt_refiner = PromptRefiner(refiner_model=provider)
    
    async def run(self, context: AgentContext) -> AgentResult:
        """
        Refine a prompt based on feedback.
        
        Args:
            context: Must contain 'prompt' (original) and 'feedback' (evaluation feedback)
            
        Returns:
            Refined prompt
        """
        if not context.feedback:
            logger.warning("No feedback provided for refinement")
            return AgentResult(
                output=context.prompt,  # Return original if no feedback
                metadata={"no_feedback": True},
            )
        
        logger.info(f"Refining prompt based on feedback: {context.feedback[:100]}...")
        
        try:
            # Extract additional metadata if available
            iteration = context.additional_context.get("iteration", 1)
            current_answer = context.additional_context.get("current_answer", "")
            evaluator_reasoning = context.additional_context.get("evaluator_reasoning_summary", "")
            
            # Use the new PromptRefiner
            refined_prompt = await self.prompt_refiner.refine_prompt(
                original_question=context.prompt,
                current_answer=current_answer,
                evaluation_feedback=context.feedback,
                iteration=iteration,
                evaluator_reasoning=evaluator_reasoning,
            )
            
            # Count tokens for cost tracking
            tokens_used = self.provider.count_tokens(context.prompt + context.feedback + refined_prompt)
            
            logger.info(f"Prompt refinement complete, tokens: {tokens_used}")
            
            return AgentResult(
                output=refined_prompt,
                metadata={
                    "original_prompt": context.prompt,
                    "feedback_used": context.feedback,
                    "iteration": iteration,
                    "refinement_history": self.prompt_refiner.get_refinement_history(),
                    "reasoning_summary": self.prompt_refiner.last_reasoning_summary,
                },
                tokens_used=tokens_used,
            )
            
        except Exception as e:
            logger.error(f"Refinement failed: {e}")
            return AgentResult(
                output=context.prompt,  # Fallback to original
                metadata={
                    "error": str(e),
                    "fallback": True,
                    "original_prompt": context.prompt,
                },
                tokens_used=0,
            ) 