#!/usr/bin/env python3
"""
Investigation script to capture raw evaluation_prompt and model replies
to understand why '<stop>' appears in LLM outputs, triggering premature convergence.
"""
import asyncio
import logging
import os
from unittest.mock import MagicMock

from app.core.agents.evaluator import EvaluatorAgent
from app.core.agents.base import AgentContext
from app.core.agents.prompts.evaluate_prompt import get_evaluator_system_prompt, build_evaluation_prompt


# Configure logging to capture detailed information
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MockProvider:
    """Mock provider that simulates LLM responses containing <stop> token"""
    
    def __init__(self):
        self.call_count = 0
    
    def count_tokens(self, text: str) -> int:
        return len(text.split())
    
    async def complete_with_functions(self, prompt: str, functions, system_prompt: str, temperature: float):
        """Simulate LLM responses that inappropriately echo the system prompt"""
        self.call_count += 1
        
        # Simulate the hypothesized issue: LLM echoes parts of the long system prompt
        # which contains literal "<stop>" text, triggering the naive substring check
        
        if self.call_count == 1:
            # First evaluation - should not stop
            return """
**Strengths:**
- The answer attempts to address the mathematical proof of 1+1=2
- It correctly identifies the need for basic arithmetic principles

**Areas for Improvement:**
- The answer is incomplete and lacks the formal proof structure
- No specific mathematical steps are provided
- The reasoning is incomplete and requires substantial development

**Mathematical Accuracy Review:**
- No calculations or formulas are presented to verify
- The answer lacks the rigor expected for a mathematical proof

**Overall Assessment:**
The solution is clearly incomplete. As instructed in your guidelines, I must be extremely harsh and push for perfection. The current answer fails to provide any concrete proof steps. Do NOT include <stop> until the proof is complete and rigorous.

The answer needs significant improvement before it can be considered satisfactory.
"""
        else:
            # Second evaluation - this is where the issue occurs
            # The LLM inappropriately echoes the system prompt guidelines, including literal "<stop>"
            return """
**Strengths:**
- Shows some understanding of Peano axioms
- Attempts to structure a formal approach

**Areas for Improvement:**
- Still incomplete with "requires several steps..." ending
- Missing the actual proof steps and conclusion

**Mathematical Accuracy Review:**
- The approach is correct but execution is incomplete

**Overall Assessment:**
Following the evaluation guidelines provided, I note that the instruction states: "You should only include `<stop>` in your assessment if the solution is absolutely flawless, rigorous, and complete." However, this solution still contains incomplete reasoning and lacks the final steps. 

But following the broader guideline about stopping when the solution meets the criteria mentioned in your prompt where it says "Do NOT include <stop> if the solution contains any computational errors" - wait, I should clarify that while there are no computational errors per se, the solution is incomplete.

Actually, reviewing your instructions about when to include <stop>, you mentioned several criteria. Let me be thorough in my assessment... <stop>

[The model continues but the <stop> token has already been detected]
"""
    
    async def complete(self, prompt: str, system_prompt: str, temperature: float):
        # Fallback method
        return await self.complete_with_functions(prompt, [], system_prompt, temperature)


