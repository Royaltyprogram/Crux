"""
Professor agent for orchestrating specialists.
"""
import json
import ast
import re
from typing import Any, Dict, List, Optional, Callable

from app.core.agents.base import AbstractAgent, AgentContext, AgentResult
from app.core.agents.prompts.graduate_worker_prompt import build_enhanced_task_prompt, build_specialist_consultation_continuation_prompt
from app.core.agents.prompts.professor_prompt import get_professor_quality_first_prompt
from app.core.providers.base import BaseProvider
from app.settings import settings
from app.utils.logging import get_logger
from app.core.providers.base import get_current_job_id
import re
import hashlib

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
        
        # Initialize reasoning token tracking
        self.last_reasoning_tokens = 0
        
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
    
    def _normalize_output(self, text: str) -> str:
        """Normalize model output for readability.
        - Convert CRLF to LF
        - Collapse 3+ consecutive newlines to 2
        - Trim leading/trailing whitespace
        """
        if not isinstance(text, str):
            return text
        try:
            original = text
            # Normalize line endings
            s = original.replace('\r\n', '\n').replace('\r', '\n')
            # Count collapsible runs before collapsing
            runs_3plus = len(re.findall(r'\n{3,}', s))
            # Collapse and trim
            s = re.sub(r'\n{3,}', '\n\n', s)
            s = s.strip()
            # Log only when content changed
            if s != original:
                try:
                    logger.debug(
                        f"Professor normalization changed output: len {len(original)} -> {len(s)}; collapsed_runs(>=3): {runs_3plus}"
                    )
                except Exception:
                    pass
            return s
        except Exception:
            return text

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
            
            # Extract reasoning tokens if available
            reasoning_tokens = 0
            reasoning_summary = None
            if hasattr(self.provider, 'last_reasoning_tokens'):
                reasoning_tokens = getattr(self.provider, 'last_reasoning_tokens', 0)
                self.last_reasoning_tokens = reasoning_tokens
            if hasattr(self.provider, 'last_reasoning_summary'):
                reasoning_summary = getattr(self.provider, 'last_reasoning_summary', None)
            # Surface reasoning tokens to progress stream as soon as we have them
            if progress_callback and reasoning_tokens:
                try:
                    progress_callback(0.5, "Professor analysis: reasoning updated", reasoning_tokens)
                except Exception:
                    pass
            
            # Count tokens for initial analysis
            tokens_used = self.provider.count_tokens(initial_prompt)
            if isinstance(response, str):
                tokens_used += self.provider.count_tokens(response)
            elif hasattr(response, 'content'):
                tokens_used += self.provider.count_tokens(response.content)
            
            # Parse the response and handle function calls
            specialist_results = []
            pending_specialist_calls: List[Dict[str, Any]] = []
            def _compact(s: str, lim: int = 300) -> str:
                try:
                    return re.sub(r"\s+", " ", s).strip()[:lim]
                except Exception:
                    return str(s)[:lim]
            
            # Process structured function calls if any
            if hasattr(response, 'function_calls') and response.function_calls:
                logger.info(f"Professor identified {len(response.function_calls)} specialist consultation(s)")
                for func_call in response.function_calls:
                    if func_call.name == "consult_graduate_specialist":
                        # Handle arguments - could be dict or string
                        arguments = func_call.arguments
                        if isinstance(arguments, str):
                            try:
                                arguments = json.loads(arguments)
                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse function arguments: {arguments}")
                                continue
                        pending_specialist_calls.append(arguments)
            # Some providers use `tool_calls` ala OpenAI; handle if present
            elif hasattr(response, 'tool_calls') and response.tool_calls:
                try:
                    calls = response.tool_calls
                    logger.info(f"Professor identified {len(calls)} tool_call(s) (OpenAI style)")
                    for call in calls:
                        # call may be dict-like or object with .function
                        fn = None
                        if isinstance(call, dict):
                            fn = call.get('function') or call
                        else:
                            fn = getattr(call, 'function', None) or call
                        if isinstance(fn, dict):
                            name = fn.get('name') or fn.get('tool_name') or fn.get('tool') or fn.get('function') or fn.get('name')
                            args = fn.get('arguments') or fn.get('parameters') or {}
                        else:
                            name = getattr(fn, 'name', None)
                            args = getattr(fn, 'arguments', {})
                        if name == 'consult_graduate_specialist':
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    # Relaxed fallback: attempt Python-literal style
                                    try:
                                        args = ast.literal_eval(args)
                                    except Exception:
                                        logger.error(f"Failed to parse function arguments: {args}")
                                        continue
                            logger.info(f"Professor detected specialist via tool_calls: { _compact(json.dumps(args) if isinstance(args, dict) else str(args)) }")
                            pending_specialist_calls.append(args)
                except Exception as e:
                    logger.error(f"Error handling response.tool_calls: {e}")
            else:
                # Fallback parsing of textual specialist calls when provider lacks structured tool support
                # Handle both plain-string responses and wrapper objects with a .content field
                text_response = response if isinstance(response, str) else getattr(response, 'content', '')
                
                def _normalize_specialist_args(raw: Dict[str, Any]) -> Dict[str, Any]:
                    """Map various model-produced argument shapes into our required schema."""
                    spec = (
                        raw.get('specialization') or
                        raw.get('expertise') or
                        raw.get('domain') or
                        'general'
                    )
                    task = (
                        raw.get('specific_task') or
                        raw.get('task') or
                        raw.get('task_description') or
                        raw.get('query') or
                        (raw.get('subtasks', [{}])[0].get('description') if isinstance(raw.get('subtasks'), list) and raw.get('subtasks') else '') or
                        ''
                    )
                    context_for_spec = (
                        raw.get('context_for_specialist') or
                        raw.get('query') or
                        ''
                    )
                    constraints_for_spec = (
                        raw.get('problem_constraints') or
                        raw.get('verification_requirements') or
                        ''
                    )
                    return {
                        'specialization': spec,
                        'specific_task': task,
                        'context_for_specialist': context_for_spec,
                        'problem_constraints': constraints_for_spec,
                    }

                def _parse_args_relaxed(s: str) -> Optional[Dict[str, Any]]:
                    """Try to parse non-strict JSON or Python-like dicts; finally extract quoted key-values by regex."""
                    if not isinstance(s, str):
                        return s if isinstance(s, dict) else None
                    # 1) strict JSON
                    try:
                        val = json.loads(s)
                        return val if isinstance(val, dict) else None
                    except Exception:
                        pass
                    # 2) Python literal
                    try:
                        val = ast.literal_eval(s)
                        return val if isinstance(val, dict) else None
                    except Exception:
                        pass
                    # 3) Quote bare keys heuristically then retry JSON
                    try:
                        tmp = re.sub(r'([\{,\s])([A-Za-z_][\w\-]*)\s*:', r'\1"\2":', s)
                        val = json.loads(tmp)
                        if isinstance(val, dict):
                            return val
                    except Exception:
                        pass
                    # 4) Extract quoted key-values (single or double quotes)
                    keys = [
                        'specialization','expertise','domain',
                        'specific_task','task','task_description','query',
                        'context_for_specialist','problem_constraints','verification_requirements'
                    ]
                    out: Dict[str, Any] = {}
                    for k in keys:
                        m = re.search(rf"{k}\\s*:\\s*([\"'])(.*?)\\1", s, re.IGNORECASE | re.DOTALL)
                        if m:
                            out[k] = m.group(2).strip()
                    return out or None

                if isinstance(text_response, str) and text_response:
                    # 1) Check for legacy one-liner format: consult_graduate_specialist({...})
                    pattern = r"consult_graduate_specialist\s*\((.*)\)"
                    for line in text_response.splitlines():
                        line = line.strip()
                        match = re.search(pattern, line)
                        if match:
                            json_part = match.group(1)
                            try:
                                arguments = json.loads(json_part)
                                logger.info(f"Professor detected specialist via regex_call: { _compact(json_part) }")
                                pending_specialist_calls.append(_normalize_specialist_args(arguments))
                            except json.JSONDecodeError:
                                # Relaxed fallback: attempt Python-literal style
                                try:
                                    arguments = ast.literal_eval(json_part)
                                    if isinstance(arguments, dict):
                                        logger.info(f"Professor detected specialist via regex_call (relaxed JSON)")
                                        pending_specialist_calls.append(_normalize_specialist_args(arguments))
                                    else:
                                        logger.error(f"Specialist arguments not a dict after relaxed parse: {type(arguments)}")
                                except Exception:
                                    logger.error(f"Failed to parse specialist arguments: {json_part}")
                    # 1b) Multi-line function-call capture across text
                    if not pending_specialist_calls:
                        ml_matches = re.findall(r"consult_graduate_specialist\s*\(([\s\S]*?)\)", text_response, re.IGNORECASE)
                        for json_part in ml_matches:
                            parsed = _parse_args_relaxed(json_part)
                            if isinstance(parsed, dict) and parsed:
                                logger.info("Professor detected specialist via multiline_regex_call (relaxed)")
                                pending_specialist_calls.append(_normalize_specialist_args(parsed))
                    # 2) Check for JSON array format containing tool/function entries
                    parsed_array = False
                    try:
                        start = text_response.find('[')
                        end = text_response.rfind(']') + 1
                        if start != -1 and end > start:
                            json_blob = text_response[start:end]
                            tool_calls = json.loads(json_blob)
                            parsed_array = True
                            for call in tool_calls:
                                if not isinstance(call, dict):
                                    continue
                                name = (
                                    call.get('tool') or
                                    call.get('function') or
                                    call.get('name') or
                                    call.get('tool_name') or
                                    (call.get('function') or {}).get('name')
                                )
                                if name == 'consult_graduate_specialist':
                                    arguments = call.get('parameters', {}) or call.get('args', {}) or call.get('arguments') or (call.get('function') or {}).get('arguments')
                                    logger.info(f"Professor detected specialist via json_array: { _compact(json.dumps(arguments) if isinstance(arguments, dict) else str(arguments)) }")
                                    pending_specialist_calls.append(_normalize_specialist_args(arguments))
                    except json.JSONDecodeError:
                        logger.error("Failed to parse JSON tool/function call array from model output")
                    # 3) Try single-object JSON with tool/function field or actions array
                    if not pending_specialist_calls and not parsed_array:
                        try:
                            start_obj = text_response.find('{')
                            end_obj = text_response.rfind('}') + 1
                            if start_obj != -1 and end_obj > start_obj:
                                json_blob = text_response[start_obj:end_obj]
                                maybe_obj = json.loads(json_blob)
                                if isinstance(maybe_obj, dict):
                                    # Direct single-call object case
                                    name = (
                                        maybe_obj.get('tool') or
                                        maybe_obj.get('function') or
                                        maybe_obj.get('name') or
                                        maybe_obj.get('tool_name') or
                                        (maybe_obj.get('function') or {}).get('name')
                                    )
                                    if name == 'consult_graduate_specialist':
                                        arguments = (
                                            maybe_obj.get('parameters', {}) or
                                            maybe_obj.get('args', {}) or
                                            maybe_obj.get('arguments') or
                                            (maybe_obj.get('function') or {}).get('arguments')
                                        )
                                        logger.info(f"Professor detected specialist via single_object: { _compact(json.dumps(arguments) if isinstance(arguments, dict) else str(arguments)) }")
                                        pending_specialist_calls.append(_normalize_specialist_args(arguments))
                                    # Nested consultations array case
                                    consultations = maybe_obj.get('consultations') or maybe_obj.get('calls')
                                    if isinstance(consultations, list):
                                        for call in consultations:
                                            if not isinstance(call, dict):
                                                continue
                                            cname = (
                                                call.get('tool') or
                                                call.get('function') or
                                                call.get('name') or
                                                call.get('tool_name') or
                                                (call.get('function') or {}).get('name')
                                            )
                                            if cname == 'consult_graduate_specialist':
                                                cargs = (
                                                    call.get('parameters', {}) or
                                                    call.get('args', {}) or
                                                    call.get('arguments') or
                                                    (call.get('function') or {}).get('arguments')
                                                )
                                                logger.info(f"Professor detected specialist via consultations_array: { _compact(json.dumps(cargs) if isinstance(cargs, dict) else str(cargs)) }")
                                                pending_specialist_calls.append(_normalize_specialist_args(cargs))
                        except json.JSONDecodeError:
                            logger.error("Failed to parse single JSON tool/function call object from model output")
                    # 4) Scan fenced code blocks for JSON that may contain tool/function calls
                    if not pending_specialist_calls:
                        code_blocks = re.findall(r"```(?:json|javascript|js|python|py)?\n([\s\S]*?)```", text_response, re.IGNORECASE)
                        for block in code_blocks:
                            block_stripped = block.strip()
                            if not block_stripped:
                                continue
                            try:
                                parsed = json.loads(block_stripped)
                            except json.JSONDecodeError:
                                # try relaxed Python-literal style blocks
                                try:
                                    parsed = ast.literal_eval(block_stripped)
                                except Exception:
                                    continue
                            # Recursively extract calls from parsed content
                            def _collect_calls_from_json(obj):
                                if isinstance(obj, list):
                                    for item in obj:
                                        _collect_calls_from_json(item)
                                elif isinstance(obj, dict):
                                    # Check current dict for a function/tool signature
                                    name = (
                                        obj.get('tool') or obj.get('function') or obj.get('name') or obj.get('tool_name')
                                    )
                                    if not name and isinstance(obj.get('function'), dict):
                                        name = obj['function'].get('name')
                                    if name == 'consult_graduate_specialist':
                                        args = (
                                            obj.get('parameters') or obj.get('args') or obj.get('arguments') or
                                            (obj.get('function') or {}).get('arguments')
                                        )
                                        if isinstance(args, str):
                                            parsed_args = _parse_args_relaxed(args)
                                            args = parsed_args if isinstance(parsed_args, dict) else None
                                        if isinstance(args, dict):
                                            logger.info(f"Professor detected specialist via code_block: { _compact(json.dumps(args)) }")
                                            pending_specialist_calls.append(_normalize_specialist_args(args))
                                    # Recurse into dict values (to reach nested arrays like 'consultations')
                                    try:
                                        for v in obj.values():
                                            _collect_calls_from_json(v)
                                    except Exception:
                                        pass
                            _collect_calls_from_json(parsed)

                    # 4b) If 'consultations' array appears in plain text (not code-block), extract array region and parse
                    if not pending_specialist_calls and isinstance(text_response, str) and 'consultations' in text_response:
                        try:
                            key_idx = text_response.find('consultations')
                            bracket_start = text_response.find('[', key_idx)
                            if bracket_start != -1:
                                # naive bracket matching for the array
                                depth = 0
                                end_idx = None
                                for j in range(bracket_start, len(text_response)):
                                    ch = text_response[j]
                                    if ch == '[':
                                        depth += 1
                                    elif ch == ']':
                                        depth -= 1
                                        if depth == 0:
                                            end_idx = j + 1
                                            break
                                if end_idx:
                                    array_blob = text_response[bracket_start:end_idx]
                                    try:
                                        calls = json.loads(array_blob)
                                    except json.JSONDecodeError:
                                        # try relaxed Python-literal style
                                        calls = ast.literal_eval(array_blob)
                                    if isinstance(calls, list):
                                        for call in calls:
                                            if not isinstance(call, dict):
                                                continue
                                            cname = (
                                                call.get('tool') or call.get('function') or call.get('name') or call.get('tool_name') or
                                                (call.get('function') or {}).get('name')
                                            )
                                            if cname == 'consult_graduate_specialist':
                                                cargs = (
                                                    call.get('parameters', {}) or call.get('args', {}) or call.get('arguments') or
                                                    (call.get('function') or {}).get('arguments')
                                                )
                                                logger.info(f"Professor detected specialist via consultations_array_text: { _compact(json.dumps(cargs) if isinstance(cargs, dict) else str(cargs)) }")
                                                pending_specialist_calls.append(_normalize_specialist_args(cargs))
                        except Exception:
                            logger.debug("Consultations array extraction failed in plain text path")

                    # 5) Heuristic: if the keyword appears but we still have no calls, try to extract nearest JSON braces
                    if not pending_specialist_calls and isinstance(text_response, str) and 'consult_graduate_specialist' in text_response:
                        idx = text_response.find('consult_graduate_specialist')
                        brace_start = text_response.find('{', idx)
                        if brace_start != -1:
                            # naive brace matching
                            depth = 0
                            end = None
                            for j in range(brace_start, len(text_response)):
                                ch = text_response[j]
                                if ch == '{':
                                    depth += 1
                                elif ch == '}':
                                    depth -= 1
                                    if depth == 0:
                                        end = j + 1
                                        break
                            if end:
                                blob = text_response[brace_start:end]
                                parsed_args = _parse_args_relaxed(blob)
                                if isinstance(parsed_args, dict) and parsed_args:
                                    logger.info(f"Professor detected specialist via heuristic_braces (relaxed)")
                                    pending_specialist_calls.append(_normalize_specialist_args(parsed_args))
                                else:
                                    logger.info("Professor found 'consult_graduate_specialist' mention but could not parse arguments via heuristic")
                    if not pending_specialist_calls and isinstance(text_response, str) and 'consult_graduate_specialist' in text_response:
                        logger.info("Professor saw 'consult_graduate_specialist' mention but no parsable arguments were found")

            # Execute pending specialist consultations with explicit progress updates
            if pending_specialist_calls:
                total = len(pending_specialist_calls)
                logger.info(f"Professor making {total} specialist consultation(s)")
                if progress_callback:
                    phase_msg = f"Preparing {total} specialist consultation(s)"
                    progress_callback(0.0, phase_msg)
                for i, arguments in enumerate(pending_specialist_calls, 1):
                    spec = arguments.get('expertise') or arguments.get('specialization', 'unknown')
                    if progress_callback:
                        progress_callback((i - 1) / max(1, total), f"Specialist {i}/{total} ({spec}): starting")
                    specialist_result = await self._execute_specialist_consultation(
                        arguments,
                        context.prompt,
                        constraints,
                        progress_callback,
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
                
                # Extract reasoning tokens from synthesis if available
                if hasattr(self.provider, 'last_reasoning_tokens'):
                    synthesis_reasoning_tokens = getattr(self.provider, 'last_reasoning_tokens', 0)
                    reasoning_tokens += synthesis_reasoning_tokens
                    self.last_reasoning_tokens = reasoning_tokens
            else:
                synthesis = response if isinstance(response, str) else response.content
            
            logger.info(f"Professor completed analysis with {len(specialist_results)} specialist consultations, tokens: {tokens_used}")
            
            # Aggregate context pressure flags from specialist results
            context_summarized_any = any(
                (r.get("metadata", {}) or {}).get("context_summarized", False) for r in specialist_results
            ) if specialist_results else False
            context_truncated_any = any(
                (r.get("metadata", {}) or {}).get("context_truncated", False) for r in specialist_results
            ) if specialist_results else False

            # Build metadata with reasoning token information and flags
            metadata = {
                "specialist_consultations": len(specialist_results),
                "specialist_results": specialist_results,
                "approach": "function_calling",
                "function_calling_used": True,
                # context flags propagated upward
                "context_summarized": context_summarized_any,
                "context_truncated": context_truncated_any,
            }
            
            # Add reasoning token metadata if available
            if reasoning_tokens > 0:
                metadata["reasoning_tokens"] = reasoning_tokens
            if reasoning_summary:
                metadata["reasoning_summary"] = reasoning_summary
            
            return AgentResult(
                output=synthesis,
                metadata=metadata,
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
                # Provider lacks explicit function-calling support; fall back to a plain completion
                # WITHOUT passing the functions payload because some providers (e.g. LMStudio) will
                # reject unknown parameters.
                logger.info("Provider doesn't have complete_with_functions; falling back to plain completion (streaming)")
                response = await self.provider.complete(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    temperature=temperature if temperature is not None else self.temperature,
                    stream=True,
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
            # Build a stable specialist-specific job_id derived from the parent job and task
            _parent_job_id = None
            try:
                _parent_job_id = get_current_job_id()
            except Exception:
                _parent_job_id = None
            # Derive deterministic child job_id to avoid lock contention with professor
            _specialist_job_id = None
            if _parent_job_id:
                try:
                    _slug = re.sub(r"[^a-z0-9_]+", "", specialization.lower().replace(" ", "_"))
                    _task_hash = hashlib.sha1((specific_task or "").encode("utf-8")).hexdigest()[:8]
                    _specialist_job_id = f"{_parent_job_id}:spec:{_slug}:{_task_hash}"
                except Exception:
                    _specialist_job_id = f"{_parent_job_id}:spec"

            specialist_engine = SelfEvolve(
                generator=specialist,
                evaluator=specialist_evaluator,
                refiner=specialist_refiner,
                max_iters=getattr(self, 'specialist_max_iters', settings.specialist_max_iters),  # Honor runner override when provided
                progress_callback=specialist_progress_callback if progress_callback else None,
                job_id=_specialist_job_id,
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
                    # Ensure job_id propagates for provider generation locking
                    "job_id": _specialist_job_id,
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

            # Create result with enhanced metadata (self-evolve aligned)
            result = {
                "specialization": specialization,
                "task": specific_task,
                "context": context_for_specialist,
                "constraints": problem_constraints,
                "output": specialist_solution.output,
                "final_answer": final_answer,
                "final_answer_value": final_answer_value,
                "final_evaluation": final_evaluation,
                "total_iterations": total_iterations,
                "formatted_result": formatted_result,
                "professor_reasoning_context": professor_reasoning_context,
                "reasoning_section": reasoning_section,
                "session_details": {
                    "iterations": [
                        {
                            "iteration": i + 1,
                            "reasoning_summary": iter_data.get("metadata", {}).get("generator", {}).get("reasoning_summary", ""),
                            "evaluator_reasoning_summary": iter_data.get("metadata", {}).get("evaluator", {}).get("reasoning_summary", ""),
                            "refiner_reasoning_summary": iter_data.get("metadata", {}).get("refiner", {}).get("reasoning_summary", ""),
                            "reasoning_tokens": (
                                (iter_data.get("metadata", {}).get("generator", {}).get("reasoning_tokens", 0) or 0)
                                + (iter_data.get("metadata", {}).get("evaluator", {}).get("reasoning_tokens", 0) or 0)
                                + (iter_data.get("metadata", {}).get("refiner", {}).get("reasoning_tokens", 0) or 0)
                            ),
                            "answer": iter_data.get("output", "") if (i + 1) == len(specialist_solution.evolution_history) else (iter_data.get("output", "")[:100] + "..." if iter_data.get("output", "") else ""),
                            "evaluation_feedback": iter_data.get("feedback", ""),
                            "timestamp": iter_data.get("timestamp", ""),
                        }
                        for i, iter_data in enumerate(specialist_solution.evolution_history)
                    ] if specialist_solution.evolution_history else []
                },
                "metadata": {
                    "iterations": specialist_solution.iterations,
                    "converged": specialist_solution.metadata.get('converged', False),
                    "total_tokens": specialist_solution.total_tokens,
                    "stop_reason": specialist_solution.metadata.get('stop_reason', 'unknown'),
                    "enhanced_context_used": True,
                    "evolution_history_available": bool(specialist_solution.evolution_history),
                    "complete_reasoning_provided": bool(reasoning_section),
                    # Context pressure flags propagated from Self-Evolve
                    "context_summarized": specialist_solution.metadata.get('context_summarized', False),
                    "context_truncated": specialist_solution.metadata.get('context_truncated', False),
                },
            }

            # Save consultation history for conversation continuity
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

            # Extract reasoning tokens from synthesis if available
            if hasattr(self.provider, 'last_reasoning_tokens'):
                synthesis_reasoning_tokens = getattr(self.provider, 'last_reasoning_tokens', 0)
                if synthesis_reasoning_tokens > 0:
                    self.last_reasoning_tokens += synthesis_reasoning_tokens

            return self._normalize_output(synthesis)
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            # Fallback: concatenate results using formatted_result if available
            combined_parts = []
            for r in specialist_results:
                if 'formatted_result' in r:
                    combined_parts.append(r['formatted_result'])
                else:
                    combined_parts.append(f"{r.get('specialization', 'Specialist')}: {r.get('output', '')}")

            _out = "Combined specialist results:\n\n" + "\n\n".join(combined_parts)
            return self._normalize_output(_out)

    async def synthesize(
        self,
        original_problem: str,
        specialist_results: List[Dict[str, Any]],
        synthesis_plan: Optional[str] = None,
    ) -> AgentResult:
        """
        Synthesize specialist results into final answer.
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

            # Extract reasoning tokens if available
            reasoning_tokens = 0
            reasoning_summary = None
            if hasattr(self.provider, 'last_reasoning_tokens'):
                reasoning_tokens = getattr(self.provider, 'last_reasoning_tokens', 0)
                self.last_reasoning_tokens = reasoning_tokens
            if hasattr(self.provider, 'last_reasoning_summary'):
                reasoning_summary = getattr(self.provider, 'last_reasoning_summary', None)

            # Normalize and count tokens
            normalized = self._normalize_output(synthesis)
            tokens_used = self.provider.count_tokens(synthesis_prompt) + self.provider.count_tokens(normalized)

            # Build metadata with reasoning token information
            metadata = {
                "specialist_count": len(specialist_results),
                "synthesis_plan": synthesis_plan,
            }
            if reasoning_tokens > 0:
                metadata["reasoning_tokens"] = reasoning_tokens
            if reasoning_summary:
                metadata["reasoning_summary"] = reasoning_summary

            return AgentResult(
                output=normalized,
                metadata=metadata,
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

            fallback_output = "Combined specialist results:\n\n" + "\n\n".join(combined_parts)
            normalized_fb = self._normalize_output(fallback_output)
            return AgentResult(
                output=normalized_fb,
                metadata={"error": str(e), "fallback": True},
                tokens_used=self.provider.count_tokens(normalized_fb),
            )

    async def continue_conversation(self, follow_up: str, **kwargs) -> AgentResult:
        """Continue an existing conversation using provider's capabilities."""
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

            # Extract reasoning tokens if available
            reasoning_tokens = 0
            reasoning_summary = None
            if hasattr(self.provider, 'last_reasoning_tokens'):
                reasoning_tokens = getattr(self.provider, 'last_reasoning_tokens', 0)
                self.last_reasoning_tokens = reasoning_tokens
            if hasattr(self.provider, 'last_reasoning_summary'):
                reasoning_summary = getattr(self.provider, 'last_reasoning_summary', None)

            # Extract content and normalize
            content = response if isinstance(response, str) else (
                response.content if hasattr(response, 'content') else str(response)
            )
            content = self._normalize_output(content)
            tokens_used = self.provider.count_tokens(follow_up_prompt) + self.provider.count_tokens(content)

            logger.info(f"Conversation continuation completed, tokens: {tokens_used}")

            # Build metadata with reasoning token information
            metadata = {
                "conversation_continued": True,
                "provider_continuation": True,
                "approach": "provider_continuation",
            }
            if reasoning_tokens > 0:
                metadata["reasoning_tokens"] = reasoning_tokens
            if reasoning_summary:
                metadata["reasoning_summary"] = reasoning_summary

            return AgentResult(
                output=content,
                metadata=metadata,
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

 