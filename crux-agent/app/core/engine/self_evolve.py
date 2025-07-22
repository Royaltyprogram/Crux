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
        logger.info(f"Starting Self-Evolve for: {problem.question[:100]}...")
        
        # Reset cancellation flag
        self._cancelled = False
        
        # Initialize tracking variables
        prompt = self._create_initial_prompt(problem)
        evolution_history = []
        total_tokens = 0
        current_output = ""
        should_stop = False
        
        for iteration in range(1, self.max_iters + 1):
            # Check for cancellation
            if self._cancelled:
                logger.info(f"Self-Evolve cancelled at iteration {iteration}")
                raise asyncio.CancelledError("Self-Evolve was cancelled")
            
            logger.info(f"Self-Evolve iteration {iteration}/{self.max_iters}")
            
            # Update progress if callback provided
            if self.progress_callback:
                self.progress_callback(iteration, self.max_iters, f"Self-Evolve iteration {iteration}/{self.max_iters}")
            
            # Step 1: Generate answer
            gen_context = AgentContext(
                prompt=prompt,
                additional_context={
                    "constraints": problem.constraints,
                    "context": problem.context,
                }
            )
            gen_result = await self.generator.run(gen_context)
            output = gen_result.output

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
            # For professor, skip evaluation in the final iteration
            eval_result = None
            should_stop = False
            if self.generator.role == "professor" and iteration == self.max_iters:
                logger.info("Skipping final evaluation for professor.")
                should_stop = True
            else:
                eval_context = AgentContext(
                    prompt=problem.question,  # Original question for evaluation
                    output=output,
                    additional_context={
                        "constraints": problem.constraints,
                        "context": problem.context,
                        "generator_reasoning_summary": generator_reasoning_summary,
                    }
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

            logger.info(f"Iteration {iteration} complete. Should stop: {should_stop}")
            
            # Check exit conditions
            if should_stop:
                logger.info("Evaluator issued <stop> token. Solution is complete.")
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
        
        # Final cancellation check
        if self._cancelled:
            logger.info("Self-Evolve cancelled before creating final solution")
            raise asyncio.CancelledError("Self-Evolve was cancelled")
        
        # Create final solution
        solution = Solution(
            output=current_output,
            iterations=iteration,
            evolution_history=evolution_history,
            total_tokens=total_tokens,
            metadata={
                "problem": problem.dict(),
                "converged": should_stop,
                "final_iteration": iteration,
                "stop_reason": "evaluator_stop" if should_stop else "max_iterations",
            },
        )
        
        logger.info(
            f"Self-Evolve complete. Converged: {should_stop}, "
            f"Iterations: {iteration}, Tokens: {total_tokens}"
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
    
    def get_config(self) -> Dict[str, Any]:
        """Get engine configuration."""
        return {
            "max_iters": self.max_iters,
            "generator": self.generator.role,
            "evaluator": self.evaluator.role,
            "refiner": self.refiner.role,
        } 