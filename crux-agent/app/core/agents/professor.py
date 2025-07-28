"""
Professor agent for orchestrating specialists.
"""
import json
from typing import Any, Dict, List, Optional, Callable

from app.core.agents.base import AbstractAgent, AgentContext, AgentResult
from app.core.agents.prompts.graduate_worker_prompt import build_enhanced_task_prompt, build_specialist_consultation_continuation_prompt
from app.core.agents.prompts.professor_prompt import get_professor_quality_first_prompt
from app.core.providers.base import BaseProvider
from app.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ProfessorAgent(AbstractAgent):
    """
    Professor agent that decomposes problems and orchestrates specialists.
    Uses Quality-First approach with unlimited time philosophy for maximum rigor.
    """
    
    def __init__(
        self,
        provider: BaseProvider,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """Initialize Professor agent with Quality-First approach."""
        # Always use Quality-First approach for maximum rigor
        selected_prompt = system_prompt or get_professor_quality_first_prompt()
        
        super().__init__(
            role="professor",
            provider=provider,
            system_prompt=selected_prompt,
            temperature=temperature,
        )
        
        logger.info("Professor initialized with Quality-First approach (unlimited time philosophy)")
        
        # Define the specialist consultation tool
        self.specialist_tool = {
            "type": "function",
            "name": "consult_graduate_specialist",
            "description": "Consult a graduate student specialist who will use self-evolving iterative improvement to solve specific tasks accurately",
            "strict": True,
            "parameters": {
                "type": "object",
                "required": [
                    "specialization",
                    "specific_task",
                    "context_for_specialist",
                    "problem_constraints"
                ],
                "properties": {
                    "specialization": {
                        "type": "string",
                        "description": "The area of specialization needed (e.g. 'symbolic integration expert', 'number theory specialist', 'optimization expert')"
                    },
                    "specific_task": {
                        "type": "string",
                        "description": "The specific mathematical task for the specialist to solve using the self-evolve mechanism"
                    },
                    "context_for_specialist": {
                        "type": "string",
                        "description": "Relevant context and information the specialist needs"
                    },
                    "problem_constraints": {
                        "type": "string",
                        "description": "Global problem constraints that must be strictly followed throughout the session (in YAML or JSON format, or plain text). Examples: 'c₁,c₂ are absolute constants', 'KL divergence reduction conditions', 'boundary conditions', etc."
                    }
                },
                "additionalProperties": False
            }
        }
    
    async def run(self, context: AgentContext) -> AgentResult:
        """
        Execute professor logic with function calling capabilities.
        
        Args:
            context: Execution context with problem
            
        Returns:
            Result with specialist consultations and synthesis
        """
        logger.info(f"Professor analyzing problem: {context.prompt[:100]}...")
        
        # Extract context information
        additional_context = context.additional_context or {}
        constraints = additional_context.get("constraints", "")
        progress_callback = getattr(self, '_progress_callback', None)
        
        # Create the initial prompt for function calling
        initial_prompt = f"""
Problem: {context.prompt}

Context: {additional_context.get("context", "")}

Constraints: {constraints}

You are a Professor with access to graduate student specialists. Analyze this problem and determine:
1. Whether you can solve it directly or need specialist consultation
2. If specialists are needed, identify the specific expertise required
3. Use the consult_graduate_specialist function to delegate specific tasks
4. Synthesize the results into a comprehensive solution

Begin your analysis and make specialist consultations as needed.
"""
        
        try:
            # Generate response with function calling capability
            response = await self._generate_with_functions(
                prompt=initial_prompt,
                functions=[self.specialist_tool],
                temperature=self.temperature,
            )
            
            # Count tokens for initial analysis
            tokens_used = self.provider.count_tokens(initial_prompt)
            if isinstance(response, str):
                tokens_used += self.provider.count_tokens(response)
            elif hasattr(response, 'content'):
                tokens_used += self.provider.count_tokens(response.content)
            
            # Parse the response and handle function calls
            specialist_results = []
            
            # Process function calls if any
            if hasattr(response, 'function_calls') and response.function_calls:
                logger.info(f"Professor making {len(response.function_calls)} specialist consultations")
                for i, func_call in enumerate(response.function_calls, 1):
                    if func_call.name == "consult_graduate_specialist":
                        logger.info(f"Specialist consultation {i}: {func_call.arguments.get('specialization', 'unknown')}")
                        specialist_result = await self._execute_specialist_consultation(
                            func_call.arguments,
                            context.prompt,
                            constraints,
                            progress_callback
                        )
                        specialist_results.append(specialist_result)
            
            # Get the final synthesis
            if specialist_results:
                synthesis = await self._synthesize_specialist_results(
                    context.prompt,
                    specialist_results,
                    constraints
                )
                # Add synthesis tokens
                tokens_used += self.provider.count_tokens(synthesis)
            else:
                synthesis = response if isinstance(response, str) else response.content
            
            logger.info(f"Professor completed analysis with {len(specialist_results)} specialist consultations, tokens: {tokens_used}")
            
            return AgentResult(
                output=synthesis,
                metadata={
                    "specialist_consultations": len(specialist_results),
                    "specialist_results": specialist_results,
                    "approach": "function_calling",
                    "function_calling_used": True,
                },
                tokens_used=tokens_used,
            )
            
        except Exception as e:
            logger.error(f"Professor analysis failed: {e}")
            # Fallback to simple text response
            fallback_prompt = f"Analyze and provide solution for: {context.prompt}"
            response = await self._generate(
                prompt=fallback_prompt,
            )
            tokens_used = self.provider.count_tokens(fallback_prompt + response)
            
            return AgentResult(
                output=response,
                metadata={"error": str(e), "fallback": True},
                tokens_used=tokens_used,
            )
    
    async def _generate_with_functions(
        self,
        prompt: str,
        functions: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> Any:
        """
        Generate response with function calling capability.
        
        Args:
            prompt: The prompt to generate from
            functions: List of available functions
            temperature: Generation temperature
            
        Returns:
            Response with possible function calls
        """
        try:
            # Check if provider supports function calling
            if hasattr(self.provider, 'complete_with_functions'):
                return await self.provider.complete_with_functions(
                    prompt=prompt,
                    functions=functions,
                    system_prompt=self.system_prompt,
                    temperature=temperature if temperature is not None else self.temperature,
                )
            else:
                # Fallback to regular generation
                logger.warning("Provider doesn't support function calling, falling back to regular generation")
                return await self._generate(
                    prompt=prompt,
                    temperature=temperature if temperature is not None else self.temperature,
                )
        except Exception as e:
            logger.error(f"Function calling failed: {e}")
            # Fallback to regular generation
            return await self._generate(
                prompt=prompt,
                temperature=temperature if temperature is not None else self.temperature,
            )
    
    async def _execute_specialist_consultation(
        self,
        arguments: Dict[str, Any],
        original_problem: str,
        constraints: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a specialist consultation based on function call arguments.
        
        Args:
            arguments: Function call arguments
            original_problem: The original problem being solved
            constraints: Problem constraints
            
        Returns:
            Specialist consultation result
        """
        try:
            # The arguments from the LLM may be a JSON string.
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode specialist arguments: {arguments}")
                    return {
                        "specialization": "unknown",
                        "task": "",
                        "output": "Failed to decode arguments for specialist consultation.",
                        "error": "JSONDecodeError",
                    }

            specialization = arguments.get("specialization", "general")
            specific_task = arguments.get("specific_task", "")
            context_for_specialist = arguments.get("context_for_specialist", "")
            problem_constraints = arguments.get("problem_constraints", constraints)
            
            # Build enhanced task prompt for specialist
            professor_reasoning_context = f"""
PROFESSOR'S REASONING CONTEXT:
Original Problem: {original_problem}
Specialist Context: {context_for_specialist}
Task Constraints: {problem_constraints}

The professor has determined that this specific task requires your expertise in {specialization}.
"""
            
            enhanced_prompt = build_enhanced_task_prompt(
                specialization=specialization,
                task=specific_task,
                professor_reasoning_context=professor_reasoning_context
            )
            
            logger.info(f"Consulting {specialization} specialist for task: {specific_task[:100]}...")
            
            # Create specialist and execute task with Self-Evolve
            from app.core.agents.specialist import SpecialistAgent
            from app.core.agents.evaluator import EvaluatorAgent
            from app.core.agents.refiner import RefinerAgent
            from app.core.engine.self_evolve import SelfEvolve, Problem
            
            specialist = SpecialistAgent(
                domain=specialization,
                provider=self.provider,
            )
            
            # Create specialist's own evaluator and refiner for Self-Evolve
            specialist_evaluator = EvaluatorAgent(provider=self.provider)
            specialist_refiner = RefinerAgent(provider=self.provider)
            
            # Create specialist progress callback if provided
            def specialist_progress_callback(current_iter: int, max_iters: int, phase: str):
                if progress_callback:
                    # Calculate actual progress based on specialist iteration
                    specialist_progress = (current_iter - 1) / max_iters if max_iters > 0 else 0.0
                    specialist_phase = f"Specialist ({specialization}): {phase}"
                    progress_callback(specialist_progress, specialist_phase)
            
            # Create Self-Evolve engine for specialist
            from app.settings import settings
            specialist_engine = SelfEvolve(
                generator=specialist,
                evaluator=specialist_evaluator,
                refiner=specialist_refiner,
                max_iters=settings.specialist_max_iters,  # Use configured specialist iterations
                progress_callback=specialist_progress_callback if progress_callback else None,
            )
            
            # Create problem for specialist
            specialist_problem = Problem(
                question=specific_task,
                context=context_for_specialist,
                constraints=problem_constraints,
            )
            
            # Execute specialist Self-Evolve
            specialist_solution = await specialist_engine.solve(specialist_problem)
            
            # Extract detailed information for continuation prompt
            final_answer = specialist_solution.output
            total_iterations = specialist_solution.iterations
            
            # Extract evaluation from evolution history (if available)
            final_evaluation = "Evaluation completed successfully."
            reasoning_section = ""
            if specialist_solution.evolution_history:
                last_iteration = specialist_solution.evolution_history[-1]
                final_evaluation = last_iteration.get("feedback", "No feedback provided.")
                
                # Extract reasoning from the final evaluation metadata
                evaluator_metadata = last_iteration.get("metadata", {}).get("evaluator", {})
                reasoning_section = evaluator_metadata.get("reasoning", "No reasoning provided.")


            # Build a formatted result for the continuation prompt
            formatted_result = build_specialist_consultation_continuation_prompt(
                specialization=specialization,
                task=specific_task,
                final_answer=final_answer,
                total_iterations=total_iterations,
                final_evaluation=final_evaluation,
                reasoning_section=reasoning_section,
            )
            
            # Create result with both formatted and raw data
            return {
                "specialization": specialization,
                "task": specific_task,
                "context": context_for_specialist,
                "constraints": problem_constraints,
                "output": specialist_solution.output,
                "formatted_result": formatted_result,  # For continuation prompts
                "metadata": {
                    "iterations": specialist_solution.iterations,
                    "converged": specialist_solution.metadata.get('converged', False),
                    "total_tokens": specialist_solution.total_tokens,
                    "stop_reason": specialist_solution.metadata.get('stop_reason', 'unknown'),
                }
            }
            
        except Exception as e:
            logger.error(f"Specialist consultation failed: {e}")
            return {
                "specialization": arguments.get("specialization", "unknown"),
                "task": arguments.get("specific_task", ""),
                "output": f"Specialist consultation failed: {str(e)}",
                "error": str(e),
            }
    
    async def _synthesize_specialist_results(
        self,
        original_problem: str,
        specialist_results: List[Dict[str, Any]],
        constraints: str,
    ) -> str:
        """
        Synthesize results from specialist consultations.
        
        Args:
            original_problem: The original problem
            specialist_results: List of specialist results
            constraints: Problem constraints
            
        Returns:
            Synthesized solution
        """
        # Build synthesis prompt
        synthesis_prompt = f"""
Original Problem: {original_problem}

Constraints: {constraints}

Specialist Consultations:
"""
        
        for i, result in enumerate(specialist_results, 1):
            # Use formatted_result if available, otherwise fall back to simple output
            if 'formatted_result' in result:
                synthesis_prompt += f"\n\n--- Consultation {i} ---\n{result['formatted_result']}\n"
            else:
                synthesis_prompt += f"\n\n--- Specialist {i} ({result.get('specialization', 'Unknown')}) ---\n"
                synthesis_prompt += f"Task: {result.get('task', 'N/A')}\n"
                synthesis_prompt += f"Result: {result.get('output', 'No output')}\n"
        
        synthesis_prompt += """

As the supervising Professor, synthesize these specialist results into a comprehensive solution that:
1. Addresses the original problem completely
2. Integrates insights from all specialists
3. Ensures all constraints are satisfied
4. Presents a clear, coherent final answer
5. Highlights key findings and provides proper mathematical reasoning

Provide your final synthesis:
"""
        
        try:
            # Generate synthesis
            synthesis = await self._generate(
                prompt=synthesis_prompt,
                temperature=0.5,  # Moderate temperature for synthesis
            )
            
            return synthesis
            
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            # Fallback: concatenate results using formatted_result if available
            combined_parts = []
            for r in specialist_results:
                if 'formatted_result' in r:
                    combined_parts.append(r['formatted_result'])
                else:
                    combined_parts.append(f"{r.get('specialization', 'Specialist')}: {r.get('output', '')}")
            
            return f"Combined specialist results:\n\n" + "\n\n".join(combined_parts)

    async def synthesize(
        self,
        original_problem: str,
        specialist_results: List[Dict[str, Any]],
        synthesis_plan: Optional[str] = None,
    ) -> AgentResult:
        """
        Synthesize specialist results into final answer.
        
        Args:
            original_problem: The original problem
            specialist_results: Results from specialists
            synthesis_plan: Plan for synthesis
            
        Returns:
            Synthesized result
        """
        logger.info(f"Professor synthesizing {len(specialist_results)} specialist results")
        
        # Build synthesis prompt
        synthesis_prompt = f"""
Original Problem: {original_problem}

Synthesis Plan: {synthesis_plan or "Combine all specialist insights into a comprehensive solution"}

Specialist Results:
"""
        
        for i, result in enumerate(specialist_results, 1):
            # Use formatted_result if available, otherwise fall back to simple output
            if 'formatted_result' in result:
                synthesis_prompt += f"\n\n--- Consultation {i} ---\n{result['formatted_result']}\n"
            else:
                synthesis_prompt += f"\n\n--- Specialist {i} ({result.get('domain', 'Unknown')}) ---\n"
                synthesis_prompt += f"Task: {result.get('task', 'N/A')}\n"
                synthesis_prompt += f"Result: {result.get('output', 'No output')}\n"
        
        synthesis_prompt += """

Please synthesize these specialist results into a comprehensive solution that:
1. Addresses the original problem completely
2. Integrates insights from all specialists
3. Presents a clear, coherent answer
4. Highlights key findings and recommendations
"""
        
        try:
            # Generate synthesis
            synthesis = await self._generate(
                prompt=synthesis_prompt,
                temperature=0.5,  # Moderate temperature for synthesis
            )
            
            # Count tokens for synthesis
            tokens_used = self.provider.count_tokens(synthesis_prompt + synthesis)
            
            return AgentResult(
                output=synthesis,
                metadata={
                    "specialist_count": len(specialist_results),
                    "synthesis_plan": synthesis_plan,
                },
                tokens_used=tokens_used,
            )
            
        except Exception as e:
            logger.error(f"Professor synthesis failed: {e}")
            # Fallback: concatenate results using formatted_result if available
            combined_parts = []
            for r in specialist_results:
                if 'formatted_result' in r:
                    combined_parts.append(r['formatted_result'])
                else:
                    combined_parts.append(f"{r.get('domain', 'Specialist')}: {r.get('output', '')}")
            
            fallback_output = f"Combined specialist results:\n\n" + "\n\n".join(combined_parts)
            
            return AgentResult(
                output=fallback_output,
                metadata={"error": str(e), "fallback": True},
                tokens_used=self.provider.count_tokens(fallback_output),
            )

 