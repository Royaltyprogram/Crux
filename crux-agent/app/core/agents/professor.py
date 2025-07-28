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
        
        # Conversation continuity support (using provider's capabilities)
        self.consultation_history = []  # Track consultation history
        
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
        context_text = additional_context.get("context", "")
        constraints_text = constraints
        
        prompt_parts = [f"Problem: {context.prompt}"]
        
        if context_text:
            prompt_parts.append(f"Context: {context_text}")
        
        if constraints_text:
            prompt_parts.append(f"Constraints: {constraints_text}")
        
        initial_prompt = f"""
{chr(10).join(prompt_parts)}

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
                        # Handle arguments - could be dict or string
                        arguments = func_call.arguments
                        if isinstance(arguments, str):
                            try:
                                import json
                                arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse function arguments: {arguments}")
                                continue
                        
                        logger.info(f"Specialist consultation {i}: {arguments.get('specialization', 'unknown')}")
                        specialist_result = await self._execute_specialist_consultation(
                            arguments,
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
                response = await self.provider.complete_with_functions(
                    prompt=prompt,
                    functions=functions,
                    system_prompt=self.system_prompt,
                    temperature=temperature if temperature is not None else self.temperature,
                )
                
                # Provider automatically tracks response ID internally
                return response
            elif functions:
                # Try passing functions to regular complete method
                logger.info("Provider doesn't have complete_with_functions, trying complete with functions parameter")
                response = await self.provider.complete(
                    prompt=prompt,
                    functions=functions,
                    system_prompt=self.system_prompt,
                    temperature=temperature if temperature is not None else self.temperature,
                )
                return response
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
            
            # Build enhanced task prompt for specialist (self-evolve pattern)
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
            
            # Create enhanced problem with comprehensive context (self-evolve pattern)
            # Build enhanced task following self-evolve's enhanced_task pattern
            enhanced_task_content = f"""**PROFESSOR'S MEMORANDUM**

**TO**: Graduate Student Specialist, {specialization}
**FROM**: Supervising Professor
**SUBJECT**: Critical Task Assignment

You have been selected for this assignment due to your advanced expertise in {specialization}. This task is a pivotal component of a larger research initiative, and its successful completion requires the highest level of mathematical rigor.

**YOUR ASSIGNED TASK:**
{specific_task}

**EXPECTATIONS:**
I expect a solution that is analytically sound, rigorously derived, and demonstrates a deep command of the theoretical frameworks within your field. Your primary approach must be through mathematical proof and derivation.

Use computational tools exclusively for verifying your analytical results. Do not substitute computation for reasoning.

Present your solution as a formal mathematical argument, concluding with the final answer in <answer> tags for integration into the main research.

