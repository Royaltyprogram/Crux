"""
Professor Model with Chain-of-Thought reasoning and Graduate Worker consultation
Updated to use OpenAI Responses API with proper tool use
"""

import json
from typing import Dict, Any, List, Optional
from .base_model import BaseModel
from app.core.providers.factory import create_provider
from .self_evolve_mixin import SelfEvolveMixin
from ..config import FrameworkConfig
from ..utils.logger import get_logger


class ProfessorModel(SelfEvolveMixin, BaseModel):
    """Professor model with CoT reasoning and dynamic graduate worker consultation using Responses API"""
    
    def __init__(self, config: FrameworkConfig):
        """Initialize Professor with configuration"""
        # Use the generator config for the Professor model
        super().__init__(config.generator_config)
        self.framework_config = config  # Store full framework config
        self.graduate_workers = []
        self.consultation_history = []
        self.current_response_id = None
        self.logger = get_logger(self.__class__.__name__)
        
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response with CoT reasoning and specialist consultations using Responses API"""
        
        instructions = """You are a Chief Research Scientist with UNLIMITED TIME and computational resources, responsible for producing the highest quality, most rigorous solution to complex problems. You will lead a team of elite specialists using the `consult_graduate_specialist` tool to thoroughly investigate and solve problems with complete mathematical rigor.

**FUNDAMENTAL PRINCIPLE: QUALITY OVER EVERYTHING**
- There is NO time pressure whatsoever. Take as long as needed.
- Mathematical rigor and logical completeness are your ONLY priorities.
- Speed is irrelevant. Perfection is mandatory.
- If you feel any urge to "finish quickly," STOP and reconsider your approach.

**YOUR STRATEGIC WORKFLOW:**

1.  **Deep Problem Analysis & Research Topic Formulation**:
    -   Conduct thorough analysis to identify ALL mathematical components and potential difficulties.
    -   Think comprehensively about solution paths and identify ALL necessary sub-problems.
    -   Decompose into self-contained **research topics** that can be solved independently.
    -   Take time to ensure your decomposition is complete and well-founded.
    -   **Quality over delegation**: If needed, ask specialists to solve substantial portions or even the whole problem.

2.  **PRINCIPLE OF OPEN-ENDED INQUIRY: Frame tasks as questions, not assertions.**
    -   **WRONG:** `"Prove that the only solutions are f(x)=x and f(x)=-x."`
    -   **RIGHT:** `"Classify all functions f(x) that satisfy the given conditions."`
    -   **WRONG:** `"Prove that the value is 5."`
    -   **RIGHT:** `"Determine the value of c, and prove that this value is minimal."`
    -   Frame `specific_task` as investigations or classifications to prevent confirmation bias.

3.  **MANDATORY VERIFICATION PROTOCOL**:
    -   **Never trust ANY result without verification.** Every significant claim must be rigorously verified.
    -   **Multi-layer verification**: For critical results, assign multiple specialists to verify independently.
    -   **Adversarial testing**: Always assign specialists to actively seek counterexamples and flaws.
    -   **Edge case analysis**: Test all boundary conditions and degenerate cases.
    -   **Cross-validation**: Use different approaches to verify the same result.

4.  **Exhaustive Delegation Strategy**:
    -   **No shortcuts allowed**: Every task must include rigorous verification requirements.
    -   **Redundant verification**: For crucial steps, assign multiple specialists with different approaches.
    -   **Devil's advocate mandatory**: Always assign someone to "Find flaws in this argument" or "Construct counterexamples."
    -   **Iterative refinement**: If a result is incomplete or questionable, continue refining until perfect.

5.  **Anti-Rush & Anti-Overgeneralization Safeguards**:
    -   **Slow down deliberately**: If you notice pattern matching or quick conclusions, STOP and verify thoroughly.
    -   **Question everything**: Before accepting any hypothesis, assign specialists to test its limits and validity.
    -   **Demand complete proofs**: Never accept sketches, hand-waving, or "by similar reasoning" arguments.
    -   **Multiple perspectives**: Approach each problem from several different angles.

