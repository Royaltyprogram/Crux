"""
Basic mode orchestrator using a single Self-Evolve instance.
"""
import asyncio
from typing import Any, Callable, Dict, Optional

from app.core.agents.base import AbstractAgent
from app.core.agents.evaluator import EvaluatorAgent
from app.core.agents.generator import GeneratorAgent
from app.core.agents.refiner import RefinerAgent
from app.core.engine.self_evolve import Problem, SelfEvolve, Solution
from app.core.providers.base import BaseProvider
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BasicRunner:
    """
    Basic mode orchestrator that uses a single Self-Evolve instance
    with a generator, evaluator, and refiner.
    """
    
    def __init__(
        self,
        provider: BaseProvider,
        generator_agent: Optional[AbstractAgent] = None,
        max_iters: int = None,  # Will use settings.max_iters if None
    ):
        """
        Initialize BasicRunner.
        
        Args:
            provider: LLM provider for all agents
            generator_agent: Optional custom generator agent
            max_iters: Maximum iterations for Self-Evolve
        """
        self.provider = provider
        self._cancelled = False  # Add cancellation flag
        
        # Use settings default if not provided
        if max_iters is None:
            max_iters = settings.max_iters
        
        # Use provided generator or create a default one
        if generator_agent:
            self.generator = generator_agent
        else:
            # Create a general-purpose generator
            self.generator = GeneratorAgent(provider=provider)
        
        # Create evaluator and refiner
        self.evaluator = EvaluatorAgent(provider=provider)
        self.refiner = RefinerAgent(provider=provider)
        
        # Create Self-Evolve engine
        self.engine = SelfEvolve(
            generator=self.generator,
            evaluator=self.evaluator,
            refiner=self.refiner,
            max_iters=max_iters,
        )
        
        logger.info(f"BasicRunner initialized with max_iters={max_iters}")
    
    def cancel(self):
        """Cancel the current solve operation."""
        self._cancelled = True
        if hasattr(self.engine, 'cancel'):
            self.engine.cancel()
        logger.info("BasicRunner cancellation requested")
    
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled
    
    async def solve(
        self,
        question: str,
        context: Optional[str] = None,
        constraints: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Solution:
        """
        Solve a problem using basic mode.
        
        Args:
            question: The question/problem to solve
            context: Additional context
            constraints: Any constraints or requirements
            metadata: Additional metadata
            progress_callback: Optional callback for progress updates (progress, phase)
            
        Returns:
            Solution from Self-Evolve
            
        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        logger.info(f"BasicRunner solving: {question[:100]}...")
        
        # Reset cancellation flag
        self._cancelled = False
        
        # Create progress adapter for SelfEvolve
        def self_evolve_progress(current_iter: int, max_iters: int, phase: str):
            if progress_callback:
                # Calculate progress based on iteration
                progress = (current_iter - 1) / max_iters  # Start from 0 for first iteration
                progress_callback(0.2 + 0.7 * progress, phase)  # 20% ~ 90% range
        
        # Set progress callback on SelfEvolve engine
        self.engine.progress_callback = self_evolve_progress
        
        # Initial progress
        if progress_callback:
            progress_callback(0.1, "Starting basic solve")
        
        # Check for cancellation
        if self._cancelled:
            logger.info("BasicRunner cancelled before starting")
            raise asyncio.CancelledError("BasicRunner was cancelled")
        
        # Create problem
        problem = Problem(
            question=question,
            context=context,
            constraints=constraints,
            metadata=metadata or {},
        )
        
        # Run Self-Evolve
        try:
            solution = await self.engine.solve(problem)
        except asyncio.CancelledError:
            logger.info("BasicRunner solve was cancelled")
            if progress_callback:
                progress_callback(1.0, "Cancelled")
            raise
        
        # Final progress
        if progress_callback:
            progress_callback(0.95, "Finalizing solution")
        
        # Add runner info to metadata
        solution.metadata["runner"] = "basic"
        solution.metadata["engine_config"] = self.engine.get_config()
        
        if progress_callback:
            progress_callback(1.0, "Completed")
        
        return solution
    
    def get_config(self) -> Dict[str, Any]:
        """Get runner configuration."""
        return {
            "mode": "basic",
            "generator": self.generator.role,
            "provider": self.provider.__class__.__name__,
            "engine": self.engine.get_config(),
        } 