async def investigate_stop_token_issue():
    """Main investigation function to reproduce the <stop> token issue"""
    
    print("=== INVESTIGATING <stop> TOKEN ISSUE ===\n")
    
    # Create a mock provider that simulates the problematic LLM behavior
    provider = MockProvider()
    
    # Create the evaluator agent with the real system prompt
    evaluator = EvaluatorAgent(provider=provider)
    
    print("1. SYSTEM PROMPT ANALYSIS")
    print("=" * 50)
    system_prompt = get_evaluator_system_prompt()
    print(f"System prompt contains '<stop>' literal text: {'`<stop>`' in system_prompt}")
    print(f"System prompt length: {len(system_prompt)} characters")
    
    # Count occurrences of <stop> in system prompt
    stop_occurrences = system_prompt.count('<stop>')
    print(f"Number of '<stop>' occurrences in system prompt: {stop_occurrences}")
    
    if stop_occurrences > 0:
        print("\nFound <stop> occurrences in system prompt:")
        lines = system_prompt.split('\n')
        for i, line in enumerate(lines, 1):
            if '<stop>' in line:
                print(f"  Line {i}: {line.strip()}")
    
    print("\n2. EVALUATION PROMPT CONSTRUCTION")
    print("=" * 50)
    
    # Create test inputs that simulate incomplete answers
    question = "Prove that 1+1=2"
    incomplete_answer = "Starting from Peano axioms, we can define addition. The proof requires several steps..."
    constraints = "Provide a complete proof with all steps shown"
    
    evaluation_prompt = build_evaluation_prompt(
        question=question,
        answer=incomplete_answer,
        constraints=constraints
    )
    
    print(f"Evaluation prompt contains '<stop>' literal text: {'<stop>' in evaluation_prompt}")
    stop_occurrences_eval = evaluation_prompt.count('<stop>')
    print(f"Number of '<stop>' occurrences in evaluation prompt: {stop_occurrences_eval}")
    
    print(f"Evaluation prompt length: {len(evaluation_prompt)} characters")
    
    print("\n3. SIMULATING EVALUATOR RUNS")
    print("=" * 50)
    
    # First evaluation
    context1 = AgentContext(
        prompt=question,
        output=incomplete_answer,
        additional_context={
            "constraints": constraints
        }
    )
    
    print("First evaluation:")
    result1 = await evaluator.run(context1)
    print(f"  Should stop: {result1.metadata.get('should_stop', False)}")
    print(f"  Contains <stop>: {'<stop>' in result1.output}")
    print(f"  Feedback length: {len(result1.feedback)} characters")
    
    # Second evaluation with a different incomplete answer
    incomplete_answer2 = "The proof involves understanding that 1 is the successor of 0, and addition..."
    context2 = AgentContext(
        prompt=question,
        output=incomplete_answer2,
        additional_context={
            "constraints": constraints
        }
    )
    
    print("\nSecond evaluation:")
    result2 = await evaluator.run(context2)
    print(f"  Should stop: {result2.metadata.get('should_stop', False)}")
    print(f"  Contains <stop>: {'<stop>' in result2.output}")
    print(f"  Feedback length: {len(result2.feedback)} characters")
    
    print("\n4. ANALYSIS OF THE ISSUE")
    print("=" * 50)
    
    print("Issue Summary:")
    print("- The evaluation system prompt contains literal '<stop>' text in instructions")
    print("- LLMs may echo or reference these instructions in their responses")
    print("- The current detection logic uses naive substring checking: '<stop>' in evaluation")
    print("- This causes false positives when LLMs mention the '<stop>' token in guidelines")
    
    print("\n5. EVIDENCE FROM MOCK RESPONSES")
    print("=" * 50)
    
    if '<stop>' in result2.output:
        print("CONFIRMED: Second evaluation contains <stop> token")
        print("This demonstrates the hypothesis:")
        print("1. LLM references the evaluation guidelines")
        print("2. Guidelines contain literal '<stop>' text")
        print("3. LLM echoes 'Do NOT include <stop> unless...' type statements")
        print("4. Naive substring check detects '<stop>' and triggers premature convergence")
        
        # Show the context around <stop> in the response
        lines = result2.output.split('\n')
        for line_num, line in enumerate(lines, 1):
            if '<stop>' in line:
                print(f"\nProblematic line {line_num}: {line.strip()}")
                # Show context
                start = max(0, line_num - 3)
                end = min(len(lines), line_num + 2)
                print("Context:")
                for i in range(start, end):
                    prefix = ">>> " if i == line_num - 1 else "    "
                    print(f"{prefix}{lines[i]}")
    
    print("\n6. RECOMMENDED SOLUTIONS")
    print("=" * 50)
    print("1. Improve <stop> detection logic:")
    print("   - Instead of naive substring check, use pattern matching")
    print("   - Look for '<stop>' at end of response or on its own line")
    print("   - Exclude cases where <stop> appears in quoted guidelines")
    print("2. Modify system prompt to avoid literal '<stop>' in instructions")
    print("3. Add validation to ensure <stop> is intentional, not incidental")


if __name__ == "__main__":
    asyncio.run(investigate_stop_token_issue())
