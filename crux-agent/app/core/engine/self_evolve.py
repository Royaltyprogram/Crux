"""
Self-Evolve engine for iterative improvement.
"""
import asyncio
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from app.core.agents.base import AbstractAgent, AgentContext, AgentResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Problem(BaseModel):
    """Input problem/question."""
    
    question: str = Field(..., description="The problem or question to solve")
    context: Optional[str] = Field(None, description="Additional context")
    constraints: Optional[str] = Field(None, description="Constraints or requirements")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class Solution(BaseModel):
    """Solution output from Self-Evolve."""
    
    output: str = Field(..., description="Final solution/answer")
    iterations: int = Field(..., ge=1, description="Number of iterations performed")
    evolution_history: list[Dict[str, Any]] = Field(default_factory=list, description="History of evolution")
    total_tokens: int = Field(0, description="Total tokens used")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SelfEvolve:
    """
    Self-Evolve engine that iteratively improves answers through generation, evaluation, and refinement.
    """
    
    def __init__(
        self,
        generator: AbstractAgent,
        evaluator: AbstractAgent,
        refiner: AbstractAgent,
        *,
        max_iters: int = 3,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ):
        """
        Initialize Self-Evolve engine.
        
        Args:
            generator: Agent that generates answers
            evaluator: Agent that evaluates answer quality  
            refiner: Agent that refines prompts based on feedback
            max_iters: Maximum number of iterations
            progress_callback: Optional callback for progress updates (current_iter, max_iters, phase)
        """
        self.generator = generator
        self.evaluator = evaluator
        self.refiner = refiner
        self.max_iters = max_iters
        self.progress_callback = progress_callback
        self._cancelled = False  # Add cancellation flag
        
        logger.info(f"SelfEvolve initialized with max_iters={max_iters}")
    
    def cancel(self):
        """Cancel the current solve operation."""
        self._cancelled = True
        logger.info("SelfEvolve cancellation requested")
    
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled
    
    async def solve(self, problem: Problem) -> Solution:
        """
        Solve a problem using the Self-Evolve algorithm.
        
        Args:
            problem: Problem to solve
            
        Returns:
            Solution with final answer and metadata
            
        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        return await self._solve_internal(problem, start_iteration=1, evolution_history=[])

    async def resume_solve(self, problem: Problem, evolution_history: list, start_iteration: int) -> Solution:
        """
        Resume solving a problem from a previous state.
        
        Args:
            problem: Problem to solve
            evolution_history: Previous evolution history
            start_iteration: Iteration to start from
            
        Returns:
            Solution with final answer and metadata
            
        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        return await self._solve_internal(problem, start_iteration, evolution_history)

    async def _solve_internal(self, problem: Problem, start_iteration: int = 1, evolution_history: list = None) -> Solution:
        """
        Internal method to solve a problem using the Self-Evolve algorithm with an option to resume.
        
        Args:
            problem: Problem to solve
            start_iteration: Iteration to start from
            evolution_history: Existing evolution history
            
        Returns:
            Solution with final answer and metadata
            
        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        if evolution_history is None:
            evolution_history = []
            
        logger.info(f"Starting Self-Evolve from iteration {start_iteration} for: {problem.question[:100]}...")

        # Reset cancellation flag
        self._cancelled = False

        # Initialize tracking variables
        if evolution_history and "refined_prompt" in evolution_history[-1]:
            prompt = evolution_history[-1]["refined_prompt"]
        else:
            prompt = self._create_initial_prompt(problem)
            
        # Initialize additional tracking variables
        best_iteration = None        # Dict from evolution_history
        best_output = ""
        fallback_triggered = False

        # Calculate tokens from previous iterations
        total_tokens = 0
        for item in evolution_history:
            if "metadata" in item:
                gen_tokens = item["metadata"].get("generator", {}).get("tokens_used", 0)
                eval_tokens = item["metadata"].get("evaluator", {}).get("tokens_used", 0)
                refiner_tokens = item["metadata"].get("refiner", {}).get("tokens_used", 0)
                total_tokens += gen_tokens + eval_tokens + refiner_tokens
                
        current_output = evolution_history[-1]["output"] if evolution_history else ""
        should_stop = False

        iteration = start_iteration
        while iteration <= self.max_iters:
            # Check for cancellation
            if self._cancelled:
                logger.info(f"Self-Evolve cancelled at iteration {iteration}")
                raise asyncio.CancelledError("Self-Evolve was cancelled")

            logger.info(f"Self-Evolve iteration {iteration}/{self.max_iters}")

            # Update progress if callback provided
            if self.progress_callback:
                self.progress_callback(iteration, self.max_iters, f"Self-Evolve iteration {iteration}/{self.max_iters}")

            # Step 1: Generate answer with validation
            gen_context = AgentContext(
                prompt=prompt,
                additional_context={
                    "constraints": problem.constraints,
                    "context": problem.context,
                },
            )
            
            # Try generation with retries for invalid outputs
            gen_result = None
            output = None
            retry_count = 0
            max_retries_per_iteration = 4  # Increase retries from 2 to 4
            generation_successful = False
            
            while retry_count <= max_retries_per_iteration:
                try:
                    gen_result = await self.generator.run(gen_context)
                    output = gen_result.output
                    
                    # Validate the generated output
                    if self._is_valid_output(output):
                        generation_successful = True
                        break  # Valid output, proceed
                    else:
                        logger.warning(f"Invalid output detected in iteration {iteration}, retry {retry_count + 1}: {repr(output[:100])}")
                        retry_count += 1
                        if retry_count <= max_retries_per_iteration:
                            continue
                        else:
                            # TODO: New control-flow injection point - consider alternative handling when max retries are reached
                            logger.error(f"Max retries reached for iteration {iteration} with invalid output")
                            break
                            
                except Exception as e:
                    logger.error(f"Generation failed in iteration {iteration}, retry {retry_count + 1}: {e}")
                    retry_count += 1
                    if retry_count <= max_retries_per_iteration:
                        continue
                    else:
                        # Create a fallback result with error message
                        gen_result = type('GenResult', (), {
                            'output': f"Generation failed after {max_retries_per_iteration + 1} attempts: {str(e)}",
                            'metadata': {'error': str(e), 'fallback': True},
                            'tokens_used': 0
                        })()
                        output = gen_result.output
                        break
            
            # If we never got a valid output, skip this iteration entirely
            if not generation_successful:
                logger.error(f"Skipping iteration {iteration} due to persistent invalid output after {max_retries_per_iteration + 1} attempts")
                if best_iteration is not None:
                    fallback_triggered = True
                    break  # Exit the main while loop
                else:
                    raise Exception("No valid iteration found; marking task as failed.")

            # Extract reasoning summary from generator
            generator_reasoning_summary = gen_result.metadata.get("reasoning_summary", "")
            current_output = output

            # Track tokens
            if gen_result.tokens_used:
                total_tokens += gen_result.tokens_used

            # Check for cancellation after generation
            if self._cancelled:
                logger.info(f"Self-Evolve cancelled after generation in iteration {iteration}")
                raise asyncio.CancelledError("Self-Evolve was cancelled")

            # Step 2: Evaluate answer
            # For professor, skip evaluation in the final iteration (but only if we've had multiple iterations)
            eval_result = None
            should_stop = False
            if self.generator.role == "professor" and iteration == self.max_iters and iteration > 1:
                logger.info("Skipping final evaluation for professor.")
                should_stop = True
            else:
                # Double-check output validity before evaluation (defense in depth)
                if not self._is_valid_output(output):
                    logger.warning(f"Skipping evaluation for invalid output in iteration {iteration}")
                    # Create a mock evaluation result that won't trigger stop
                    eval_result = type('EvalResult', (), {
                        'feedback': 'Evaluation skipped due to invalid generator output',
                        'metadata': {'should_stop': False, 'status': 'skipped_invalid_output'},
                        'tokens_used': 0
                    })()
                else:
                    eval_context = AgentContext(
                        prompt=problem.question,  # Original question for evaluation
                        output=output,
                        additional_context={
                            "constraints": problem.constraints,
                            "context": problem.context,
                            "generator_reasoning_summary": generator_reasoning_summary,
                        },
                    )
                    eval_result = await self.evaluator.run(eval_context)

                # Extract evaluator reasoning summary
                evaluator_reasoning_summary = eval_result.metadata.get("reasoning_summary", "")

                # Track tokens
                if eval_result.tokens_used:
                    total_tokens += eval_result.tokens_used

                # Check for <stop> token
                should_stop = eval_result.metadata.get("should_stop", False)

                # Check for cancellation after evaluation
                if self._cancelled:
                    logger.info(f"Self-Evolve cancelled after evaluation in iteration {iteration}")
                    raise asyncio.CancelledError("Self-Evolve was cancelled")

            # Record iteration
            iteration_data = {
                "iteration": iteration,
                "prompt": prompt,
                "output": output,
                "feedback": eval_result.feedback if eval_result else "Final iteration, evaluation skipped.",
                "should_stop": should_stop,
                "metadata": {
                    "generator": gen_result.metadata,
                    "evaluator": eval_result.metadata if eval_result else {"status": "skipped"},
                },
            }
            evolution_history.append(iteration_data)

            # Update additional tracking variables after successful generation
            best_iteration = iteration_data
            best_output = output
            fallback_triggered = 'fallback' in gen_result.metadata

            logger.info(f"Iteration {iteration} complete. Should stop: {should_stop}")

            # Check exit conditions
            if should_stop:
                logger.info(f"Evaluator issued <stop> token after iteration {iteration}. Solution is complete.")
                logger.info(f"Final evaluation feedback: {eval_result.feedback[:200] if eval_result else 'No evaluation'}...")
                break

            # Step 3: Refine prompt for next iteration (if not last iteration)
            if iteration < self.max_iters:
                # Ensure we have an evaluation result before refining
                if eval_result:
                    refine_context = AgentContext(
                        prompt=prompt,
                        feedback=eval_result.feedback,
                        additional_context={
                            "should_stop": should_stop,
                            "constraints": problem.constraints,
                            "context": problem.context,
                            "evaluator_reasoning_summary": evaluator_reasoning_summary,
                            "current_answer": current_output,
                            "iteration": iteration,
                        },
                    )
                    refine_result = await self.refiner.run(refine_context)
                    prompt = refine_result.output

                    # Track tokens
                    if refine_result.tokens_used:
                        total_tokens += refine_result.tokens_used

                    # Add refinement data to iteration
                    iteration_data["refined_prompt"] = prompt
                    iteration_data["metadata"]["refiner"] = refine_result.metadata

                    # Check for cancellation after refinement
                    if self._cancelled:
                        logger.info(f"Self-Evolve cancelled after refinement in iteration {iteration}")
                        raise asyncio.CancelledError("Self-Evolve was cancelled")
                else:
                    logger.info("Skipping refinement due to skipped evaluation.")
            
            # Increment iteration counter only after successful completion
            iteration += 1

        # Final cancellation check
        if self._cancelled:
            logger.info("Self-Evolve cancelled before creating final solution")
            raise asyncio.CancelledError("Self-Evolve was cancelled")

        # Calculate actual completed iterations from evolution history
        completed_iterations = len(evolution_history)
        final_iteration = iteration - 1  # iteration is incremented after completion
        
        # Determine final iteration and stop reason based on fallback status
        if fallback_triggered:
            final_iter = best_iteration
            stop_reason = "fallback_to_best"
        else:
            final_iter = evolution_history[-1]
            stop_reason = "evaluator_stop" if should_stop else "max_iterations"
        
        # Create final solution
        solution = Solution(
            output=final_iter["output"],
            iterations=completed_iterations,
            evolution_history=evolution_history,
            total_tokens=total_tokens,
            metadata={
                "problem": problem.dict(),
                "converged": should_stop,
                "final_iteration": final_iteration,
                "stop_reason": stop_reason,
            },
        )
        
        # Add fallback metadata
        solution.metadata["stop_reason"] = stop_reason
        solution.metadata["fallback_used"] = fallback_triggered

        logger.info(
            f"Self-Evolve complete. Converged: {should_stop}, "
            f"Iterations: {completed_iterations}, Tokens: {total_tokens}"
        )

        return solution

    def _create_initial_prompt(self, problem: Problem) -> str:
        """
        Create initial prompt from problem.
        
        Args:
            problem: Input problem
            
        Returns:
            Initial prompt string
        """
        prompt_parts = [problem.question]
        
        if problem.context:
            prompt_parts.append(f"\nContext: {problem.context}")
        
        if problem.constraints:
            prompt_parts.append(f"\nConstraints: {problem.constraints}")
        
        return "\n".join(prompt_parts)
    
    def _is_valid_output(self, output: str) -> bool:
        """
        Validate if an output is worth counting as a real iteration.
        
        Args:
            output: Generated output to validate
            
        Returns:
            True if output is valid, False otherwise
        """
        if not output:
            return False
            
        output_stripped = output.strip()
        
        # Check for completely empty output
        if not output_stripped:
            return False
            
        # Check for placeholder outputs
        if output_stripped in ["...", "…", "[content continues]", "[generating...]"]:
            return False
            
        # Check for error messages
        error_patterns = [
            "i apologize, but i encountered an error",
            "i'm sorry, but an error occurred",
            "unable to generate",
            "generation failed",
            "error generating",
            "cannot process",
            "failed to process",
        ]
        
        output_lower = output_stripped.lower()
        for pattern in error_patterns:
            if pattern in output_lower:
                return False
                
        # Check for outputs that are too short to be meaningful (less than 10 words)
        word_count = len(output_stripped.split())
        if word_count < 10:
            return False
            
        return True
    
    def get_config(self) -> Dict[str, Any]:
        """Get engine configuration."""
        return {
            "max_iters": self.max_iters,
            "generator": self.generator.role,
            "evaluator": self.evaluator.role,
            "refiner": self.refiner.role,
        }