I am counting on your specialized skills to handle this with the precision and depth required. Do not fail to provide a well-reasoned attempt.
{professor_reasoning_context}"""

            specialist_problem = Problem(
                question=enhanced_task_content,  # Use enhanced task instead of simple task
                context=context_for_specialist,
                constraints=problem_constraints,
                metadata={
                    # Enhanced metadata following self-evolve pattern
                    "specialization": specialization,
                    "professor_reasoning_context": professor_reasoning_context,
                    "original_problem": original_problem,
                    "from_professor": True,
                    "enhanced_context_used": True,
                }
            )
            
            # Execute specialist Self-Evolve with enhanced problem
            specialist_solution = await specialist_engine.solve(specialist_problem)
            
            # Extract detailed information for continuation prompt (self-evolve pattern)
            final_answer = specialist_solution.output
            total_iterations = specialist_solution.iterations
            
            # DEBUG: Print specialist solution structure
            logger.info("=" * 60)
            logger.info("SPECIALIST SOLUTION DEBUG INFO")
            logger.info("=" * 60)
            logger.info(f"Final Answer: {final_answer[:200]}...")
            logger.info(f"Total Iterations: {total_iterations}")
            logger.info(f"Evolution History Length: {len(specialist_solution.evolution_history) if specialist_solution.evolution_history else 0}")
            
            if specialist_solution.evolution_history:
                for i, iter_data in enumerate(specialist_solution.evolution_history, 1):
                    logger.info(f"--- Iteration {i} Structure ---")
                    logger.info(f"  Keys: {list(iter_data.keys())}")
                    if 'output' in iter_data:
                        logger.info(f"  Output: {iter_data['output'][:100]}...")
                    if 'feedback' in iter_data:
                        logger.info(f"  Feedback: {iter_data['feedback'][:100]}...")
                    if 'metadata' in iter_data:
                        logger.info(f"  Metadata Keys: {list(iter_data['metadata'].keys())}")
            logger.info("=" * 60)
            
            # Enhanced evaluation extraction with comprehensive reasoning (self-evolve pattern)
            final_evaluation = "Evaluation completed successfully."
            reasoning_section = ""
            
            if specialist_solution.evolution_history:
                # Extract final evaluation from last iteration
                last_iteration = specialist_solution.evolution_history[-1]
                final_evaluation = last_iteration.get("feedback", "No feedback provided.")
                
                # Extract reasoning summaries from ALL iterations + final answer (optimized for context)
                reasoning_section = ""
                if specialist_solution.evolution_history:
                    reasoning_section += "\n\n**COMPLETE REASONING PROCESS FROM SPECIALIST**:\n"
                    
                    # Process all iterations but only include full answer for the final one
                    for i, iteration in enumerate(specialist_solution.evolution_history, 1):
                        is_final_iteration = (i == len(specialist_solution.evolution_history))
                        
                        reasoning_section += f"\n--- Iteration {i} Reasoning ---\n"
                        
                        # Include full specialist answer ONLY for final iteration
                        if is_final_iteration and iteration.get('output'):
                            reasoning_section += f"**Final Specialist Answer:**\n{iteration['output']}\n\n"
                        
                        # Extract metadata from each iteration
                        iteration_metadata = iteration.get("metadata", {})
                        generator_metadata = iteration_metadata.get("generator", {})
                        evaluator_metadata = iteration_metadata.get("evaluator", {})
                        refiner_metadata = iteration_metadata.get("refiner", {})
                        
                        # Generator reasoning (all iterations)
                        if generator_metadata.get('reasoning_summary'):
                            reasoning_section += f"Generator Reasoning:\n{generator_metadata['reasoning_summary']}\n\n"
                        
                        # Evaluator reasoning (all iterations)  
                        if evaluator_metadata.get('reasoning_summary'):
                            reasoning_section += f"Evaluator Reasoning:\n{evaluator_metadata['reasoning_summary']}\n\n"
                        
                        # Include evaluator feedback (all iterations)
                        if iteration.get('feedback'):
                            reasoning_section += f"Evaluator Feedback:\n{iteration['feedback']}\n\n"
                        
                        # Prompt refiner reasoning (all iterations)
                        if refiner_metadata.get('reasoning_summary'):
                            reasoning_section += f"Prompt Refiner Reasoning:\n{refiner_metadata['reasoning_summary']}\n\n"


            # Build a formatted result for the continuation prompt
            formatted_result = build_specialist_consultation_continuation_prompt(
                specialization=specialization,
                task=specific_task,
                final_answer=final_answer,
                total_iterations=total_iterations,
                final_evaluation=final_evaluation,
                reasoning_section=reasoning_section,
            )
            
            # Extract final answer value (like self-evolve's final_answer_value)
            import re
            final_answer_value = final_answer
            answer_match = re.search(r'<answer>(.*?)</answer>', final_answer, re.DOTALL | re.IGNORECASE)
            if answer_match:
                final_answer_value = answer_match.group(1).strip()

            # Create result with enhanced metadata (exactly like self-evolve pattern)
            result = {
                "specialization": specialization,
                "task": specific_task,
                "context": context_for_specialist,
                "constraints": problem_constraints,
                "output": specialist_solution.output,
                "final_answer": final_answer,  # Complete final answer
                "final_answer_value": final_answer_value,  # Extracted answer value
                "final_evaluation": final_evaluation,  # Complete evaluation from verifier
                "total_iterations": total_iterations,  # Number of iterations
                "formatted_result": formatted_result,  # For continuation prompts
                "professor_reasoning_context": professor_reasoning_context,  # Enhanced context preservation
                "reasoning_section": reasoning_section,  # Complete reasoning process from ALL iterations
                "session_details": {  # Complete session details like self-evolve
                    "iterations": [
                        {
                            "iteration": i + 1,
                            "reasoning_summary": iter_data.get("metadata", {}).get("generator", {}).get("reasoning_summary", ""),
                            "evaluator_reasoning_summary": iter_data.get("metadata", {}).get("evaluator", {}).get("reasoning_summary", ""),
                            "refiner_reasoning_summary": iter_data.get("metadata", {}).get("refiner", {}).get("reasoning_summary", ""),
                            # Include full answer only for final iteration, preview for others
                            "answer": iter_data.get("output", "") if (i + 1) == len(specialist_solution.evolution_history) else (iter_data.get("output", "")[:100] + "..." if iter_data.get("output", "") else ""),
                            "evaluation_feedback": iter_data.get("feedback", ""),
                            "timestamp": iter_data.get("timestamp", "")
                        }
                        for i, iter_data in enumerate(specialist_solution.evolution_history)
                    ]
                },
                "metadata": {
                    "iterations": specialist_solution.iterations,
                    "converged": specialist_solution.metadata.get('converged', False),
                    "total_tokens": specialist_solution.total_tokens,
                    "stop_reason": specialist_solution.metadata.get('stop_reason', 'unknown'),
                    "enhanced_context_used": True,  # Flag for enhanced context usage
                    "evolution_history_available": bool(specialist_solution.evolution_history),
                    "complete_reasoning_provided": bool(reasoning_section),  # Flag for complete reasoning
                }
            }
            
            # Save consultation history for conversation continuity (like self-evolve)
            self.consultation_history.append(result)
            logger.info(f"Consultation result saved to history. Total consultations: {len(self.consultation_history)}")
            
            return result
            
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

    async def continue_conversation(self, follow_up: str, **kwargs) -> AgentResult:
        """Continue an existing conversation using provider's capabilities.
        
        Leverages the provider's built-in conversation continuation functionality
        which handles Response API continuation for o-series models automatically.
        
        Args:
            follow_up: Follow-up prompt/question
            **kwargs: Additional arguments
            
        Returns:
            AgentResult with continued conversation
        """
        # Check if provider supports conversation continuation
        if not hasattr(self.provider, 'continue_conversation'):
            logger.warning("Provider doesn't support conversation continuation, falling back to new conversation")
            from app.core.agents.base import AgentContext
            return await self.run(AgentContext(prompt=follow_up, additional_context=kwargs))

        logger.info("Continuing conversation using provider's continuation capability")
        
        # Create follow-up prompt that mentions specialist tools
        follow_up_prompt = f"""
{follow_up}

