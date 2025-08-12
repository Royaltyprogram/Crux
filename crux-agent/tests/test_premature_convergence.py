"""
Tests to expose premature convergence issues in SelfEvolve engine.

These tests are designed to fail and demonstrate cases where the SelfEvolve
engine incorrectly claims convergence when the generator produces obviously
incomplete answers.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.engine.self_evolve import Problem, SelfEvolve, Solution
from app.core.agents.base import AbstractAgent, AgentContext, AgentResult


class MockIncompleteGeneratorAgent(AbstractAgent):
    """Mock generator that deliberately produces incomplete answers."""
    
    def __init__(self):
        # Create a simple mock provider
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split())  # Simple token counting
        super().__init__(role="generator", provider=provider)
        self.call_count = 0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Generate deliberately incomplete answers."""
        self.call_count += 1
        
        # For simple math problem, give obviously incomplete answers
        if "1+1" in context.prompt or "prove 1+1=2" in context.prompt.lower():
            if self.call_count == 1:
                incomplete_answer = "To prove 1+1=2, we need to start with basic arithmetic principles..."
            elif self.call_count == 2:
                incomplete_answer = "Starting from Peano axioms, we can define addition. The proof requires several steps..."
            else:
                incomplete_answer = "The proof involves understanding that 1 is the successor of 0, and addition..."
        else:
            incomplete_answer = f"This is a partial answer (attempt {self.call_count}). The complete solution requires more work..."
        
        return AgentResult(
            output=incomplete_answer,
            metadata={
                "temperature": 0.7,
                "reasoning_summary": f"Incomplete reasoning attempt {self.call_count}",
            },
            tokens_used=len(incomplete_answer.split()),
        )


class MockEagerEvaluatorAgent(AbstractAgent):
    """Mock evaluator that incorrectly signals to stop on incomplete answers."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split())
        super().__init__(role="evaluator", provider=provider)
        self.evaluation_count = 0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Evaluate answers, incorrectly signaling stop for incomplete answers."""
        self.evaluation_count += 1
        
        # Simulate an evaluator that prematurely says the solution is complete
        # This is the bug we want to expose - the evaluator is too eager
        if self.evaluation_count >= 2:  # After 2nd iteration, falsely claim completion
            feedback = "The answer looks complete and satisfactory. <stop>"
            should_stop = True
        else:
            feedback = "The answer is good but could use more detail. Continue improving."
            should_stop = False
        
        return AgentResult(
            output=feedback,
            feedback=feedback,
            metadata={
                "should_stop": should_stop,
                "evaluation_count": self.evaluation_count,
                "reasoning_summary": f"Evaluation {self.evaluation_count}",
            },
            tokens_used=len(feedback.split()),
        )


class MockRefinerAgent(AbstractAgent):
    """Mock refiner that provides basic refinement prompts."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split())
        super().__init__(role="refiner", provider=provider)
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Refine the prompt based on feedback."""
        refined_prompt = f"{context.prompt}\n\nPlease provide a more detailed and complete answer based on the feedback: {context.feedback}"
        
        return AgentResult(
            output=refined_prompt,
            metadata={"original_prompt": context.prompt},
            tokens_used=len(refined_prompt.split()),
        )


@pytest.fixture
def mock_agents():
    """Create mock agents for testing."""
    generator = MockIncompleteGeneratorAgent()
    evaluator = MockEagerEvaluatorAgent()
    refiner = MockRefinerAgent()
    return generator, evaluator, refiner