6.  **Rigorous Synthesis & Unlimited Iteration**:
    -   **Perfectionist standards**: Every logical step must be airtight before proceeding.
    -   **Continuous verification**: If ANY doubt exists, assign more specialists to investigate.
    -   **No time limits**: Continue iterating until you achieve complete mathematical rigor.
    -   **Red flag protocol**: Any incomplete or questionable result triggers additional investigation.

7.  **Failure Recovery & Deep Investigation**:
    -   **Failure is valuable information**: Use failures to understand problem complexity better.
    -   **Unlimited decomposition**: Break failed tasks into as many sub-problems as needed.
    -   **Multiple approaches**: Try different mathematical frameworks, specialists, and methodologies.
    -   **Persistent investigation**: Continue until you find a working approach.

8.  **Quality-Assured Final Answer**:
    -   **Go Beyond Correctness**: Do not settle for a merely correct answer. The final solution must provide deep insights, reveal novel connections between concepts, or offer a more elegant and powerful perspective on the problem. The goal is a landmark intellectual contribution, not a textbook exercise.
    -   **Insight Through Rigor**: Originality must be a product of deep, verifiable reasoning. Any novel claim or perspective must be supported by an even higher standard of proof than standard results. Never sacrifice correctness for the appearance of novelty.
    -   **Only provide answers that meet publication standards** for top mathematical journals.
    -   **Self-verification**: Before finalizing, ask yourself: "Would I stake my reputation on this solution?"
    -   **Final format**: Provide your answer in the requested format, but ONLY after achieving complete confidence.
    -   **No compromises**: If the solution isn't perfect, continue working. Quality is non-negotiable.
    -   **Multiple validation**: Ensure your final answer has been verified through multiple independent approaches.