You are continuing the previous conversation. You still have access to all specialist consultation tools if needed.
Use your previous analysis and specialist consultations to provide a comprehensive follow-up response.
"""
        
        try:
            # Use provider's conversation continuation
            response = await self.provider.continue_conversation(
                follow_up=follow_up_prompt,
                temperature=self.temperature,
            )
            
            # Count tokens for follow-up
            tokens_used = self.provider.count_tokens(follow_up_prompt)
            if isinstance(response, str):
                tokens_used += self.provider.count_tokens(response)
            elif hasattr(response, 'content'):
                tokens_used += self.provider.count_tokens(response.content)
            
            # Extract content from response
            content = response if isinstance(response, str) else (
                response.content if hasattr(response, 'content') else str(response)
            )
            
            logger.info(f"Conversation continuation completed, tokens: {tokens_used}")
            
            return AgentResult(
                output=content,
                metadata={
                    "conversation_continued": True,
                    "provider_continuation": True,
                    "approach": "provider_continuation",
                },
                tokens_used=tokens_used,
            )
            
        except Exception as e:
            logger.error(f"Provider conversation continuation failed: {e}")
            # Fallback to new conversation
            logger.info("Falling back to new conversation")
            from app.core.agents.base import AgentContext
            return await self.run(AgentContext(prompt=follow_up, additional_context=kwargs))
    
    def get_consultation_summary(self) -> Dict[str, Any]:
        """Return a lightweight structured summary of all specialist consultations (like self-evolve).
        
        This helper is primarily used by example scripts to display a quick
        overview of what happened during the Professor workflow without dumping
        the entire consultation history.
        """
        return {
            "total_consultations": len(self.consultation_history),
            "current_response_id": getattr(self.provider, 'current_response_id', None),
            "consultations": [
                {
                    "specialization": item.get("specialization", "unknown"),
                    "task": item.get("task", "")[:200],  # Limit length
                    "iterations": item.get("metadata", {}).get("iterations", 0),
                    "converged": item.get("metadata", {}).get("converged", False),
                }
                for item in self.consultation_history
            ]
        }

 