@pytest.mark.xfail(reason="SelfEvolve incorrectly claims convergence on incomplete answers - fix needed")
@pytest.mark.asyncio
async def test_premature_convergence_simple_math(mock_agents):
    """
    Test that SelfEvolve should NOT converge when generator produces incomplete answers.
    
    This test uses a simple math problem "prove 1+1=2" where the generator
    deliberately produces obviously incomplete answers, but the evaluator
    incorrectly signals convergence.
    """
    generator, evaluator, refiner = mock_agents
    
    # Create SelfEvolve engine with max_iters=3
    engine = SelfEvolve(
        generator=generator,
        evaluator=evaluator,
        refiner=refiner,
        max_iters=3
    )
    
    # Create a simple problem
    problem = Problem(
        question="Prove that 1+1=2",
        context="Use mathematical rigor and formal proof techniques",
        constraints="Provide a complete proof with all steps shown"
    )
    
    # Run the engine
    solution = await engine.solve(problem)
    
    # The solution should NOT be marked as converged because the answers are incomplete
    assert solution.metadata["converged"] is False, \
        "SelfEvolve should not converge when generator produces incomplete answers"
    
    # The stop reason should NOT be evaluator_stop since the answer is incomplete
    assert solution.metadata["stop_reason"] != "evaluator_stop", \
        f"Stop reason should not be 'evaluator_stop' for incomplete answers, got: {solution.metadata['stop_reason']}"
    
    # Should have run all 3 iterations since it didn't truly converge
    assert solution.iterations == 3, \
        f"Should have run all 3 iterations, but only ran {solution.iterations}"
    
    # The output should be flagged as potentially incomplete
    # (This is an additional check we might want to implement)
    incomplete_indicators = ["partial", "incomplete", "requires more", "several steps", "more work"]
    output_lower = solution.output.lower()
    has_incomplete_indicator = any(indicator in output_lower for indicator in incomplete_indicators)
    
    assert has_incomplete_indicator, \
        f"Solution output appears complete but should be incomplete: '{solution.output[:100]}...'"


@pytest.mark.xfail(reason="SelfEvolve incorrectly claims convergence on incomplete answers - fix needed")
@pytest.mark.asyncio
async def test_premature_convergence_complex_problem(mock_agents):
    """
    Test premature convergence on a more complex problem.
    
    This tests that SelfEvolve doesn't incorrectly claim convergence
    when dealing with multi-step problems that require thorough solutions.
    """
    generator, evaluator, refiner = mock_agents
    
    # Create SelfEvolve engine
    engine = SelfEvolve(
        generator=generator,
        evaluator=evaluator,
        refiner=refiner,
        max_iters=3
    )
    
    # Create a complex problem that requires multiple steps
    problem = Problem(
        question="Explain the process of photosynthesis and its role in the carbon cycle",
        context="Provide a comprehensive explanation suitable for a biology student",
        constraints="Include chemical equations, key steps, and environmental impact"
    )
    
    # Run the engine
    solution = await engine.solve(problem)
    
    # Assertions to catch premature convergence
    assert solution.metadata["converged"] is False, \
        "Complex problems should not converge with incomplete answers"
    
    assert solution.metadata["stop_reason"] != "evaluator_stop", \
        f"Stop reason should not be 'evaluator_stop' for incomplete complex answers, got: {solution.metadata['stop_reason']}"
    
    # Should complete all iterations
    assert solution.iterations == 3, \
        f"Should have completed all 3 iterations, got {solution.iterations}"


@pytest.mark.xfail(reason="SelfEvolve incorrectly claims convergence on incomplete answers - fix needed")
@pytest.mark.asyncio
async def test_stop_reason_consistency():
    """
    Test that stop_reason is consistent with convergence status.
    
    When converged=False, stop_reason should never be 'evaluator_stop'.
    """
    generator = MockIncompleteGeneratorAgent()
    evaluator = MockEagerEvaluatorAgent()
    refiner = MockRefinerAgent()
    
    engine = SelfEvolve(
        generator=generator,
        evaluator=evaluator,
        refiner=refiner,
        max_iters=3
    )
    
    problem = Problem(
        question="What is the meaning of life?",
        context="Provide a philosophical perspective"
    )
    
    solution = await engine.solve(problem)
    
    # Test consistency between converged flag and stop_reason
    if not solution.metadata["converged"]:
        assert solution.metadata["stop_reason"] != "evaluator_stop", \
            "When converged=False, stop_reason should not be 'evaluator_stop'"
    
    if solution.metadata["stop_reason"] == "evaluator_stop":
        assert solution.metadata["converged"] is True, \
            "When stop_reason='evaluator_stop', converged should be True"


