"""
Main orchestrator for iterative improvement using prompt refinement
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import json
import os
import re

from ..models.generator_model import GeneratorModel
from ..models.evaluator_model import EvaluatorModel
from ..context_manager import ContextBuilder, ContextEnhancer, PromptRefiner
from ..config import FrameworkConfig, ModelConfig
from ..utils.logger import get_logger


@dataclass
class IterationResult:
    """Result from a single iteration"""
    iteration: int
    question: str
    refined_question: Optional[str]
    answer: str
    reasoning_summary: Optional[str]  # Generator reasoning
    evaluation_feedback: str
    evaluator_reasoning_summary: Optional[str]  # Evaluator reasoning
    refiner_reasoning_summary: Optional[str]  # Prompt refiner reasoning
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "question": self.question,
            "refined_question": self.refined_question,
            "answer": self.answer,
            "reasoning_summary": self.reasoning_summary,
            "evaluation_feedback": self.evaluation_feedback,
            "evaluator_reasoning_summary": self.evaluator_reasoning_summary,
            "refiner_reasoning_summary": self.refiner_reasoning_summary,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class IterationSession:
    """Complete iteration session results"""
    original_question: str
    final_answer: str
    iterations: List[IterationResult]
    total_iterations: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_question": self.original_question,
            "final_answer": self.final_answer,
            "total_iterations": self.total_iterations,
            "iterations": [it.to_dict() for it in self.iterations]
        }


class IterationManager:
    """Manage the iterative improvement process using prompt refinement"""
    
    def __init__(
        self,
        generator: GeneratorModel,
        evaluator: EvaluatorModel,
        config: FrameworkConfig,
        use_ai_refiner: bool = True,
        constraints: Optional[str] = None,
        max_context_tokens: Optional[int] = None,
        enable_persistence: bool = False,
        results_dir: Optional[str] = None
    ):
        self.logger = get_logger(self.__class__.__name__)
        self.generator = generator
        self.evaluator = evaluator
        self.config = config
        self.constraints = constraints
        self.context_builder = ContextBuilder()
        self.context_enhancer = ContextEnhancer()
        
        # Persistence settings
        self.enable_persistence = enable_persistence
        self.results_dir = results_dir or "./tooliense/logs"
        
        # Context management settings - get provider-specific limits from environment
        from app.settings import settings
        
        # Determine provider from generator model if possible
        current_provider = settings.llm_provider
        if hasattr(generator, 'config') and hasattr(generator.config, 'model_name'):
            # Try to detect provider from model config
            if 'gpt' in generator.config.model_name.lower() or 'o4' in generator.config.model_name.lower():
                current_provider = 'openai'
            elif 'deepseek' in generator.config.model_name.lower() or 'qwen' in generator.config.model_name.lower():
                current_provider = 'openrouter'
            elif hasattr(generator, 'provider') and 'lmstudio' in str(type(generator.provider)).lower():
                current_provider = 'lmstudio'
        
        # Use provider-specific context limits
        self.max_context_tokens = max_context_tokens or settings.get_context_limit(current_provider)
        self.response_reserve = settings.response_reserve
        self.summarization_threshold = settings.summarization_threshold
        self.current_provider = current_provider
        
        self.logger.info(f"Context management initialized for {current_provider}: {self.max_context_tokens:,} tokens")
        self.logger.info(f"Response reserve: {self.response_reserve:,} tokens, Summarization threshold: {self.summarization_threshold*100:.0f}%")
        
        
        # Initialize prompt refiner
        if use_ai_refiner:
            # AI 기반 프롬프트 개선을 위해 별도 refiner_config를 우선 사용하고,
            # 없으면 evaluator_config를 fallback으로 사용
            if getattr(config, 'refiner_config', None):
                refiner_config = config.refiner_config
            else:
                refiner_config = ModelConfig(
                    api_key=config.evaluator_config.api_key,
                    model_name=config.evaluator_config.model_name,
                    temperature=0.7
                )
            from ..models.base_model import BaseModel
            # Create a minimal wrapper for the refiner
            class RefinerModel(BaseModel):
                def generate(self, prompt: str, **kwargs) -> str:
                    return ""  # Not used directly
            
            refiner_model = RefinerModel(refiner_config)
            self.prompt_refiner = PromptRefiner(refiner_model=refiner_model)
        else:
            # 규칙 기반 프롬프트 개선
            self.prompt_refiner = PromptRefiner()
    
    def run_iterative_improvement(
        self,
        question: str
    ) -> IterationSession:
        """Run the complete iterative improvement process with prompt refinement"""
        
        self.logger.info(f"Starting iterative improvement for: {question}")
        
        # Clear any previous context and refinement history
        self.context_builder.clear_history()
        self.prompt_refiner.clear_history()
        
        iterations = []
        current_question = question  # 현재 사용할 프롬프트
        original_question = question  # 원본 질문 보존
        current_answer = None
        
        # Track recent answers for convergence check
        recent_answer_values = []
        
        # Track reasoning summaries for cross-agent context
        accumulated_reasoning = []
        
        for i in range(self.config.max_iterations):
            self.logger.info(f"Starting iteration {i + 1}")
            
            # Build token-aware context from accumulated reasoning for Generator
            reasoning_context = self._manage_context_size(current_question, accumulated_reasoning)
            
            # Generate answer with current prompt and managed reasoning context
            if reasoning_context:
                full_prompt = current_question + reasoning_context
            else:
                full_prompt = current_question
                
            # WORKAROUND: Force streaming to reliably capture reasoning summary.
            # The non-streaming path in base_model has a bug.
            answer = self.generator.generate(full_prompt, stream=True)
            reasoning_summary = self.generator.last_reasoning_summary
            current_answer = answer
            
            # Add generator reasoning to accumulated context
            if reasoning_summary:
                accumulated_reasoning.append(f"Generator Iteration {i+1}:\n{reasoning_summary}")
            
            # Build enhanced evaluation prompt with generator reasoning
            eval_context = ""
            if reasoning_summary:
                eval_context = f"\n\n---GENERATOR REASONING CONTEXT---\nThe generator's reasoning process for this answer:\n{reasoning_summary}"
            
            # Evaluate the Q&A pair with reasoning context
            enhanced_eval_prompt = f"Question: {original_question}\n\nAnswer: {answer}{eval_context}"
            evaluation_feedback = self.evaluator.evaluate(enhanced_eval_prompt, "", self.constraints)
            evaluator_reasoning = getattr(self.evaluator, 'last_reasoning_summary', '')
            
            # Add evaluator reasoning to accumulated context
            if evaluator_reasoning:
                accumulated_reasoning.append(f"Evaluator Iteration {i+1}:\n{evaluator_reasoning}")
            
            # Log QA pair with refined prompt info
            self.logger.info(json.dumps({
                "event": "qa_pair",
                "iteration": i + 1,
                "original_question": original_question,
                "refined_question": current_question if current_question != original_question else None,
                "answer": answer,
                "evaluation_feedback": evaluation_feedback
            }, ensure_ascii=False))
            
            # Initially no refiner reasoning for this iteration
            refiner_reasoning = ""
            
            # Store iteration result with proper reasoning summaries
            iterations.append(IterationResult(
                iteration=i + 1,
                question=original_question,
                refined_question=current_question if current_question != original_question else None,
                answer=answer,
                reasoning_summary=reasoning_summary,  # Generator reasoning
                evaluation_feedback=evaluation_feedback,
                evaluator_reasoning_summary=evaluator_reasoning,  # Evaluator reasoning
                refiner_reasoning_summary=refiner_reasoning,  # Will be updated later if refiner is used
                timestamp=datetime.now()
            ))
            
            # Stop if the evaluator says the answer is good enough
            if "<stop>" in evaluation_feedback:
                self.logger.info("Evaluator has indicated to stop. Halting iterations.")
                break
            
            # Extract answer value from <answer> tags
            answer_value = self._extract_answer_value(answer)
            if answer_value is not None:
                recent_answer_values.append(answer_value)
                # Keep only last 3 answer values
                if len(recent_answer_values) > 3:
                    recent_answer_values.pop(0)
                
                # Check for convergence: 3 consecutive same answers
                if len(recent_answer_values) >= 3 and len(set(recent_answer_values[-3:])) == 1:
                    self.logger.info(f"Answer converged to '{answer_value}' for 3 consecutive iterations, stopping")
                    break
            
            # Continue iterations if not converged and not at max iterations
            if i < self.config.max_iterations - 1:
                # Build context for prompt refiner with both generator and evaluator reasoning
                refiner_context = ""
                if reasoning_summary or evaluator_reasoning:
                    refiner_context += "\n\n---REASONING CONTEXT FOR REFINEMENT---"
                    if reasoning_summary:
                        refiner_context += f"\nGenerator's reasoning:\n{reasoning_summary}"
                    if evaluator_reasoning:
                        refiner_context += f"\nEvaluator's reasoning:\n{evaluator_reasoning}"
                
                # Refine the prompt based on evaluation feedback with reasoning context
                enhanced_refine_params = {
                    "original_question": original_question + refiner_context,
                    "current_answer": answer,
                    "evaluation_feedback": evaluation_feedback,
                    "iteration": i + 1
                }
                
                refined_prompt = self.prompt_refiner.refine_prompt(**enhanced_refine_params)
                
                # Update the last iteration with refiner reasoning
                current_refiner_reasoning = getattr(self.prompt_refiner, 'last_reasoning_summary', '')
                iterations[-1].refiner_reasoning_summary = current_refiner_reasoning
                
                # Add refiner reasoning to accumulated context
                if current_refiner_reasoning:
                    accumulated_reasoning.append(f"Prompt Refiner Iteration {i+1}:\n{current_refiner_reasoning}")
                
                # Update current question for next iteration
                current_question = refined_prompt
                
                self.logger.info(f"Iteration {i + 1} complete, prompt refined for next iteration")
                self.logger.debug(f"Refined prompt preview: {refined_prompt[:200]}...")
        
        # Use the last answer as final answer
        final_answer = current_answer if current_answer else "No answer generated"
        
        session = IterationSession(
            original_question=original_question,
            final_answer=final_answer,
            iterations=iterations,
            total_iterations=len(iterations)
        )
        
        self.logger.info(
            f"Completed iterative improvement. "
            f"Total iterations: {session.total_iterations}"
        )
        
        # Log refinement history
        refinement_history = self.prompt_refiner.get_refinement_history()
        if refinement_history:
            self.logger.info(json.dumps({
                "event": "refinement_history",
                "history": refinement_history
            }, ensure_ascii=False))
        
        # Persist results if enabled
        if self.enable_persistence:
            self.logger.info("About to call _save_example_results")
            try:
                self.logger.info("Entering _save_example_results try block")
                self._save_example_results(session)
                self.logger.info("_save_example_results completed successfully")
            except Exception as e:
                self.logger.error(f"Exception in _save_example_results: {e}")
                self.logger.warning(f"Failed to save example results: {e}")
        else:
            self.logger.debug("Persistence disabled, skipping _save_example_results")
        return session
    
    def _extract_answer_value(self, answer: str) -> Optional[str]:
        """Extract the value from <answer> tags in the response"""
        # Look for <answer>...</answer> pattern
        match = re.search(r'<answer>(.*?)</answer>', answer, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using the generator's token counter."""
        try:
            # Use the generator's token counting method
            if hasattr(self.generator, 'count_tokens'):
                return self.generator.count_tokens(text)
            elif hasattr(self.generator, 'provider') and hasattr(self.generator.provider, 'count_tokens'):
                return self.generator.provider.count_tokens(text)
            else:
                # Fallback: rough estimation (4 chars per token)
                return len(text) // 4
        except Exception as e:
            self.logger.warning(f"Token counting failed, using fallback: {e}")
            return len(text) // 4
    
    def _manage_context_size(self, base_prompt: str, accumulated_reasoning: List[str]) -> str:
        """Intelligently manage context size using LLM-based summarization when needed.
        
        Strategy:
        1. Calculate total context size
        2. If approaching limit (80%), trigger LLM summarization
        3. Always keep the most recent reasoning intact
        4. Summarize older reasoning to compress context
        
        Args:
            base_prompt: The core prompt (question + current refinements)
            accumulated_reasoning: List of reasoning summaries to potentially include
            
        Returns:
            Context string that fits within token limits
        """
        if not accumulated_reasoning:
            return ""
        
        # Count tokens in base prompt (this must always be included)
        base_tokens = self._count_tokens(base_prompt)
        available_tokens = self.max_context_tokens - base_tokens - self.response_reserve
        
        if available_tokens <= 0:
            self.logger.warning(
                f"Base prompt ({base_tokens} tokens) exceeds context limit. "
                f"Context limit: {self.max_context_tokens}, reserved for response: {self.response_reserve}"
            )
            return ""  # No room for additional context
        
        # Build full context and check if summarization is needed
        full_context = "\n\n".join(accumulated_reasoning)
        full_context_tokens = self._count_tokens(full_context)
        
        # If context fits comfortably, use it as-is
        if full_context_tokens <= available_tokens:
            context_usage = full_context_tokens / available_tokens
            if context_usage > self.summarization_threshold:
                self.logger.info(
                    f"Context usage high: {full_context_tokens}/{available_tokens} tokens ({context_usage*100:.1f}%) - consider summarization"
                )
            return "\n\n---PREVIOUS REASONING CONTEXT---\n" + full_context
        
        # Context is too large - need intelligent management
        self.logger.info(
            f"Context too large: {full_context_tokens}/{available_tokens} tokens. Applying intelligent summarization..."
        )
        
        # Strategy: Keep most recent reasoning intact, summarize older ones
        if len(accumulated_reasoning) == 1:
            # Only one reasoning - either summarize it or truncate
            return self._handle_single_large_reasoning(accumulated_reasoning[0], available_tokens)
        
        # Multiple reasoning summaries - keep recent, summarize old
        return self._handle_multiple_reasoning(accumulated_reasoning, available_tokens)
    
    def _handle_single_large_reasoning(self, reasoning: str, available_tokens: int) -> str:
        """Handle a single large reasoning that exceeds available tokens."""
        reasoning_tokens = self._count_tokens(reasoning)
        
        # If it's moderately over the limit, try LLM summarization
        if reasoning_tokens <= available_tokens * 2:  # Within 2x limit
            target_tokens = int(available_tokens * 0.9)  # Target 90% of available
            summarized = self._summarize_reasoning_with_llm(reasoning, target_tokens)
            
            if summarized and self._count_tokens(summarized) <= available_tokens:
                self.logger.info(
                    f"LLM summarization: {reasoning_tokens} -> {self._count_tokens(summarized)} tokens"
                )
                return "\n\n---PREVIOUS REASONING CONTEXT (SUMMARIZED)---\n" + summarized
        
        # Fallback to truncation if summarization fails or reasoning is too large
        self.logger.warning("Falling back to truncation for single large reasoning")
        truncated = self._truncate_reasoning(reasoning, available_tokens)
        final_tokens = self._count_tokens(truncated)
        self.logger.info(f"Truncation applied: {reasoning_tokens} -> {final_tokens} tokens")
        return "\n\n---PREVIOUS REASONING CONTEXT (TRUNCATED)---\n" + truncated
    
    def _handle_multiple_reasoning(self, accumulated_reasoning: List[str], available_tokens: int) -> str:
        """Handle multiple reasoning summaries that collectively exceed available tokens."""
        # Always keep the most recent reasoning intact if possible
        most_recent = accumulated_reasoning[-1]
        most_recent_tokens = self._count_tokens(most_recent)
        
        # Reserve space for the most recent reasoning
        remaining_tokens = available_tokens - most_recent_tokens
        
        if remaining_tokens <= 0:
            # Even the most recent reasoning is too large
            self.logger.warning("Most recent reasoning alone exceeds available tokens")
            return self._handle_single_large_reasoning(most_recent, available_tokens)
        
        # Summarize older reasoning to fit in remaining space
        older_reasoning = accumulated_reasoning[:-1]  # All except the most recent
        
        if not older_reasoning:
            # Only one reasoning (the most recent)
            return "\n\n---PREVIOUS REASONING CONTEXT---\n" + most_recent
        
        # Try to fit older reasoning through summarization
        older_combined = "\n\n".join(older_reasoning)
        older_tokens = self._count_tokens(older_combined)
        
        if older_tokens <= remaining_tokens:
            # Older reasoning fits - use everything as-is
            return "\n\n---PREVIOUS REASONING CONTEXT---\n" + "\n\n".join(accumulated_reasoning)
        
        # Need to summarize older reasoning
        target_tokens = int(remaining_tokens * 0.8)  # Use 80% of remaining space
        summarized_older = self._summarize_reasoning_with_llm(older_combined, target_tokens)
        
        if summarized_older and self._count_tokens(summarized_older) <= remaining_tokens:
            self.logger.info(
                f"LLM summarized older reasoning: {older_tokens} -> {self._count_tokens(summarized_older)} tokens"
            )
            context_parts = [summarized_older, most_recent]
            return "\n\n---PREVIOUS REASONING CONTEXT (OLDER SUMMARIZED)---\n" + "\n\n".join(context_parts)
        
        # Summarization failed - use rolling window fallback
        self.logger.warning("LLM summarization failed, using rolling window fallback")
        return "\n\n---PREVIOUS REASONING CONTEXT (RECENT ONLY)---\n" + most_recent
    
    def _summarize_reasoning_with_llm(self, reasoning_text: str, target_tokens: int) -> Optional[str]:
        """Use LLM to intelligently summarize reasoning context.
        
        Uses a single, effective summarization prompt that typically achieves good compression
        without the complexity of multiple passes.
        
        Args:
            reasoning_text: The reasoning text to summarize
            target_tokens: Target token count for the summary
            
        Returns:
            Summarized text, or None if summarization fails
        """
        current_tokens = self._count_tokens(reasoning_text)
        
        # If already fits, no need to summarize
        if current_tokens <= target_tokens:
            return reasoning_text
        
        # Single effective summarization prompt
        summarization_prompt = """Create a concise summary, focusing on key insights and main conclusions. Remove verbose explanations but keep important details.

Reasoning to summarize:
{reasoning_text}

Summary:""".format(reasoning_text=reasoning_text)
        
        try:
            # Generate summary with focused temperature for consistency
            summary = self.generator.generate(summarization_prompt, temperature=0.2, stream=False)
            
            if not summary or len(summary.strip()) < 30:
                self.logger.warning("LLM summarization produced empty or too short result")
                return None
            
            summary = summary.strip()
            summary_tokens = self._count_tokens(summary)
            
            # Check if summarization achieved meaningful compression
            if summary_tokens >= current_tokens * 0.90:  # Less than 10% compression
                self.logger.warning(f"LLM summarization ineffective: {current_tokens} -> {summary_tokens} tokens")
                return None
            
            # Log the compression achieved
            compression_ratio = summary_tokens / current_tokens
            self.logger.info(f"LLM summarization: {current_tokens} -> {summary_tokens} tokens ({compression_ratio:.1%})")
            
            # Return the summary whether it fits perfectly or not - let caller decide
            return summary
            
        except Exception as e:
            self.logger.error(f"LLM summarization failed: {e}")
            return None
    
    def _truncate_reasoning(self, reasoning: str, max_tokens: int) -> str:
        """Truncate a reasoning summary to fit within token limits.
        
        Strategy: Keep the beginning and end, drop the middle.
        This preserves the setup and conclusion while dropping detailed steps.
        
        Args:
            reasoning: Original reasoning text
            max_tokens: Maximum tokens allowed
            
        Returns:
            Truncated reasoning text that fits within max_tokens
        """
        current_tokens = self._count_tokens(reasoning)
        if current_tokens <= max_tokens:
            return reasoning
        
        # Split into lines for better truncation
        lines = reasoning.split('\n')
        
        # Keep first 30% and last 30% of lines, drop middle 40%
        total_lines = len(lines)
        keep_start = max(1, int(total_lines * 0.3))
        keep_end = max(1, int(total_lines * 0.3))
        
        if keep_start + keep_end >= total_lines:
            # If too few lines, just truncate by characters
            target_chars = int(len(reasoning) * (max_tokens / current_tokens))
            return reasoning[:target_chars] + "\n\n[... reasoning truncated for context management ...]\n\n" + reasoning[-target_chars//4:]
        
        # Reconstruct with beginning and end
        truncated_lines = (
            lines[:keep_start] + 
            ["\n[... middle reasoning truncated for context management ...]\n"] +
            lines[-keep_end:]
        )
        
        truncated = '\n'.join(truncated_lines)
        
        # Check if it fits, if not, do character-based truncation
        if self._count_tokens(truncated) > max_tokens:
            self.logger.debug("Line-based truncation still too large, applying character-based truncation")
            target_chars = int(len(reasoning) * (max_tokens / current_tokens) * 0.9)  # 90% to be safe
            keep_start_chars = target_chars // 2
            keep_end_chars = target_chars // 4
            truncated = (
                reasoning[:keep_start_chars] + 
                "\n\n[... reasoning truncated for context management ...]\n\n" +
                reasoning[-keep_end_chars:]
            )
            final_tokens = self._count_tokens(truncated)
            self.logger.debug(f"Character-based truncation: {current_tokens} -> {final_tokens} tokens")
        
        return truncated
    
    def _save_example_results(self, session: "IterationSession") -> None:
        """Save per-iteration Q&A pairs into the examples/logs folder.

        Directory layout:
            examples/logs/{execution_id}/
                final_answer.md
                iteration1/qa.md
                iteration2/qa.md
                ...
        """
        self.logger.debug("_save_example_results function entered")
        self.logger.debug(f"Session has {len(session.iterations)} iterations")
        
        # Use configured results directory
        results_root = self.results_dir
        self.logger.debug(f"results_root = {results_root}")
        
        self.logger.debug("Creating directories")
        os.makedirs(results_root, exist_ok=True)
        self.logger.debug(f"Directory created successfully: {results_root}")
        
        # Execution identifier (timestamp-based)
        exec_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logger.debug(f"exec_id = {exec_id}")
        
        exec_dir = os.path.join(results_root, exec_id)
        self.logger.debug(f"exec_dir = {exec_dir}")
        
        os.makedirs(exec_dir, exist_ok=True)
        self.logger.debug(f"Created exec_dir successfully")

        # Save each iteration
        self.logger.debug(f"Starting to save {len(session.iterations)} iterations")
        for it in session.iterations:
            self.logger.debug(f"Processing iteration {it.iteration}")
            iter_dir = os.path.join(exec_dir, f"iteration{it.iteration}")
            self.logger.debug(f"iter_dir = {iter_dir}")
            
            os.makedirs(iter_dir, exist_ok=True)
            self.logger.debug(f"Created iter_dir successfully")
            
            md_content = f"# Iteration {it.iteration}\n\n"
            md_content += "## Question (Refined)\n\n"
            md_content += f"```\n{it.refined_question}\n```\n\n"
            md_content += "## Answer\n\n"
            md_content += f"```\n{it.answer}\n```\n\n"
            if it.reasoning_summary:
                md_content += "## Generator Reasoning Summary\n\n"
                md_content += f"```\n{it.reasoning_summary}\n```\n\n"
            md_content += "## Evaluation\n\n"
            md_content += f"```\n{it.evaluation_feedback}\n```\n\n"
            if it.evaluator_reasoning_summary:
                md_content += "## Evaluator Reasoning Summary\n\n"
                md_content += f"```\n{it.evaluator_reasoning_summary}\n```\n\n"
            if it.refiner_reasoning_summary:
                md_content += "## Prompt Refiner Reasoning Summary\n\n"
                md_content += f"```\n{it.refiner_reasoning_summary}\n```\n\n"

            # Save to file
            md_path = os.path.join(iter_dir, "qa.md")
            self.logger.debug(f"md_path = {md_path}")

            self.logger.debug(f"Writing to file: {md_path}")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            self.logger.debug(f"Successfully wrote iteration {it.iteration} file")

        # Save final answer summary
        self.logger.debug("Saving final answer summary")
        final_md_path = os.path.join(exec_dir, "final_answer.md")
        self.logger.debug(f"final_md_path = {final_md_path}")
        
        with open(final_md_path, "w", encoding="utf-8") as f:
            f.write("# Final Answer\n\n")
            f.write("```)\n")
            f.write(session.final_answer.strip())
            f.write("\n```)\n\n")
            f.write(f"_Total iterations_: {session.total_iterations}\n")
        
        self.logger.debug("Successfully wrote final_answer.md")
        self.logger.debug("_save_example_results function completed successfully")
