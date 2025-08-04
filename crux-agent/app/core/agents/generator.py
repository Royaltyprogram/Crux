"""
Generator agent for producing initial answers.
"""
from typing import Optional

from app.core.agents.base import AbstractAgent, AgentContext, AgentResult
from app.core.providers.base import BaseProvider
from app.core.agents.prompts.generator_prompt import get_generator_system_prompt
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GeneratorAgent(AbstractAgent):
    """
    Generator agent that produces initial answers to questions.
    """
    
    DEFAULT_SYSTEM_PROMPT = get_generator_system_prompt()
    
    def __init__(
        self,
        provider: BaseProvider,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """Initialize Generator agent."""
        super().__init__(
            role="generator",
            provider=provider,
            system_prompt=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
            temperature=temperature,
        )
    
    async def run(self, context: AgentContext) -> AgentResult:
        """
        Generate an initial answer to the question.
        
        Args:
            context: Must contain 'prompt' (the question to answer)
            
        Returns:
            Generated answer
        """
        logger.info(f"Generating answer for: {context.prompt[:100]}...")
        
        # Extract constraints and additional context
        constraints = context.additional_context.get("constraints")
        problem_context = context.additional_context.get("context")
        
        # Build the complete prompt
        full_prompt = context.prompt + "\n\nsolve this problem with consulting the graduate_specialist and perfect mathematical rigor."
        
        if problem_context:
            full_prompt = f"Context: {problem_context}\n\nQuestion: {full_prompt}"
        
        if constraints:
            full_prompt = f"{full_prompt}\n\nConstraints: {constraints}"
        
        try:
            # Generate answer
            answer = await self._generate(
                prompt=full_prompt,
                temperature=self.temperature,
            )
            
            # Count tokens using provider's accurate tokenization
            tokens_used = self.provider.count_tokens(full_prompt + answer)

            # Extract reasoning summary and tokens from provider (if any)
            reasoning_summary = ""
            reasoning_tokens = 0
            if hasattr(self.provider, "get_last_reasoning_summary"):
                reasoning_summary = self.provider.get_last_reasoning_summary()
            if hasattr(self.provider, "last_reasoning_tokens"):
                reasoning_tokens = self.provider.last_reasoning_tokens

            logger.info(f"Answer generation complete, tokens: {tokens_used}, reasoning tokens: {reasoning_tokens}")
            
            return AgentResult(
                output=answer,
                metadata={
                    "question": context.prompt,
                    "constraints": constraints,
                    "context": problem_context,
                    "temperature": self.temperature,
                    "reasoning_summary": reasoning_summary,
                    "reasoning_tokens": reasoning_tokens,
                },
                tokens_used=tokens_used,
            )
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            # Fallback to a simple response
            fallback_answer = f"I apologize, but I encountered an error while generating an answer to your question: {context.prompt}"
            
            return AgentResult(
                output=fallback_answer,
                metadata={
                    "error": str(e),
                    "fallback": True,
                    "question": context.prompt,
                },
                tokens_used=self.provider.count_tokens(fallback_answer),
            ) 