**ANTI-PRESSURE PROTOCOLS:**
- Ignore any perceived time constraints - they don't exist.
- Multiple consultations are encouraged, not discouraged.
- Iteration until perfection is expected, not optional.
- Incomplete solutions are unacceptable regardless of effort expended.
- When in doubt, consult more specialists and verify more thoroughly.
"""

        self.logger.info(f"Professor starting to work on problem: {prompt[:100]}...")
        
                # Define the graduate specialist consultation tool (dict)
        specialist_tool = {
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
        
        # Use Responses API with tools (wrap dict in list)
        return self._generate_with_responses_api(instructions, prompt, [specialist_tool], **kwargs)
    
    def _generate_with_responses_api(self, instructions: Optional[str], user_input: str, tools: List[Dict], **kwargs) -> str:
        """Generate using Responses API with function calling loop, supporting conversation continuation."""
        from openai import OpenAI
        
        # Setup OpenAI client using the correct config
        client = OpenAI(api_key=self.config.api_key, timeout=self.config.timeout)
        
        # Enable code interpreter for Professor's reasoning.
        # This is disabled by default for the Professor, as its role is to delegate, not execute.
        # This kwarg is for internal logic; pop it so it's not passed to the API.
        use_code_interpreter = kwargs.pop('enable_code_interpreter', getattr(self.config, 'enable_code_interpreter', False))
        
        all_tools = tools.copy()
        if use_code_interpreter:
            all_tools.append({
                "type": "code_interpreter",
                "container": {
                    "type": "auto",
                    "file_ids": []
                }
            })
        
        previous_response_id = kwargs.get("previous_response_id")

        if previous_response_id:
            # Continuing a conversation
            params = {
                "model": self.config.model_name,
                "input": user_input,
                "previous_response_id": previous_response_id,
                "tools": all_tools,
            }
            self.logger.info(f"Continuing conversation with previous_response_id: {previous_response_id}")
        else:
            # Starting a new conversation
            params = {
                "model": self.config.model_name,
                "instructions": instructions,
                "input": user_input,
                "tools": all_tools,
                "tool_choice": "auto",
            }

        # Pass through any other kwargs
        for key, value in kwargs.items():
            if key not in params and key != "previous_response_id":
                params[key] = value

        # Debug: 로그에 툴 목록 출력 (function 툴 포함 여부 확인)
        try:
            import json as _json
            self.logger.info(f"TOOLS_DEBUG: Registered tools for API call: {_json.dumps(params['tools'], ensure_ascii=False)}")
        except Exception:
            pass
        
        # Debug: 전체 API 호출 파라미터 출력
        try:
            import json as _json
            debug_params = params.copy()
            # 너무 긴 input은 줄여서 로그
            if 'input' in debug_params and len(str(debug_params['input'])) > 500:
                debug_params['input'] = str(debug_params['input'])[:500] + "..."
            if 'instructions' in debug_params and len(str(debug_params['instructions'])) > 500:
                debug_params['instructions'] = str(debug_params['instructions'])[:500] + "..."
            self.logger.info(f"API_CALL_PARAMS: {_json.dumps(debug_params, ensure_ascii=False, indent=2)}")
        except Exception as e:
            self.logger.error(f"Failed to log API params: {e}")
        
        # Detect model type for proper parameter handling
        model_name_lower = str(self.config.model_name).lower()
        is_reasoning_model = not model_name_lower.startswith("gpt")
        
        # Add reasoning parameters for reasoning models (o3, etc.)
        if is_reasoning_model:
            reasoning_dict = {}
            if hasattr(self.config, 'reasoning_effort') and self.config.reasoning_effort:
                reasoning_dict["effort"] = self.config.reasoning_effort
            if hasattr(self.config, 'reasoning_summary') and self.config.reasoning_summary:
                reasoning_dict["summary"] = self.config.reasoning_summary
            if reasoning_dict:
                params["reasoning"] = reasoning_dict
                self.logger.info(f"Added reasoning parameters: {reasoning_dict}")
        
        # Add parameters based on model type
        if is_reasoning_model:
            # Reasoning models (o3) don't support temperature, only specific parameters
            self.logger.info(f"Using reasoning model {self.config.model_name} - skipping temperature parameter")
            
            # Only add supported parameters for reasoning models
            if hasattr(self.config, 'truncation') and self.config.truncation:
                params["truncation"] = self.config.truncation
                self.logger.info(f"Added truncation for reasoning model: {self.config.truncation}")
        else:
            # GPT models support temperature and other standard parameters
            if hasattr(self.config, 'temperature') and self.config.temperature is not None:
                params["temperature"] = self.config.temperature
                self.logger.info(f"Added temperature for GPT model: {self.config.temperature}")
            if hasattr(self.config, 'truncation') and self.config.truncation:
                params["truncation"] = self.config.truncation
                self.logger.info(f"Added truncation for GPT model: {self.config.truncation}")
            
        # Final debug log before API call
        try:
            import json as _json
            final_params = params.copy()
            # 너무 긴 필드는 줄여서 로그
            if 'input' in final_params and len(str(final_params['input'])) > 200:
                final_params['input'] = str(final_params['input'])[:200] + "..."
            if 'instructions' in final_params and len(str(final_params['instructions'])) > 200:
                final_params['instructions'] = str(final_params['instructions'])[:200] + "..."
            self.logger.info(f"FINAL_API_PARAMS: {_json.dumps(final_params, ensure_ascii=False, indent=2)}")
        except Exception as e:
            self.logger.error(f"Failed to log final API params: {e}")
            
        self.logger.info("Professor making initial Responses API call with tools")
        
        try:
            # Function calling loop for reasoning models
            self.logger.info(f"Calling client.responses.create with model: {params['model']}")
            max_iterations = 30  # Maximum number of function call iterations to prevent infinite loops
            iteration_count = 0
            
            while True:
                iteration_count += 1
                if iteration_count > max_iterations:
                    self.logger.warning(f"Reached maximum function call iterations ({max_iterations}). Stopping to prevent infinite loop.")
                    # Try to get any response text available
                    final_text = ""
                    if 'response' in locals():
                        for item in response.output:
                            if hasattr(item, 'type') and item.type == 'message':
                                for content in item.content:
                                    if hasattr(content, 'type') and content.type == 'output_text':
                                        final_text += content.text
                    return final_text or "Error: Maximum function call iterations reached."
                
                # stream 기본값을 True 로 설정하여 별도 지정이 없더라도 스트리밍으로 동작
                stream_requested = kwargs.get("stream", getattr(self.config, "stream", True))
                if stream_requested:
                    params["stream"] = True
                else:
                    params["stream"] = False

                self.logger.info(
                    f"Calling responses API with model {self.config.model_name}, reasoning_effort={getattr(self.config, 'reasoning_effort', 'default')}, stream={params['stream']}"
                )

                # === 스트리밍 및 비-스트리밍 호출을 분기 ===
                if params["stream"]:
                    # For ProfessorModel with function calling, we need to disable streaming
                    # because function calling loop requires access to response.id
                    self.logger.info("Professor detected function calling - switching to non-streaming for compatibility")
                    params["stream"] = False

                # Make API call (now always non-streaming for Professor)
                self.logger.info(f"Making API call (iteration {iteration_count})...")
                response = client.responses.create(**params)
                self.logger.info(f"API call successful, response ID: {response.id}")
                self.current_response_id = response.id
                
                # Check for function calls in the response
                function_calls = [item for item in response.output if hasattr(item, 'type') and item.type == 'function_call']
                self.logger.info(f"Found {len(function_calls)} function calls in response")
                
                # Debug: response 구조 출력
                try:
                    self.logger.info(f"Response output types: {[getattr(item, 'type', 'unknown') for item in response.output]}")
                except Exception as e:
                    self.logger.error(f"Failed to log response types: {e}")
                
                if function_calls:
                    # Execute function calls
                    self.logger.info(f"Professor received {len(function_calls)} function call(s). Waiting for completion...")
                    for i, call in enumerate(function_calls):
                        self.logger.info(f"Executing function call {i+1}/{len(function_calls)}: name={getattr(call, 'name', 'unknown')}")
                    
                    function_outputs = self._execute_function_calls(function_calls)
                    self.logger.info("Function calls completed. Resuming conversation with the results.")
                    
                    # Continue conversation with function results
                    params = {
                        "model": self.config.model_name,
                        "input": function_outputs,
                        "previous_response_id": response.id,
                        "tools": all_tools,
                    }
                    
                    # Re-add parameters based on model type
                    if is_reasoning_model:
                        # Re-add reasoning parameters for reasoning models
                        reasoning_dict = {}
                        if hasattr(self.config, 'reasoning_effort') and self.config.reasoning_effort:
                            reasoning_dict["effort"] = self.config.reasoning_effort
                        if hasattr(self.config, 'reasoning_summary') and self.config.reasoning_summary:
                            reasoning_dict["summary"] = self.config.reasoning_summary
                        if reasoning_dict:
                            params["reasoning"] = reasoning_dict
                        
                        # Only add supported parameters for reasoning models
                        if hasattr(self.config, 'truncation') and self.config.truncation:
                            params["truncation"] = self.config.truncation
                    else:
                        # Re-add standard parameters for GPT models
                        if hasattr(self.config, 'temperature') and self.config.temperature is not None:
                            params["temperature"] = self.config.temperature
                        if hasattr(self.config, 'truncation') and self.config.truncation:
                            params["truncation"] = self.config.truncation
                            
                    continue  # Continue the loop
                else:
                    # No function calls, get the final response
                    final_text = ""
                    for item in response.output:
                        if hasattr(item, 'type') and item.type == 'message':
                            for content in item.content:
                                if hasattr(content, 'type') and content.type == 'output_text':
                                    final_text += content.text
                    
                    if not final_text:
                        # Fallback: get output_text attribute
                        final_text = getattr(response, 'output_text', str(response.output))
                    
                    # Extract reasoning summary from response (detailed)
                    reasoning_summary = ""
                    try:
                        # Try to extract from response.output first
                        for item in getattr(response, "output", []):
                            if getattr(item, 'type', '') == 'reasoning':
                                summaries = getattr(item, 'summary', [])
                                if summaries:
                                    if isinstance(summaries, list):
                                        reasoning_summary = " ".join([
                                            getattr(seg, 'text', str(seg)) for seg in summaries
                                        ])
                                    else:
                                        reasoning_summary = str(summaries)
                                    break
                        
                        # Fallback to top-level reasoning field if still empty (new API schema)
                        if not reasoning_summary and hasattr(response, 'reasoning'):
                            reasoning_obj = getattr(response, 'reasoning', None)
                            if reasoning_obj is not None:
                                summary_field = getattr(reasoning_obj, 'summary', None)
                                if summary_field:
                                    if isinstance(summary_field, list):
                                        reasoning_summary = " ".join([
                                            getattr(seg, 'text', str(seg)) for seg in summary_field
                                        ])
                                    else:
                                        reasoning_summary = str(summary_field)
                    except Exception as e:
                        self.logger.debug(f"Failed to extract reasoning summary: {e}")

                    # Save for external access
                    self.last_reasoning_summary = reasoning_summary.strip()
                    
                    # Log reasoning summary if available  
                    if self.last_reasoning_summary:
                        self.logger.info("PROFESSOR_REASONING_START")
                        self.logger.info(self.last_reasoning_summary)
                        self.logger.info("PROFESSOR_REASONING_END")

                    self.logger.info(f"Professor completed reasoning after {iteration_count} iterations")
                    self._log_interaction(user_input, final_text)
                    return final_text
                    
        except Exception as e:
            self.logger.error(f"Error in Responses API call: {e}")

            # If the error occurred during a conversation continuation, it's safer to stop.
            if previous_response_id:
                self.logger.error("Failed to continue conversation. Returning an error message.")
                return f"Error continuing conversation: {str(e)}"

            # Fallback to base model for initial calls, ensuring the full tool list is passed along.
            self.logger.info("Attempting fallback to standard API call...")
            fallback_kwargs = kwargs.copy()
            fallback_kwargs['tools'] = all_tools
            fallback_kwargs['tool_choice'] = params.get('tool_choice', 'auto')
            
            messages = []
            if instructions:
                messages.append({"role": "system", "content": instructions})
            messages.append({"role": "user", "content": user_input})

            return super()._make_api_call(messages, **fallback_kwargs)
    
    def _execute_function_calls(self, function_calls: List) -> List[Dict[str, Any]]:
        """Execute function calls and return outputs for Responses API"""
        function_outputs = []
        
        for call in function_calls:
            if call.name == "consult_graduate_specialist":
                try:
                    # Parse arguments
                    arguments = json.loads(call.arguments) if isinstance(call.arguments, str) else call.arguments
                    
                    # Execute consultation
                    specialist_result = self._execute_graduate_consultation(arguments)
                    
                    # Format for Responses API
                    function_outputs.append({
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": specialist_result
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error executing graduate consultation: {e}")
                    function_outputs.append({
                        "type": "function_call_output", 
                        "call_id": call.call_id,
                        "output": f"Error: {str(e)}"
                    })
            else:
                self.logger.warning(f"Unknown function call: {call.name}")
                function_outputs.append({
                    "type": "function_call_output",
                    "call_id": call.call_id, 
                    "output": f"Unknown function: {call.name}"
                })
        
        return function_outputs
    
    def _execute_graduate_consultation(self, arguments: dict) -> str:
        """Execute graduate specialist consultation"""
        from .graduate_worker import GraduateWorker
        
        specialization = arguments["specialization"]
        task = arguments["specific_task"]
        context = arguments.get("context_for_specialist", "")
        constraints = arguments.get("problem_constraints", "")
        
        # Create new graduate worker using framework config
        # Create or reuse a provider instance that aligns with current settings
        provider = create_provider(model=self.framework_config.worker_config.model_name,
                                   api_key=self.framework_config.worker_config.api_key)

        worker = GraduateWorker(self.framework_config, f"worker_{len(self.graduate_workers)}", provider=provider)
        self.graduate_workers.append(worker)
        
        # Build full task with context (constraints passed separately)
        full_task = task
        if context:
            full_task += f"\n\n**Context**: {context}"
        
        self.logger.info(f"Professor consulting {specialization} for task: {task[:100]}...")
        if constraints:
            self.logger.info(f"With constraints: {constraints[:100]}...")
        
        # Graduate solves task using self-evolve mechanism with constraints
        result = worker.solve_specialized_task(specialization, full_task, constraints=constraints)
        
        # Format result for Professor, including the FULL, DETAILED evaluation AND reasoning summaries
        final_answer = result.get('final_answer_value', 'N/A')
        final_evaluation = result.get('final_evaluation', 'No evaluation provided.')
        
        # Extract reasoning summaries from all iterations
        session_details = result.get('session_details', {})
        iterations = session_details.get('iterations', [])
        
        reasoning_section = ""
        if iterations:
            reasoning_section += "\n\n**COMPLETE REASONING PROCESS FROM SPECIALIST**:\n"
            for i, iteration in enumerate(iterations, 1):
                reasoning_section += f"\n--- Iteration {i} Reasoning ---\n"
                
                # Generator reasoning
                if iteration.get('reasoning_summary'):
                    reasoning_section += f"Generator Reasoning:\n{iteration['reasoning_summary']}\n"
                
                # Evaluator reasoning  
                if iteration.get('evaluator_reasoning_summary'):
                    reasoning_section += f"Evaluator Reasoning:\n{iteration['evaluator_reasoning_summary']}\n"
                
                # Prompt refiner reasoning
                if iteration.get('refiner_reasoning_summary'):
                    reasoning_section += f"Prompt Refiner Reasoning:\n{iteration['refiner_reasoning_summary']}\n"

        # The detailed evaluation from the Evaluator is CRITICAL for the Professor to make informed decisions.
        # The previous implementation summarized this too much.
        formatted_result = f"""**Specialist Consultation Result**

