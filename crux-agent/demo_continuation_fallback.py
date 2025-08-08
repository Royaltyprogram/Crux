#!/usr/bin/env python3
"""
Demonstration script for the improved continuation fallback strategy.

This script shows how the new fallback mechanism works:
• When continuation is requested with evolution_history and current iteration fails to generate valid output
• Instead of raising a hard exception, it falls back to the latest valid iteration
• Marks should_stop = True and metadata.fallback_used = True with diagnostic message
• The allow_continuation_fallback flag (default True) can be used to toggle this behavior

Run with: python demo_continuation_fallback.py
"""

import asyncio
from unittest.mock import MagicMock

from app.core.engine.self_evolve import Problem, SelfEvolve, Solution
from app.core.agents.base import AbstractAgent, AgentContext, AgentResult


class DemoInvalidGeneratorAgent(AbstractAgent):
    """Demo generator that produces invalid outputs after the first call."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split()) if x.strip() else 0
        super().__init__(role="generator", provider=provider)
        self.call_count = 0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Generate invalid outputs to trigger fallback."""
        self.call_count += 1
        
        # Always return invalid outputs to trigger fallback
        invalid_outputs = ["", "   ", "\n\t  \n", "..."]
        output = invalid_outputs[(self.call_count - 1) % len(invalid_outputs)]
        
        return AgentResult(
            output=output,
            metadata={
                "temperature": 0.7,
                "reasoning_summary": f"Demo invalid output {self.call_count}",
            },
            tokens_used=0,
        )


class DemoEvaluatorAgent(AbstractAgent):
    """Demo evaluator that provides feedback."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split())
        super().__init__(role="evaluator", provider=provider)
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Evaluate answers."""
        feedback = "Good answer but could be improved."
        
        return AgentResult(
            output=feedback,
            feedback=feedback,
            metadata={
                "should_stop": False,
                "reasoning_summary": "Demo evaluation",
            },
            tokens_used=len(feedback.split()),
        )


class DemoRefinerAgent(AbstractAgent):
    """Demo refiner that provides refinement prompts."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split())
        super().__init__(role="refiner", provider=provider)
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Refine prompts."""
        refined_prompt = f"{context.prompt}\n\nPlease provide more details."
        
        return AgentResult(
            output=refined_prompt,
            metadata={"original_prompt": context.prompt},
            tokens_used=len(refined_prompt.split()),
        )


async def demo_with_fallback_enabled():
    """Demonstrate fallback behavior when enabled (default)."""
    print("=== DEMO: Continuation Fallback ENABLED (default) ===")
    
    # Create agents
    generator = DemoInvalidGeneratorAgent()
    evaluator = DemoEvaluatorAgent()
    refiner = DemoRefinerAgent()
    
    # Create SelfEvolve engine with fallback enabled (default)
    engine = SelfEvolve(
        generator=generator,
        evaluator=evaluator,
        refiner=refiner,
        max_iters=3,
        allow_continuation_fallback=True  # This is the default
    )
    
    # Create a test problem
    problem = Problem(
        question="What is the capital of France?",
        context="Provide a clear and accurate answer",
        constraints="Answer should be factual"
    )
    
    # Create evolution history with a valid iteration
    evolution_history = [
        {
            "iteration": 1,
            "prompt": "What is the capital of France?",
            "output": "The capital of France is Paris, a beautiful city located in the north-central part of the country along the Seine River.",  # Valid output
            "feedback": "Good answer, but could include more historical context.",
            "should_stop": False,
            "metadata": {
                "generator": {
                    "temperature": 0.7,
                    "reasoning_summary": "Initial valid response",
                    "tokens_used": 22
                },
                "evaluator": {
                    "should_stop": False,
                    "reasoning_summary": "Valid output evaluation",
                    "tokens_used": 10
                }
            },
            "refined_prompt": "What is the capital of France?\n\nPlease provide more details."
        }
    ]
    
    try:
        # Try to resume - this should use fallback instead of raising exception
        solution = await engine.resume_solve(problem, evolution_history, start_iteration=2)
        
        print(f"✅ SUCCESS: Got solution instead of exception!")
        print(f"📄 Output: {solution.output}")
        print(f"🔄 Fallback used: {solution.metadata['fallback_used']}")
        print(f"🛡️ Stop reason: {solution.metadata['stop_reason']}")
        print(f"💬 Diagnostic: {solution.metadata.get('fallback_diagnostic', 'None')}")
        print(f"🔢 Total iterations: {solution.iterations}")
        print(f"🪙 Total tokens: {solution.total_tokens}")
        
    except Exception as e:
        print(f"❌ UNEXPECTED: Exception raised: {e}")


