"""
Specialist agent for domain-specific reasoning.
"""
from typing import Optional, Any, Dict, List

from app.core.agents.base import AbstractAgent, AgentContext, AgentResult
from app.core.agents.prompts.graduate_worker_prompt import get_specialist_system_prompt, build_specialist_prompt
from app.core.providers.base import BaseProvider
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SpecialistAgent(AbstractAgent):
    """
    Specialist agent with domain expertise.
    """
    
    def __init__(
        self,
        domain: str,
        provider: BaseProvider,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize Specialist agent.
        
        Args:
            domain: Specialist domain/expertise area
            provider: LLM provider
            system_prompt: Custom system prompt (overrides domain default)
            temperature: Generation temperature
        """
        # Use domain-specific prompt from prompts module
        if not system_prompt:
            system_prompt = get_specialist_system_prompt(domain)
        
        super().__init__(
            role=f"specialist_{domain}",
            provider=provider,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        self.domain = domain

    async def _generate_with_functions(
        self,
        *,
        prompt: str,
        functions: List[Dict[str, Any]],
        temperature: Optional[float] = None,
    ) -> str:
        """Generate using function-calling interface, granting access to code interpreter if supported."""
        try:
            # If the provider supports function calling, use it (adds code interpreter automatically)
            if hasattr(self.provider, "complete_with_functions"):
                response = await self.provider.complete_with_functions(
                    prompt=prompt,
                    functions=functions,
                    system_prompt=self.system_prompt,
                    temperature=temperature if temperature is not None else self.temperature,
                )

                # Provider may return raw string or an object with a content attribute
                if isinstance(response, str):
                    return response
                if hasattr(response, "content"):
                    return response.content  # type: ignore[attr-defined]

                # Fallback – cast to string
                return str(response)

            # Provider does not support function calling – fallback to regular generation
            return await self._generate(
                prompt=prompt,
                temperature=temperature if temperature is not None else self.temperature,
            )

        except Exception:
            # Any unexpected failure – fallback to regular generation
            return await self._generate(
                prompt=prompt,
                temperature=temperature if temperature is not None else self.temperature,
            )

    async def run(self, context: AgentContext) -> AgentResult:
        """
        Execute specialist reasoning for the given task.
        
        Args:
            context: Execution context with task
            
        Returns:
            Specialist result
        """
        logger.info(f"Specialist ({self.domain}) processing task: {context.prompt[:100]}...")
        
        # Extract comprehensive context information (following self-evolve pattern)
        task_info = context.additional_context.get("task_info", {})
        context_str = context.additional_context.get("context", "")
        
        # Enhanced context extraction from professor
        professor_reasoning = context.additional_context.get("professor_reasoning_context", "")
        problem_constraints = context.additional_context.get("problem_constraints", "")
        original_problem = context.additional_context.get("original_problem", context.prompt)
        
        # Build comprehensive professor reasoning context (self-evolve pattern)
        enhanced_professor_context = ""
        if professor_reasoning or problem_constraints or original_problem != context.prompt:
            enhanced_professor_context = f"""
PROFESSOR'S REASONING CONTEXT:
Original Problem: {original_problem}
Specialist Context: {context_str}
Task Constraints: {problem_constraints}
Professor's Analysis: {professor_reasoning}

The professor has determined that this specific task requires your expertise in {self.domain}.
"""
        
        # Build specialist prompt using enhanced context
        specialist_prompt = build_specialist_prompt(
            specialization=self.domain,
            prompt=context.prompt,
            context=enhanced_professor_context if enhanced_professor_context else context_str
        )
        
        try:
            # Generate specialist response (enable code execution via function-calling API)
            response_text = await self._generate_with_functions(
                prompt=specialist_prompt,
                functions=[],  # No custom functions – enables built-in code interpreter
                temperature=self.temperature,
            )
            
            # Count tokens for cost tracking
            tokens = self.provider.count_tokens(specialist_prompt + response_text)
            
            logger.info(f"Specialist ({self.domain}) completed task, tokens: {tokens}")
            
            # Enhanced metadata including comprehensive context (self-evolve pattern)
            enhanced_metadata = {
                "domain": self.domain,
                "task": context.prompt,
                "task_info": task_info,
                "reasoning_summary": self.provider.get_last_reasoning_summary() if hasattr(self.provider, "get_last_reasoning_summary") else "",
                "original_problem": original_problem,
                "professor_reasoning_context": professor_reasoning,
                "problem_constraints": problem_constraints,
                "context_str": context_str,
                "enhanced_context_used": bool(enhanced_professor_context),
            }
            
            return AgentResult(
                output=response_text,
                metadata=enhanced_metadata,
                tokens_used=tokens,
            )
            
        except Exception as e:
            logger.error(f"Specialist ({self.domain}) failed: {e}")
            return AgentResult(
                output=f"Error in {self.domain} specialist: {str(e)}",
                metadata={"error": str(e), "domain": self.domain},
            )
    
    def __repr__(self) -> str:
        """String representation."""
        return f"SpecialistAgent(domain='{self.domain}', provider={self.provider.__class__.__name__})" 