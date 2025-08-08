"""
Unit tests for improved continuation fallback strategy.

Tests that the new continuation fallback strategy works correctly:
• When continuation is requested (evolution_history not empty) and current iteration cannot yield a valid output after retries, does NOT raise hard exception if allow_continuation_fallback=True.
• Instead, retrieves the latest valid iteration from evolution_history and returns it as final answer.
• Marks should_stop = True and metadata.fallback_used = True with diagnostic message.
• Provides option flag allow_continuation_fallback (default True) to toggle this behaviour.

Test Coverage:
1. test_continuation_fallback_returns_valid_iteration - Main test that fallback works
2. test_continuation_fallback_with_diagnostic_message - Verifies diagnostic message
3. test_continuation_fallback_disabled_raises_exception - Tests when fallback is disabled
4. test_continuation_fallback_prefers_most_recent_valid - Tests fallback selection strategy
5. test_continuation_fallback_metadata_correct - Tests metadata is set correctly
"""
import pytest
from unittest.mock import MagicMock
import logging

from app.core.engine.self_evolve import Problem, SelfEvolve, Solution
from app.core.agents.base import AbstractAgent, AgentContext, AgentResult


class MockValidOutputGeneratorAgent(AbstractAgent):
    """Mock generator that produces valid outputs."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split()) if x.strip() else 0
        super().__init__(role="generator", provider=provider)
        self.call_count = 0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Generate valid outputs."""
        self.call_count += 1
        
        # Generate a valid output (more than 10 words)
        output = f"This is a comprehensive and detailed response that meets all validity criteria. Call number: {self.call_count}"
        
        return AgentResult(
            output=output,
            metadata={
                "temperature": 0.7,
                "reasoning_summary": f"Valid output generation attempt {self.call_count}",
            },
            tokens_used=len(output.split()),
        )


class MockInvalidOutputGeneratorAgent(AbstractAgent):
    """Mock generator that only produces invalid outputs."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split()) if x.strip() else 0
        super().__init__(role="generator", provider=provider)
        self.call_count = 0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Generate only invalid outputs."""
        self.call_count += 1
        
        # Cycle through invalid outputs
        invalid_outputs = ["", "   ", "\n\t  \n", "..."]
        output = invalid_outputs[(self.call_count - 1) % len(invalid_outputs)]
        
        return AgentResult(
            output=output,
            metadata={
                "temperature": 0.7,
                "reasoning_summary": f"Invalid output attempt {self.call_count}",
            },
            tokens_used=0,
        )


class MockBasicEvaluatorAgent(AbstractAgent):
    """Mock evaluator that provides basic evaluation feedback."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split())
        super().__init__(role="evaluator", provider=provider)
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Evaluate answers with basic feedback."""
        feedback = "The answer needs improvement."
        
        return AgentResult(
            output=feedback,
            feedback=feedback,
            metadata={
                "should_stop": False,
                "reasoning_summary": "Basic evaluation feedback",
            },
            tokens_used=len(feedback.split()),
        )