async def demo_with_fallback_disabled():
    """Demonstrate fallback behavior when disabled."""
    print("\n=== DEMO: Continuation Fallback DISABLED ===")
    
    # Create agents
    generator = DemoInvalidGeneratorAgent()
    evaluator = DemoEvaluatorAgent()
    refiner = DemoRefinerAgent()
    
    # Create SelfEvolve engine with fallback disabled
    engine = SelfEvolve(
        generator=generator,
        evaluator=evaluator,
        refiner=refiner,
        max_iters=3,
        allow_continuation_fallback=False  # Disable fallback
    )
    
    # Create a test problem
    problem = Problem(
        question="What is machine learning?",
        context="Provide a comprehensive explanation",
        constraints="Include examples and applications"
    )
    
    # Create evolution history with a valid iteration
    evolution_history = [
        {
            "iteration": 1,
            "prompt": "What is machine learning?",
            "output": "Machine learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed for every task.",  # Valid output
            "feedback": "Good foundation but needs more examples.",
            "should_stop": False,
            "metadata": {
                "generator": {"tokens_used": 25},
                "evaluator": {"should_stop": False, "tokens_used": 8}
            }
        }
    ]
    
    try:
        # Try to resume - this should raise exception because fallback is disabled
        solution = await engine.resume_solve(problem, evolution_history, start_iteration=2)
        print(f"❌ UNEXPECTED: Got solution when exception was expected!")
        
    except Exception as e:
        print(f"✅ EXPECTED: Exception raised as expected: {e}")


async def demo_no_valid_history():
    """Demonstrate behavior when no valid iterations exist in history."""
    print("\n=== DEMO: No Valid Iterations in History ===")
    
    # Create agents
    generator = DemoInvalidGeneratorAgent()
    evaluator = DemoEvaluatorAgent()
    refiner = DemoRefinerAgent()
    
    # Create SelfEvolve engine with fallback enabled
    engine = SelfEvolve(
        generator=generator,
        evaluator=evaluator,
        refiner=refiner,
        max_iters=2,
        allow_continuation_fallback=True  # Enabled but no valid history
    )
    
    # Create a test problem
    problem = Problem(question="Explain quantum computing")
    
    # Create evolution history with ONLY invalid iterations
    evolution_history = [
        {
            "iteration": 1,
            "prompt": "Explain quantum computing",
            "output": "",  # Invalid: empty string
            "feedback": "Empty response, please provide content.",
            "should_stop": False,
            "metadata": {
                "generator": {"tokens_used": 0},
                "evaluator": {"should_stop": False, "tokens_used": 7}
            }
        }
    ]
    
    try:
        # Try to resume - this should raise exception because no valid iterations exist
        solution = await engine.resume_solve(problem, evolution_history, start_iteration=2)
        print(f"❌ UNEXPECTED: Got solution when exception was expected!")
        
    except Exception as e:
        print(f"✅ EXPECTED: Exception raised because no valid iterations exist: {e}")


async def main():
    """Run all demonstrations."""
    print("🚀 DEMONSTRATION: Improved Continuation Fallback Strategy")
    print("=" * 60)
    
    await demo_with_fallback_enabled()
    await demo_with_fallback_disabled()
    await demo_no_valid_history()
    
    print("\n" + "=" * 60)
    print("✨ SUMMARY:")
    print("• When allow_continuation_fallback=True (default) and valid iterations exist:")
    print("  → Falls back to latest valid iteration instead of raising exception")
    print("  → Marks fallback_used=True and includes diagnostic message")
    print("• When allow_continuation_fallback=False:")
    print("  → Raises exception as before (backward compatibility)")
    print("• When no valid iterations exist in history:")
    print("  → Always raises exception regardless of fallback setting")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