@pytest.mark.xfail(reason="SelfEvolve needs better incomplete answer detection - fix needed")
@pytest.mark.asyncio
async def test_incomplete_answer_detection():
    """
    Test that SelfEvolve can detect obviously incomplete answers.
    
    This test checks if the engine has mechanisms to detect when
    generator outputs are clearly incomplete or truncated.
    """
    class VeryIncompleteGeneratorAgent(MockIncompleteGeneratorAgent):
        async def run(self, context: AgentContext) -> AgentResult:
            # Generate obviously incomplete/truncated answers
            incomplete_answers = [
                "The answer is...",
                "To solve this problem, we need to",
                "Step 1: Start with basic principles",
                "The solution involves multiple steps including"
            ]
            
            self.call_count += 1
            answer = incomplete_answers[(self.call_count - 1) % len(incomplete_answers)]
            
            return AgentResult(
                output=answer,
                metadata={"temperature": 0.7},
                tokens_used=len(answer.split()),
            )
    
    generator = VeryIncompleteGeneratorAgent()
    evaluator = MockEagerEvaluatorAgent()
    refiner = MockRefinerAgent()
    
    engine = SelfEvolve(
        generator=generator,
        evaluator=evaluator,
        refiner=refiner,
        max_iters=3
    )
    
    problem = Problem(question="Solve x² + 5x + 6 = 0")
    
    solution = await engine.solve(problem)
    
    # The engine should recognize these as incomplete and not converge
    assert solution.metadata["converged"] is False, \
        f"Engine should detect incomplete answers and not converge. Output: '{solution.output}'"
    
    # Should have used all available iterations trying to improve
    assert solution.iterations == 3, \
        f"Should have used all iterations to try to improve incomplete answers, got {solution.iterations}"


@pytest.mark.asyncio
async def test_proper_convergence_with_complete_answers():
    """
    Test that SelfEvolve correctly converges when answers are actually complete.
    
    This test ensures that the fix doesn't break legitimate convergence.
    """
    class CompleteGeneratorAgent(AbstractAgent):
        def __init__(self):
            provider = MagicMock()
            provider.count_tokens = lambda x: len(x.split())
            super().__init__(role="generator", provider=provider)
        
        async def run(self, context: AgentContext) -> AgentResult:
            # Provide a complete, detailed answer
            complete_answer = """
            To prove that 1+1=2, we use the Peano axioms and the definition of addition:
            
            1. Start with Peano axioms where 0 is the first natural number
            2. Define 1 as the successor of 0: 1 = S(0)
            3. Define 2 as the successor of 1: 2 = S(1) = S(S(0))
            4. Addition is defined recursively: a + S(b) = S(a + b) and a + 0 = a
            5. Therefore: 1 + 1 = 1 + S(0) = S(1 + 0) = S(1) = 2
            
            This completes the formal proof that 1+1=2.
            """
            
            return AgentResult(
                output=complete_answer.strip(),
                metadata={"temperature": 0.7},
                tokens_used=len(complete_answer.split()),
            )
    
    class AccurateEvaluatorAgent(AbstractAgent):
        def __init__(self):
            provider = MagicMock()
            provider.count_tokens = lambda x: len(x.split())
            super().__init__(role="evaluator", provider=provider)
        
        async def run(self, context: AgentContext) -> AgentResult:
            # Properly evaluate complete answers
            if "Peano axioms" in context.output and "completes the formal proof" in context.output:
                feedback = "Excellent complete proof with all necessary steps shown. <stop>"
                should_stop = True
            else:
                feedback = "The answer needs more detail and formal structure."
                should_stop = False
            
            return AgentResult(
                output=feedback,
                feedback=feedback,
                metadata={"should_stop": should_stop},
                tokens_used=len(feedback.split()),
            )
    
    generator = CompleteGeneratorAgent()
    evaluator = AccurateEvaluatorAgent()
    refiner = MockRefinerAgent()
    
    engine = SelfEvolve(
        generator=generator,
        evaluator=evaluator,  
        refiner=refiner,
        max_iters=3
    )
    
    problem = Problem(question="Prove that 1+1=2")
    solution = await engine.solve(problem)
    
    # This should properly converge since the answer is complete
    assert solution.metadata["converged"] is True, \
        "Should converge when answers are actually complete and well-structured"
    
    assert solution.metadata["stop_reason"] == "evaluator_stop", \
        f"Should stop due to evaluator when answer is complete, got: {solution.metadata['stop_reason']}"
    
    # Should not need all iterations since it converged early
    assert solution.iterations < 3, \
        f"Should converge in fewer than 3 iterations when answer is complete, got {solution.iterations}"


if __name__ == "__main__":
    # Allow running this test file directly for debugging
    pytest.main([__file__, "-v"])