class MockBasicRefinerAgent(AbstractAgent):
    """Mock refiner that provides basic refinement prompts."""
    
    def __init__(self):
        provider = MagicMock()
        provider.count_tokens = lambda x: len(x.split())
        super().__init__(role="refiner", provider=provider)
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Refine the prompt based on feedback."""
        refined_prompt = f"{context.prompt}\n\nPlease provide a more detailed answer."
        
        return AgentResult(
            output=refined_prompt,
            metadata={"original_prompt": context.prompt},
            tokens_used=len(refined_prompt.split()),
        )


@pytest.fixture
def valid_generator():
    """Create a mock generator that produces valid outputs."""
    return MockValidOutputGeneratorAgent()


@pytest.fixture
def invalid_generator():
    """Create a mock generator that produces invalid outputs."""
    return MockInvalidOutputGeneratorAgent()


@pytest.fixture
def mock_evaluator():
    """Create a mock evaluator."""
    return MockBasicEvaluatorAgent()


@pytest.fixture
def mock_refiner():
    """Create a mock refiner."""
    return MockBasicRefinerAgent()


class TestContinuationFallbackStrategy:
    """Test cases for the improved continuation fallback strategy."""

    @pytest.mark.asyncio
    async def test_continuation_fallback_returns_valid_iteration(self, invalid_generator, mock_evaluator, mock_refiner):
        """
        Test that continuation fallback returns valid iteration instead of raising exception.
        
        This is the main test case that verifies the improved continuation fallback strategy.
        """
        # Create SelfEvolve engine with fallback enabled (default)
        engine = SelfEvolve(
            generator=invalid_generator,
            evaluator=mock_evaluator,
            refiner=mock_refiner,
            max_iters=3,
            allow_continuation_fallback=True
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
                "output": "The capital of France is Paris, which is located in the north-central part of the country.",  # Valid output
                "feedback": "Good answer, but could be more detailed.",
                "should_stop": False,
                "metadata": {
                    "generator": {
                        "temperature": 0.7,
                        "reasoning_summary": "Initial valid response",
                        "tokens_used": 15
                    },
                    "evaluator": {
                        "should_stop": False,
                        "reasoning_summary": "Valid output evaluation",
                        "tokens_used": 10
                    }
                },
                "refined_prompt": "What is the capital of France?\n\nPlease provide a more detailed answer."
            }
        ]
        
        # This should NOT raise an exception but return the fallback iteration
        solution = await engine.resume_solve(problem, evolution_history, start_iteration=2)
        
        # Verify that we got a valid solution using fallback
        assert isinstance(solution, Solution)
        assert solution.output == "The capital of France is Paris, which is located in the north-central part of the country."
        assert solution.metadata["fallback_used"] is True
        assert solution.metadata["stop_reason"] == "fallback_to_best"
        assert "fallback_diagnostic" in solution.metadata
        
        # Verify that the generator was called (attempted to generate but failed)
        assert invalid_generator.call_count > 0

    @pytest.mark.asyncio
    async def test_continuation_fallback_with_diagnostic_message(self, invalid_generator, mock_evaluator, mock_refiner):
        """
        Test that fallback includes proper diagnostic message.
        """
        engine = SelfEvolve(
            generator=invalid_generator,
            evaluator=mock_evaluator,
            refiner=mock_refiner,
            max_iters=2,
            allow_continuation_fallback=True
        )
        
        problem = Problem(question="Explain photosynthesis")
        
        evolution_history = [
            {
                "iteration": 1,
                "prompt": "Explain photosynthesis",
                "output": "Photosynthesis is the process by which plants convert sunlight into energy using chlorophyll and carbon dioxide.",
                "feedback": "Good explanation but needs more detail.",
                "should_stop": False,
                "metadata": {
                    "generator": {"tokens_used": 20},
                    "evaluator": {"should_stop": False, "tokens_used": 8}
                }
            }
        ]
        
        solution = await engine.resume_solve(problem, evolution_history, start_iteration=2)
        
        # Verify diagnostic message
        assert "fallback_diagnostic" in solution.metadata
        diagnostic = solution.metadata["fallback_diagnostic"]
        assert "Continuation fallback applied" in diagnostic
        assert "iteration 1" in diagnostic
        assert "downstream consumers receive a valid response" in diagnostic

    @pytest.mark.asyncio
    async def test_continuation_fallback_disabled_raises_exception(self, invalid_generator, mock_evaluator, mock_refiner):
        """
        Test that when allow_continuation_fallback=False, exception is still raised.
        """
        # Create SelfEvolve engine with fallback disabled
        engine = SelfEvolve(
            generator=invalid_generator,
            evaluator=mock_evaluator,
            refiner=mock_refiner,
            max_iters=2,
            allow_continuation_fallback=False  # Disable fallback
        )
        
        problem = Problem(question="What is machine learning?")
        
        evolution_history = [
            {
                "iteration": 1,
                "prompt": "What is machine learning?",
                "output": "Machine learning is a subset of artificial intelligence that enables computers to learn patterns from data.",
                "feedback": "Good answer but could be expanded.",
                "should_stop": False,
                "metadata": {
                    "generator": {"tokens_used": 18},
                    "evaluator": {"should_stop": False, "tokens_used": 7}
                }
            }
        ]
        
        # This should raise an exception because fallback is disabled
        with pytest.raises(Exception) as exc_info:
            await engine.resume_solve(problem, evolution_history, start_iteration=2)
        
        assert "continuation fallback disabled" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_continuation_fallback_prefers_most_recent_valid(self, invalid_generator, mock_evaluator, mock_refiner):
        """
        Test that fallback strategy prefers the most recent valid iteration.
        """
        engine = SelfEvolve(
            generator=invalid_generator,
            evaluator=mock_evaluator,
            refiner=mock_refiner,
            max_iters=3,
            allow_continuation_fallback=True
        )
        
        problem = Problem(question="Define artificial intelligence")
        
        # Evolution history with multiple valid iterations
        evolution_history = [
            {
                "iteration": 1,
                "prompt": "Define artificial intelligence",
                "output": "Artificial intelligence is computer systems that can perform tasks requiring human intelligence like learning and reasoning.",  # Valid but older
                "feedback": "Good start, needs more examples.",
                "should_stop": False,
                "metadata": {
                    "generator": {"tokens_used": 20},
                    "evaluator": {"should_stop": False, "tokens_used": 6}
                }
            },
            {
                "iteration": 2,
                "prompt": "Define artificial intelligence with more examples",
                "output": "AI includes machine learning, natural language processing, computer vision, and robotics systems that simulate human cognitive abilities.",  # Valid and more recent
                "feedback": "Excellent comprehensive answer.",
                "should_stop": False,
                "metadata": {
                    "generator": {"tokens_used": 22},
                    "evaluator": {"should_stop": False, "tokens_used": 5}
                }
            }
        ]
        
        solution = await engine.resume_solve(problem, evolution_history, start_iteration=3)
        
        # Should use the most recent valid iteration (iteration 2)
        assert solution.output == "AI includes machine learning, natural language processing, computer vision, and robotics systems that simulate human cognitive abilities."
        assert solution.metadata["fallback_used"] is True
        assert "iteration 2" in solution.metadata["fallback_diagnostic"]

    @pytest.mark.asyncio
    async def test_continuation_fallback_metadata_correct(self, invalid_generator, mock_evaluator, mock_refiner):
        """
        Test that all metadata fields are set correctly when fallback is used.
        """
        engine = SelfEvolve(
            generator=invalid_generator,
            evaluator=mock_evaluator,
            refiner=mock_refiner,
            max_iters=2,
            allow_continuation_fallback=True
        )
        
        problem = Problem(question="Solve 2+2")
        
        evolution_history = [
            {
                "iteration": 1,
                "prompt": "Solve 2+2",
                "output": "The answer to 2+2 is 4, which is a basic arithmetic operation in mathematics.",
                "feedback": "Correct answer with good explanation.",
                "should_stop": False,
                "metadata": {
                    "generator": {"tokens_used": 15},
                    "evaluator": {"should_stop": False, "tokens_used": 6}
                }
            }
        ]
        
        solution = await engine.resume_solve(problem, evolution_history, start_iteration=2)
        
        # Verify all metadata fields
        assert solution.metadata["fallback_used"] is True
        assert solution.metadata["stop_reason"] == "fallback_to_best"
        assert "fallback_diagnostic" in solution.metadata
        assert solution.metadata["converged"] is True  # Should be marked as converged due to fallback stop
        
        # Verify solution structure
        assert len(solution.evolution_history) == 1  # Original history preserved
        assert solution.iterations == 1
        assert solution.total_tokens > 0  # Should include tokens from history

    @pytest.mark.asyncio
    async def test_no_fallback_when_valid_output_generated(self, valid_generator, mock_evaluator, mock_refiner):
        """
        Test that fallback is not triggered when current iteration produces valid output.
        """
        engine = SelfEvolve(
            generator=valid_generator,
            evaluator=mock_evaluator,
            refiner=mock_refiner,
            max_iters=2,
            allow_continuation_fallback=True
        )
        
        problem = Problem(question="What is Python?")
        
        evolution_history = [
            {
                "iteration": 1,
                "prompt": "What is Python?",
                "output": "Python is a high-level programming language known for its readability and versatility in software development.",
                "feedback": "Good answer but could mention more use cases.",
                "should_stop": False,
                "metadata": {
                    "generator": {"tokens_used": 18},
                    "evaluator": {"should_stop": False, "tokens_used": 8}
                }
            }
        ]
        
        solution = await engine.resume_solve(problem, evolution_history, start_iteration=2)
        
        # Should NOT use fallback since valid output was generated
        assert solution.metadata["fallback_used"] is False
        assert solution.metadata["stop_reason"] in ["evaluator_stop", "max_iterations"]
        assert "fallback_diagnostic" not in solution.metadata
        
        # Should have new iteration in history
        assert len(solution.evolution_history) == 2
        assert solution.iterations == 2


if __name__ == "__main__":
    # Allow running the test directly for debugging
    pytest.main([__file__, "-v", "-s"])
