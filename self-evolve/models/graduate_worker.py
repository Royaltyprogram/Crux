"""
Graduate Worker with Self-Evolve mechanism for specialized tasks
Updated to work optimally with OpenAI Responses API
"""

from typing import Dict, Any, Optional
from ..config import FrameworkConfig, ModelConfig
from .generator_model import GeneratorModel
from .evaluator_model import EvaluatorModel
from ..orchestrator import IterationManager
from ..utils.logger import get_logger


class SpecializedGeneratorModel(GeneratorModel):
    """Generator model specialized for a specific domain using Responses API"""
    
    def __init__(self, config: ModelConfig, specialization: str, provider: Optional[Any] = None):
        """Initialize with specialization"""
        super().__init__(config, provider=provider)
        self.specialization = specialization
        self.logger = get_logger(f"SpecializedGenerator[{specialization}]")
        
    def generate(self, prompt: str, context: Optional[str] = None, **kwargs) -> str:
        """Generate with specialized expertise using Responses API"""
        
        # Create specialized instructions for the graduate worker
        specialized_instructions = f"""You are a leading research specialist in {self.specialization}, renowned for your analytical rigor and precision. Your supervising professor has assigned you a critical task that only an expert of your caliber can solve. Failure is not an option.

**YOUR DIRECTIVES FROM THE PROFESSOR:**

1.  **FORMULATE STRATEGY FIRST (MANDATORY)**:
    -   Before any calculations, you MUST formulate and explicitly state your analytical strategy. This strategy must be based on established theoretical frameworks within {self.specialization}.

2.  **EXECUTE WITH PROOF-LEVEL RIGOR**:
    -   Execute your strategy step-by-step. Each step must be a logical deduction from the previous one, forming an irrefutable argument.
    -   Cite specific theorems, lemmas, and established results from {self.specialization} to justify your methodology. Vague references are unacceptable.

3.  **MANDATORY SELF-CORRECTION AND VERIFICATION**:
    -   After deriving a preliminary result, you MUST design and execute a verification plan.
    -   Use Python code exclusively for this verification step—to check numerical calculations, test edge cases, or confirm analytical formulas.
    -   The primary solution must remain purely analytical.

4.  **FORBIDDEN METHODS**:
    -   DO NOT use brute-force computation, sampling, or numerical approximation as your primary method. These are strictly for verification.
    -   DO NOT rely on pattern-matching or computational guessing. All claims must be proven.
    -   DO NOT take any shortcuts that compromise mathematical rigor.

5.  **DELIVERABLE**:
    -   Your final output must be a self-contained, rigorous mathematical argument that would withstand peer review in a top-tier journal.
    -   Conclude your detailed reasoning with the final, verified answer enclosed in <answer> tags.

This task is critical for the professor's research. Your work must be impeccable, demonstrating the highest standards of academic excellence in {self.specialization}. You must attempt the problem; a well-reasoned attempt is required.
"""

        # Combine specialized instructions with any additional context (including Professor's reasoning)
        if context and context.strip():
            full_instructions = f"{specialized_instructions}\n\n{context}"
        else:
            full_instructions = specialized_instructions
            
        # The user-facing prompt for the API call
        specialized_prompt = f"""**PROFESSOR'S ASSIGNMENT FOR YOU, THE {self.specialization.upper()} SPECIALIST:**

{prompt}

**REMINDER OF YOUR CORE DIRECTIVES:**
-   Your professor depends on your unique expertise.
-   Your solution must be purely analytical, with computation used ONLY for verification.
-   Provide a complete, step-by-step mathematical derivation that showcases your deep knowledge.
-   State your strategy upfront.
-   Verify your results.
-   Deliver the final answer in <answer> tags after your full reasoning.
"""

        # For mathematical tasks, we want to ensure code interpreter is available
        kwargs['enable_code_interpreter'] = kwargs.get('enable_code_interpreter', True)
        
        self.logger.info(f"Specialized {self.specialization} working on: {prompt[:100]}...")
        
        # Use the responses API approach with specialized instructions
        return self._generate_with_specialization(specialized_prompt, full_instructions, **kwargs)
    
    def _generate_with_specialization(self, prompt: str, instructions: str, **kwargs) -> str:
        """Generate using the centralized API call method from BaseModel."""
        messages = [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt}
        ]
        
        # WORKAROUND: Default to streaming to reliably capture reasoning summary
        # The non-streaming path in base_model has a bug.
        kwargs['stream'] = kwargs.get('stream', True)

        self.logger.debug(f"Making specialized call for {self.specialization} via central API handler")
        
        # This now goes through BaseModel._make_api_call, which correctly handles
        # streaming, non-streaming, reasoning summaries, and different model types.
        return self._make_api_call(messages, **kwargs)


