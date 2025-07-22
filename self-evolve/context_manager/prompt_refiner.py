"""
Refine prompts based on evaluation feedback
"""

from typing import Dict, List, Optional
from ..utils.logger import get_logger
from ..models.base_model import BaseModel


class PromptRefiner:
    """Refine prompts based on evaluation feedback to improve answer quality"""
    
    def __init__(self, refiner_model: Optional[BaseModel] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.refiner_model = refiner_model
        self.refinement_history: List[Dict] = []
        self.last_reasoning_summary: str = ""  # Store the last reasoning summary
    
    def refine_prompt(
        self,
        original_question: str,
        current_answer: str,
        evaluation_feedback: str,
        iteration: int
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
            refined_prompt = self._ai_refine_prompt(
                original_question, current_answer, evaluation_feedback
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
    
    def _ai_refine_prompt(
        self,
        original_question: str,
        current_answer: str,
        evaluation_feedback: str
    ) -> str:
        """Use AI model to refine the prompt"""
        
        refinement_prompt = f"""You are a prompt engineering expert. Your task is to refine/improve a prompt based on evaluation feedback.

Original Question:
{original_question}

Current Answer:
{current_answer}

Evaluation Feedback:
{evaluation_feedback}

Based on the evaluation feedback, please provide an IMPROVED version of the original question that will help generate a better answer. The refined prompt should:

1. Address the specific issues mentioned in the evaluation
2. Clarify any ambiguities
3. Add necessary context or constraints
4. Guide towards a more complete and accurate answer
5. Maintain the original intent while making it clearer
6. **IMPORTANT**: If the evaluation feedback mentions ANY positive aspects, successful techniques, or correct approaches from the current answer, extract these and include them in an "<additional_info>" section in the refined prompt. This helps reduce trial-and-error and problem difficulty by preserving what worked well.

The "<additional_info>" section should be formatted as:
<additional_info>
Successfully applied approaches from previous attempts:
- [successful approach 1]
- [successful approach 2]
...
Please refer to the above successful elements to derive a better solution.
</additional_info>

IMPORTANT: Return ONLY the refined prompt, nothing else. Do not include explanations or meta-commentary."""

        messages = [
            {"role": "system", "content": "You are a prompt refinement expert. Output only the refined prompt."},
            {"role": "user", "content": refinement_prompt}
        ]
        
        refined = self.refiner_model._make_api_call(messages)
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