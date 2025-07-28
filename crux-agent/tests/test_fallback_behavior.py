"""
Unit test for SelfEvolve engine fallback behavior.

Tests that when generator.run succeeds once then always returns invalid output,
the engine falls back to the best (successful) iteration.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from app.core.engine.self_evolve import SelfEvolve, Problem, Solution
from app.core.agents.base import AgentResult, AgentContext


class MockAgent:
    """Mock agent for testing."""
    
    def __init__(self, role: str):
        self.role = role
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Mock run method - will be overridden by test mocks."""
        pass


@pytest.mark.asyncio
async def test_fallback_to_best_after_generator_failure():
    """
    Test that engine.solve() falls back to best iteration when generator
    succeeds once then always returns invalid output.
    """
    # Create mock agents
    mock_generator = MockAgent("generator")
    mock_evaluator = MockAgent("evaluator") 
    mock_refiner = MockAgent("refiner")
    
    # The successful output from the first iteration
    successful_output = "This is a valid and complete answer to the problem with sufficient detail."
    
    # Mock generator behavior: succeed once, then return invalid output
    call_count = 0
    async def mock_generator_run(context: AgentContext) -> AgentResult:
        nonlocal call_count
        call_count += 1
        
        if call_count == 1:
            # First call succeeds with valid output
            return AgentResult(
                output=successful_output,
                metadata={"reasoning_summary": "First attempt successful"},
                tokens_used=100
            )
        else:
            # Subsequent calls return invalid output (too short)
            return AgentResult(
                output="...",  # Invalid - too short and placeholder
                metadata={"reasoning_summary": "Failed attempt"},
                tokens_used=50
            )
    
    # Mock evaluator to not trigger early stop
    async def mock_evaluator_run(context: AgentContext) -> AgentResult:
        return AgentResult(
            output="",
            feedback="Continue improving",
            metadata={"should_stop": False, "reasoning_summary": "Needs improvement"},
            tokens_used=75
        )
    
    # Mock refiner
    async def mock_refiner_run(context: AgentContext) -> AgentResult:
        return AgentResult(
            output="Refined prompt for next iteration",
            metadata={"reasoning_summary": "Prompt refined"},
            tokens_used=25
        )
    
    # Apply mocks
    mock_generator.run = AsyncMock(side_effect=mock_generator_run)
    mock_evaluator.run = AsyncMock(side_effect=mock_evaluator_run)
    mock_refiner.run = AsyncMock(side_effect=mock_refiner_run)
    
    # Create SelfEvolve engine with multiple iterations to trigger fallback
    engine = SelfEvolve(
        generator=mock_generator,
        evaluator=mock_evaluator,
        refiner=mock_refiner,
        max_iters=3  # Allow multiple iterations to test fallback
    )
    
    # Create test problem
    problem = Problem(
        question="What is the solution to this test problem?",
        context="Test context",
        constraints="Test constraints"
    )
    
    # Run solve - should not raise exception despite invalid outputs after first success
    solution = await engine.solve(problem)
    
    # Assertions
    assert isinstance(solution, Solution)
    
    # Check that the solution metadata indicates fallback was used
    assert solution.metadata["stop_reason"] == "fallback_to_best"
    assert solution.metadata.get("fallback_used", False) == True
    
    # Check that the returned answer equals the only successful output
    assert solution.output == successful_output
    
    # Verify the generator was called multiple times (first success + retries)
    assert mock_generator.run.call_count > 1
    
    # Verify that we have at least one successful iteration in history
    assert len(solution.evolution_history) >= 1
    assert solution.evolution_history[0]["output"] == successful_output
    
    # Verify solution completed without exceptions (implicit - test passes)
    print(f"✅ Test passed: engine.solve() returned without exception")
    print(f"✅ Test passed: solution.metadata['stop_reason'] == 'fallback_to_best'")
    print(f"✅ Test passed: returned answer equals the successful output")
    print(f"✅ Generator called {mock_generator.run.call_count} times")
    print(f"✅ Solution iterations: {solution.iterations}")
    print(f"✅ Evolution history length: {len(solution.evolution_history)}")


if __name__ == "__main__":
    # Allow running the test directly
    import asyncio
    asyncio.run(test_fallback_to_best_after_generator_failure())