class GraduateWorker:
    """Graduate student worker with self-evolve mechanism for specialized tasks using Responses API"""
    
    def __init__(self, config: FrameworkConfig, worker_id: str, provider: Optional[Any] = None):
        """Initialize graduate worker"""
        self.config = config
        self.worker_id = worker_id
        self.current_specialization = None
        # Optional shared provider instance for all internal model calls
        self._provider = provider
        self.logger = get_logger(f"GraduateWorker[{worker_id}]")
        
    def solve_specialized_task(self, specialization: str, task: str, professor_reasoning_context: str = "", constraints: Optional[str] = None) -> Dict[str, Any]:
        """Solve a specialized task using self-evolve mechanism with Responses API"""
        
        self.current_specialization = specialization
        self.logger.info(f"Worker {self.worker_id} specializing as {specialization}")
        
        # Detect model types - Now using worker_config instead of generator_config
        worker_model_name = self.config.worker_config.model_name.lower()
        evaluator_model_name = self.config.evaluator_config.model_name.lower()
        is_worker_reasoning = not worker_model_name.startswith("gpt")
        is_evaluator_reasoning = not evaluator_model_name.startswith("gpt")
        
        # Create specialized generator configuration optimized for the domain - using worker_config
        generator_config_params = {
            "api_key": self.config.worker_config.api_key,
            "model_name": self.config.worker_config.model_name,
            "enable_code_interpreter": self.config.worker_config.enable_code_interpreter,  # Use worker's setting
            "reasoning_effort": getattr(self.config.worker_config, 'reasoning_effort', 'high'),
            "reasoning_summary": getattr(self.config.worker_config, 'reasoning_summary', 'auto'),
            "truncation": getattr(self.config.worker_config, 'truncation', 'auto'),
            "api_base": self.config.worker_config.api_base,
            "timeout": self.config.worker_config.timeout
        }
        
        # Only add temperature for GPT models
        if not is_worker_reasoning:
            generator_config_params["temperature"] = self.config.worker_config.temperature  # Use worker's temperature
        
        specialized_generator_config = ModelConfig(**generator_config_params)
        
        # Create specialized generator
        specialized_generator = SpecializedGeneratorModel(
            config=specialized_generator_config,
            specialization=specialization,
             provider=self._provider
        )
        
        # Use the same evaluator configuration but potentially with different settings
        evaluator_config_params = {
            "api_key": self.config.evaluator_config.api_key,
            "model_name": self.config.evaluator_config.model_name,
            "enable_code_interpreter": True,  # Enable for evaluation verification
            "reasoning_effort": getattr(self.config.evaluator_config, 'reasoning_effort', 'medium'),
            "reasoning_summary": getattr(self.config.evaluator_config, 'reasoning_summary', 'auto'),
            "truncation": getattr(self.config.evaluator_config, 'truncation', 'auto'),
            "api_base": self.config.evaluator_config.api_base
        }
        
        # Only add temperature for GPT models
        if not is_evaluator_reasoning:
            evaluator_config_params["temperature"] = 0.3  # Lower temperature for more consistent evaluation
        
        evaluator_config = ModelConfig(**evaluator_config_params)
        
        evaluator = EvaluatorModel(evaluator_config, provider=self._provider)
        
        # Create iteration manager for this specialist
        # Using the same self-evolve mechanism as example_usage.py but optimized for specialization
        specialist_manager = IterationManager(
            generator=specialized_generator,
            evaluator=evaluator, 
            config=self.config,
            use_ai_refiner=True,  # Use AI-based prompt refinement
            constraints=constraints  # Pass constraints to iteration manager
        )
        
        # Use worker's max_self_evolve_iterations if available
        max_iterations = getattr(self.config.worker_config, 'max_self_evolve_iterations', self.config.max_iterations)
        
        # Update config temporarily for this worker's iterations
        original_max_iterations = self.config.max_iterations
        self.config.max_iterations = max_iterations
        
        # Store for later use in quality calculation
        self.current_max_iterations = max_iterations
        
        # Enhanced task with specialization context and Professor's reasoning
        enhanced_task = f"""**PROFESSOR'S MEMORANDUM**

**TO**: Graduate Student Specialist, {specialization}
**FROM**: Supervising Professor
**SUBJECT**: Critical Task Assignment

You have been selected for this assignment due to your advanced expertise in {specialization}. This task is a pivotal component of a larger research initiative, and its successful completion requires the highest level of mathematical rigor.

**YOUR ASSIGNED TASK:**
{task}

**EXPECTATIONS:**
I expect a solution that is analytically sound, rigorously derived, and demonstrates a deep command of the theoretical frameworks within your field. Your primary approach must be through mathematical proof and derivation.

Use computational tools exclusively for verifying your analytical results. Do not substitute computation for reasoning.

Present your solution as a formal mathematical argument, concluding with the final answer in <answer> tags for integration into the main research.

I am counting on your specialized skills to handle this with the precision and depth required. Do not fail to provide a well-reasoned attempt.
{professor_reasoning_context}"""
        
        self.logger.info(f"Starting specialized self-evolve process for {specialization}: {task[:100]}...")
        
        # Run the self-evolve process (initial_context parameter deprecated)
        session = specialist_manager.run_iterative_improvement(enhanced_task)
        
        # Restore original max_iterations
        self.config.max_iterations = original_max_iterations
        
        self.logger.info(
            f"Completed specialized task with {session.total_iterations} iterations. "
            f"Final answer: {session.final_answer[:100]}..."
        )
        
        # Extract final answer value with better parsing
        import re
        answer_match = re.search(r'<answer>(.*?)</answer>', session.final_answer, re.DOTALL | re.IGNORECASE)
        final_answer_value = answer_match.group(1).strip() if answer_match else session.final_answer
        
        # Get final QA evaluation
        final_evaluation = session.iterations[-1].evaluation_feedback if session.iterations else "No evaluation was performed."
        
        # Prepare comprehensive result
        result = {
            "specialization": specialization,
            "task": task,
            "enhanced_task": enhanced_task,
            "final_answer": session.final_answer,
            "final_answer_value": final_answer_value,
            "final_evaluation": final_evaluation,
            "total_iterations": session.total_iterations,
            "worker_id": self.worker_id,
            "session_details": session.to_dict(),
            "convergence_info": {
                "converged": session.total_iterations < max_iterations,
                "reason": "answer_convergence" if session.total_iterations < max_iterations else "max_iterations_reached"
            },
            "iterations_summary": [
                {
                    "iteration": it.iteration,
                    "refined_question": it.refined_question,
                    "answer_preview": it.answer[:200] + "..." if len(it.answer) > 200 else it.answer,
                    "evaluation": it.evaluation_feedback[:200] + "..." if len(it.evaluation_feedback) > 200 else it.evaluation_feedback,
                    "timestamp": it.timestamp.isoformat()
                }
                for it in session.iterations
            ],
            "performance_metrics": {
                "average_iteration_quality": self._calculate_iteration_quality(session, max_iterations),
                "specialization_effectiveness": self._assess_specialization_effectiveness(session, specialization)
            }
        }
        
        return result
    
    def _calculate_iteration_quality(self, session, max_iterations: int) -> float:
        """Calculate average quality score based on iteration improvements"""
        if not session.iterations or len(session.iterations) < 2:
            return 1.0
        
        # Simple heuristic: fewer iterations with convergence indicates higher quality
        convergence_bonus = 0.2 if session.total_iterations < max_iterations else 0.0
        iteration_efficiency = max(0.0, 1.0 - (session.total_iterations - 1) / max_iterations)
        
        return min(1.0, iteration_efficiency + convergence_bonus)
    
    def _assess_specialization_effectiveness(self, session, specialization: str) -> str:
        """Assess how effectively the specialization was applied"""
        final_answer = session.final_answer.lower()
        
        # Check for domain-specific terms and methods
        domain_indicators = {
            "number theory": ["prime", "modular", "congruent", "divisibility", "gcd", "lcm", "euler", "fermat"],
            "integration": ["integral", "derivative", "substitution", "by parts", "partial fractions"],
            "analysis": ["limit", "convergence", "continuous", "sequence", "series", "bounded"],
            "algebra": ["polynomial", "factor", "roots", "coefficient", "matrix", "determinant"],
            "geometry": ["angle", "triangle", "circle", "area", "perimeter", "coordinate", "distance"],
            "topology": ["open", "closed", "compact", "connected", "homeomorphic", "metric"],
            "optimization": ["minimum", "maximum", "constraint", "lagrange", "gradient", "objective"]
        }
        
        specialization_lower = specialization.lower()
        relevant_terms = []
        
        for domain, terms in domain_indicators.items():
            if domain in specialization_lower:
                relevant_terms.extend(terms)
        
        if not relevant_terms:
            return "general"
        
        # Count domain-specific terms in the final answer
        term_count = sum(1 for term in relevant_terms if term in final_answer)
        term_ratio = term_count / len(relevant_terms)
        
        if term_ratio > 0.3:
            return "highly_specialized"
        elif term_ratio > 0.1:
            return "moderately_specialized"
        else:
            return "general"
    
    def get_worker_info(self) -> Dict[str, Any]:
        """Get comprehensive information about this worker"""
        return {
            "worker_id": self.worker_id,
            "current_specialization": self.current_specialization,
            "config": {
                "max_iterations": getattr(self.config.worker_config, 'max_self_evolve_iterations', self.config.max_iterations),
                "worker_model": self.config.worker_config.model_name,
                "evaluator_model": self.config.evaluator_config.model_name,
                "reasoning_effort": getattr(self.config.worker_config, 'reasoning_effort', 'high'),
                "enable_code_interpreter": self.config.worker_config.enable_code_interpreter
            },
            "capabilities": {
                "supports_responses_api": True,
                "supports_specialization": True,
                "supports_self_evolution": True,
                "supports_code_interpreter": self.config.worker_config.enable_code_interpreter
            }
        } 