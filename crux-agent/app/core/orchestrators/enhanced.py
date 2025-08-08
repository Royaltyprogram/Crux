"""
Enhanced mode orchestrator with Professor and multiple Specialists.
"""
import asyncio
from typing import Any, Callable, Dict, List, Optional

from app.core.agents.base import AbstractAgent, AgentContext
from app.core.agents.evaluator import EvaluatorAgent
from app.core.agents.professor import ProfessorAgent
from app.core.agents.refiner import RefinerAgent
from app.core.agents.specialist import SpecialistAgent
from app.core.engine.self_evolve import Problem, SelfEvolve, Solution
from app.core.providers.base import BaseProvider
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EnhancedRunner:
    """
    Enhanced mode orchestrator that uses:
    1. Professor to decompose problems
    2. Multiple Specialists each with their own Self-Evolve
    3. Professor to synthesize results
    """
    
    def __init__(
        self,
        provider: BaseProvider,
        max_iters_per_specialist: int = None,  # Will use settings.specialist_max_iters if None
        professor_max_iters: int = None,  # Will use settings.professor_max_iters if None
    ):
        """
        Initialize EnhancedRunner.
        
        Args:
            provider: LLM provider for all agents
            max_iters_per_specialist: Max iterations for each specialist's Self-Evolve
            professor_max_iters: Max iterations for Professor's Self-Evolve
        """
        self.provider = provider
        self._cancelled = False  # Add cancellation flag
        
        # Use settings defaults if not provided
        if max_iters_per_specialist is None:
            max_iters_per_specialist = settings.specialist_max_iters
        if professor_max_iters is None:
            professor_max_iters = settings.professor_max_iters
        
        self.max_iters_per_specialist = max_iters_per_specialist
        self.professor_max_iters = professor_max_iters
        
        # Create Professor (always uses Quality-First approach)
        self.professor = ProfessorAgent(provider=provider)
        # Propagate specialist iteration limit so Professor honors request overrides
        try:
            setattr(self.professor, 'specialist_max_iters', self.max_iters_per_specialist)
        except Exception:
            # Best-effort; fallback to Professor default if attribute cannot be set
            pass
        
        # Create shared evaluator and refiner for specialists
        self.evaluator = EvaluatorAgent(provider=provider)
        self.refiner = RefinerAgent(provider=provider)
        
        logger.info(
            f"EnhancedRunner initialized with "
            f"specialist_max_iters={max_iters_per_specialist}, professor_max_iters={professor_max_iters}"
        )
    
    def cancel(self):
        """Cancel the current solve operation."""
        self._cancelled = True
        logger.info("EnhancedRunner cancellation requested")
    
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled
    
    async def solve(
        self,
        question: str,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Solution:
        """
        Solve a problem using enhanced mode.
        
        Args:
            question: The question/problem to solve
            metadata: Additional metadata
            progress_callback: Optional callback for progress updates (progress, phase)
            
        Returns:
            Solution with synthesized answer
            
        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        logger.info(f"EnhancedRunner solving: {question[:100]}...")
        
        # Reset cancellation flag
        self._cancelled = False
        
        # Progress tracking state
        total_phases = 4  # Professor analysis, Specialist consultations, Professor synthesis, Finalization
        current_phase = 0
        
        def update_phase_progress(phase_progress: float, phase_name: str, reasoning_tokens: int = 0):
            """Update progress within current phase and include reasoning tokens."""
            if progress_callback:
                # Each phase gets equal weight for simplicity
                base_progress = current_phase / total_phases
                phase_weight = 1.0 / total_phases
                total_progress = base_progress + (phase_progress * phase_weight)
                # Include reasoning tokens in the progress metadata
                progress_metadata = {"reasoning_tokens": reasoning_tokens}
                progress_callback(total_progress, phase_name, progress_metadata)
        
        # Check for cancellation
        if self._cancelled:
            logger.info("EnhancedRunner cancelled before starting")
            raise asyncio.CancelledError("EnhancedRunner was cancelled")
        
        # Phase 1: Professor initial analysis
        current_phase = 0
        update_phase_progress(0.0, "Professor analyzing problem")
        
        # Create progress adapter for Professor's Self-Evolve
        def professor_progress(current_iter: int, max_iters: int, phase: str):
            if self._cancelled:
                return
            iter_progress = (current_iter - 1) / max_iters if max_iters > 0 else 0
            update_phase_progress(iter_progress, f"Professor analysis: {phase}")
        
        # Create Professor's Self-Evolve engine with progress callback
        professor_engine = SelfEvolve(
            generator=self.professor,
            evaluator=self.evaluator,
            refiner=self.refiner,
            max_iters=self.professor_max_iters,
            progress_callback=professor_progress,
        )
        
        # Enable partial results if job_id is provided in metadata
        if metadata and metadata.get("job_id"):
            professor_engine.job_id = metadata["job_id"]
            # Import redis client here to avoid circular imports
            try:
                import redis
                from app.settings import settings
                professor_engine.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                logger.info(f"Partial results enabled for enhanced job_id: {metadata['job_id']}")
            except Exception as e:
                logger.warning(f"Failed to setup Redis for enhanced partial results: {e}")
        
        # Set progress callback on Professor instance
        self.professor._progress_callback = update_phase_progress
        
        # Create problem for Professor
        professor_problem = Problem(
            question=question,
            context=None,  # Professor decides context for specialists autonomously
            constraints=None,  # Professor decides constraints for specialists autonomously
            metadata={
                **(metadata or {}),
                "max_iters_per_specialist": self.max_iters_per_specialist,
            },
        )
        
        # Phase 2: Run Professor's Self-Evolve (this will include specialist consultations)
        current_phase = 1
        update_phase_progress(0.0, "Professor consulting specialists")
        
        # Run Professor's Self-Evolve (Professor will use function calling to consult specialists)
        try:
            professor_solution = await professor_engine.solve(professor_problem)
        except asyncio.CancelledError:
            logger.info("EnhancedRunner solve was cancelled during Professor analysis")
            if progress_callback:
                progress_callback(1.0, "Cancelled")
            raise
        
        # Check for cancellation after professor solve
        if self._cancelled:
            logger.info("EnhancedRunner cancelled after professor solve")
            raise asyncio.CancelledError("EnhancedRunner was cancelled")
        
        # Phase 3: Extract and process specialist results
        current_phase = 2
        update_phase_progress(0.5, "Processing specialist consultations")
        
        # Extract specialist consultation results from Professor's evolution history
        specialist_results = []
        total_specialist_tokens = 0
        total_reasoning_tokens = 0
        
        for iteration in professor_solution.evolution_history:
            if "specialist_results" in iteration.get("metadata", {}).get("generator", {}):
                results = iteration["metadata"]["generator"]["specialist_results"]
                specialist_results.extend(results)
                
                # Aggregate specialist tokens and reasoning tokens
                for result in results:
                    specialist_tokens = result.get("metadata", {}).get("total_tokens", 0)
                    total_specialist_tokens += specialist_tokens
                    
                    # Aggregate reasoning tokens from specialist sessions
                    session_details = result.get("session_details", {})
                    for session_iter in session_details.get("iterations", []):
                        reasoning_tokens = session_iter.get("reasoning_tokens", 0)
                        total_reasoning_tokens += reasoning_tokens
                        # Update partial progress with reasoning tokens per iteration
                        update_phase_progress(0.5, "Specialist consultation in progress", reasoning_tokens)
            
            # Also aggregate reasoning tokens from Professor iterations
            professor_metadata = iteration.get("metadata", {}).get("generator", {})
            total_reasoning_tokens += professor_metadata.get("reasoning_tokens", 0)
        
        # Also check the final metadata
        if "specialist_results" in professor_solution.metadata:
            results = professor_solution.metadata["specialist_results"]
            specialist_results.extend(results)
            
            # Aggregate specialist tokens and reasoning tokens from final metadata
            for result in results:
                specialist_tokens = result.get("metadata", {}).get("total_tokens", 0)
                total_specialist_tokens += specialist_tokens
                
                # Aggregate reasoning tokens from specialist sessions
                session_details = result.get("session_details", {})
                for session_iter in session_details.get("iterations", []):
                    total_reasoning_tokens += session_iter.get("reasoning_tokens", 0)
        
        logger.info(f"Professor completed with {len(specialist_results)} specialist consultations")
        logger.info(f"Total specialist tokens: {total_specialist_tokens}, Professor tokens: {professor_solution.total_tokens}")
        
        # Check for cancellation after processing
        if self._cancelled:
            logger.info("EnhancedRunner cancelled after processing specialist results")
            raise asyncio.CancelledError("EnhancedRunner was cancelled")
        
        # Phase 4: Finalization
        current_phase = 3
        update_phase_progress(0.8, "Finalizing enhanced solution")
        
        # Calculate total tokens including specialists
        total_tokens = professor_solution.total_tokens + total_specialist_tokens
        
        # Update metadata and tokens
        professor_solution.metadata.update({
            "runner": "enhanced",
            "approach": "professor_function_calling",
            "specialist_consultations": len(specialist_results),
            "specialist_results": specialist_results,
            "professor_tokens": professor_solution.total_tokens,
            "specialist_tokens": total_specialist_tokens,
            "reasoning_tokens": total_reasoning_tokens,
        })
        
        # Update the total tokens in the solution
        professor_solution.total_tokens = total_tokens
        
        # Complete
        if progress_callback:
            progress_callback(1.0, "Enhanced solve completed")
        
        return professor_solution
    
    async def resume_solve(
        self,
        question: str,
        evolution_history: list,
        additional_iterations: int = 1,
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Solution:
        """
        Resume solving a problem from previous state with additional iterations.
        
        For enhanced mode, this involves resuming the Professor's Self-Evolve process
        which may continue to consult specialists as needed.
        
        Args:
            question: The question/problem to solve
            evolution_history: Previous evolution history
            additional_iterations: Number of additional iterations to run
            metadata: Additional metadata
            progress_callback: Optional callback for progress updates
            
        Returns:
            Solution from Professor's continued Self-Evolve
            
        Raises:
            asyncio.CancelledError: If cancellation was requested
        """
        logger.info(f"EnhancedRunner resuming: {question[:100]}... with +{additional_iterations} iterations")
        
        # Reset cancellation flag
        self._cancelled = False
        
        # Calculate new max_iters for professor
        current_iterations = len(evolution_history)
        new_professor_max_iters = current_iterations + additional_iterations
        
        # Progress tracking state
        total_phases = 3  # Resume setup, Professor continuation, Finalization
        current_phase = 0
        
        def update_phase_progress(phase_progress: float, phase_name: str):
            """Update progress within current phase."""
            if progress_callback:
                # Each phase gets equal weight for simplicity
                base_progress = current_phase / total_phases
                phase_weight = 1.0 / total_phases
                total_progress = base_progress + (phase_progress * phase_weight)
                progress_callback(total_progress, phase_name)
        
        # Check for cancellation
        if self._cancelled:
            logger.info("EnhancedRunner cancelled before resuming")
            raise asyncio.CancelledError("EnhancedRunner was cancelled")
        
        # Phase 1: Resume setup
        current_phase = 0
        update_phase_progress(0.0, f"Resuming from iteration {current_iterations}")
        
        # Create progress adapter for Professor's Self-Evolve
        def professor_progress(current_iter: int, max_iters: int, phase: str):
            if self._cancelled:
                return
            iter_progress = (current_iter - 1) / max_iters if max_iters > 0 else 0
            update_phase_progress(iter_progress, f"Professor continuation: {phase}")
        
        # Create Professor's resume Self-Evolve engine with progress callback
        professor_resume_engine = SelfEvolve(
            generator=self.professor,
            evaluator=self.evaluator,
            refiner=self.refiner,
            max_iters=new_professor_max_iters,
            progress_callback=professor_progress,
        )
        
        # Enable partial results if job_id is provided in metadata
        if metadata and metadata.get("job_id"):
            professor_resume_engine.job_id = metadata["job_id"]
            # Import redis client here to avoid circular imports
            try:
                import redis
                from app.settings import settings
                professor_resume_engine.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                logger.info(f"Partial results enabled for enhanced resume job_id: {metadata['job_id']}")
            except Exception as e:
                logger.warning(f"Failed to setup Redis for enhanced resume partial results: {e}")
        
        # Set progress callback on Professor instance for specialist consultations
        self.professor._progress_callback = update_phase_progress
        
        # Create problem for Professor resume
        professor_problem = Problem(
            question=question,
            context=None,  # Professor decides context for specialists autonomously
            constraints=None,  # Professor decides constraints for specialists autonomously
            metadata={
                **(metadata or {}),
                "max_iters_per_specialist": self.max_iters_per_specialist,
                "resumed_from_iteration": current_iterations,
            },
        )
        
        # Phase 2: Resume Professor's Self-Evolve
        current_phase = 1
        update_phase_progress(0.0, "Professor continuing analysis")
        
        # Resume Professor's Self-Evolve from where it left off
        try:
            professor_solution = await professor_resume_engine.resume_solve(
                problem=professor_problem,
                evolution_history=evolution_history.copy(),  # Make a copy to avoid mutations
                start_iteration=current_iterations + 1
            )
        except asyncio.CancelledError:
            logger.info("EnhancedRunner resume was cancelled during Professor continuation")
            if progress_callback:
                progress_callback(1.0, "Cancelled")
            raise
        
        # Check for cancellation after professor resume
        if self._cancelled:
            logger.info("EnhancedRunner cancelled after professor resume")
            raise asyncio.CancelledError("EnhancedRunner was cancelled")
        
        # Phase 3: Process continuation results and finalization
        current_phase = 2
        update_phase_progress(0.5, "Processing continued specialist consultations")
        
        # Extract specialist consultation results from Professor's evolution history
        # This includes both original and new consultations
        specialist_results = []
        total_specialist_tokens = 0
        total_reasoning_tokens = 0

        for iteration in professor_solution.evolution_history:
            if "specialist_results" in iteration.get("metadata", {}).get("generator", {}):
                results = iteration["metadata"]["generator"]["specialist_results"]
                specialist_results.extend(results)
                
                # Aggregate specialist tokens and reasoning tokens
                for result in results:
                    specialist_tokens = result.get("metadata", {}).get("total_tokens", 0)
                    total_specialist_tokens += specialist_tokens
                    
                    # Aggregate reasoning tokens from specialist sessions
                    session_details = result.get("session_details", {})
                    for session_iter in session_details.get("iterations", []):
                        total_reasoning_tokens += session_iter.get("reasoning_tokens", 0)
            
            # Also aggregate reasoning tokens from Professor iterations
            professor_metadata = iteration.get("metadata", {}).get("generator", {})
            total_reasoning_tokens += professor_metadata.get("reasoning_tokens", 0)
        
        # Also check the final metadata
        if "specialist_results" in professor_solution.metadata:
            results = professor_solution.metadata["specialist_results"]
            specialist_results.extend(results)
            
            # Aggregate specialist tokens and reasoning tokens from final metadata
            for result in results:
                specialist_tokens = result.get("metadata", {}).get("total_tokens", 0)
                total_specialist_tokens += specialist_tokens
                
                # Aggregate reasoning tokens from specialist sessions
                session_details = result.get("session_details", {})
                for session_iter in session_details.get("iterations", []):
                    total_reasoning_tokens += session_iter.get("reasoning_tokens", 0)

        logger.info(f"Professor continuation completed with {len(specialist_results)} total specialist consultations")
        logger.info(f"Total specialist tokens: {total_specialist_tokens}, Professor tokens: {professor_solution.total_tokens}")
        
        # Check for cancellation after processing
        if self._cancelled:
            logger.info("EnhancedRunner cancelled after processing continued specialist results")
            raise asyncio.CancelledError("EnhancedRunner was cancelled")
        
        # Finalization
        update_phase_progress(0.8, "Finalizing continued enhanced solution")
        
        # Calculate total tokens including specialists
        total_tokens = professor_solution.total_tokens + total_specialist_tokens
        
        # Update metadata and tokens
        professor_solution.metadata.update({
            "runner": "enhanced",
            "approach": "professor_function_calling",
            "specialist_consultations": len(specialist_results),
            "specialist_results": specialist_results,
            "professor_tokens": professor_solution.total_tokens,
            "specialist_tokens": total_specialist_tokens,
            "reasoning_tokens": total_reasoning_tokens,
            "resumed_from_iteration": current_iterations,
        })
        
        # Update the total tokens in the solution
        professor_solution.total_tokens = total_tokens
        
        # Complete
        if progress_callback:
            progress_callback(1.0, "Enhanced resume completed")
        
        return professor_solution
    
    def get_config(self) -> Dict[str, Any]:
        """Get runner configuration."""
        return {
            "mode": "enhanced",
            "max_iters_per_specialist": self.max_iters_per_specialist,
            "professor_max_iters": self.professor_max_iters,
            "provider": self.provider.__class__.__name__,
        } 