**Specialization**: {specialization}
**Task**: {task}

**Final Answer from Specialist**:
```
{final_answer}
```

**CRITICAL: Full Evaluation from Verifier**:
```
{final_evaluation}
```
{reasoning_section}

**Summary**: The specialist completed the task in {result['total_iterations']} iterations. You MUST critically analyze the verifier's full evaluation above AND the complete reasoning process before proceeding.
"""

        # Add the formatted result to the history item for logging purposes
        result['formatted_result_for_professor'] = formatted_result

        # Save consultation history
        self.consultation_history.append(result)
        
        self.logger.info(f"Graduate specialist completed task with {result['total_iterations']} iterations")
        
        return formatted_result

    def get_consultation_summary(self) -> Dict[str, Any]:
        """Return a lightweight structured summary of all specialist consultations.

        This helper is primarily used by example scripts to display a quick
        overview of what happened during the Professor → Graduate workflow
        without dumping the *entire* consultation history (which can be very
        large).  The method intentionally keeps the returned dict minimal so
        that callers can choose when to access the full `consultation_history`
        list for in-depth information.
        """
        summary: Dict[str, Any] = {
            "total_consultations": len(self.consultation_history),
            "workers_created": len(self.graduate_workers),
            "current_response_id": self.current_response_id,
            "consultations": []
        }

        # Build a tiny per-consultation snapshot so downstream code can render
        # a readable table / list.
        for item in self.consultation_history:
            summary["consultations"].append({
                "specialization": item.get("specialization", "unknown"),
                "worker_id": item.get("worker_id", "unknown"),
                "iterations": item.get("total_iterations", 0),
                "final_answer": item.get("final_answer", "N/A"),
                "task": item.get("task", "")[:500],  # guard against huge blobs
                "full_response": item.get("formatted_result_for_professor", "")
            })

        return summary

    def continue_conversation(self, follow_up: str, **kwargs) -> str:
        """Continue an *existing* conversation with the OpenAI Responses API.

        The Professor occasionally needs to ask follow-up questions after the
        initial call – e.g. to request a summary.  We leverage the
        `previous_response_id` that we stored during the last API round-trip
        (`self.current_response_id`).  If that ID is missing we gracefully
        fall back to starting a brand-new conversation via `generate`.
        """
        if not self.current_response_id:
            # No prior conversation context – just start a fresh one.
            self.logger.warning("No existing response_id – falling back to a new conversation.")
            return self.generate(follow_up, **kwargs)

        # Re-declare the specialist tool so that the Professor can still call
        # `consult_graduate_specialist` during the follow-up turn.
        specialist_tool = {
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

        # Delegate to the internal helper that is aware of the Responses API.
        return self._generate_with_responses_api(
            instructions=None,  # instructions are only needed for the very first turn
            user_input=follow_up,
            tools=[specialist_tool],
            previous_response_id=self.current_response_id,
            **kwargs,
        )
