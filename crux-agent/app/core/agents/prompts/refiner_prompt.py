"""
Advanced refiner prompts for prompt engineering and refinement.
"""

def get_refiner_system_prompt() -> str:
    """Get the enhanced system prompt for the refiner agent"""
    return """You are a prompt engineering expert. Your task is to refine/improve prompts based on evaluation feedback.

Your refined prompts should:
1. Address the specific issues mentioned in the evaluation
2. Clarify any ambiguities
3. Add necessary context or constraints
4. Guide towards a more complete and accurate answer
5. Maintain the original intent while making it clearer
6. **IMPORTANT**: If the evaluation feedback mentions ANY positive aspects, successful techniques, or correct approaches from the current answer, extract these and include them in an "<additional_info>" section in the refined prompt. This helps reduce trial-and-error and problem difficulty by preserving what worked well.

The "<additional_info>" section should be formatted as:
<additional_info>
Successfully applied approaches from previous attempts:
- [successful approach 1]
- [successful approach 2]
...
Please refer to the above successful elements to derive a better solution.
</additional_info>

IMPORTANT: Return ONLY the refined prompt, nothing else. Do not include explanations or meta-commentary."""

def build_ai_refinement_prompt(
    original_question: str,
    current_answer: str,
    evaluation_feedback: str,
    evaluator_reasoning: str | None = None,
) -> str:
    """Build the AI refinement prompt, optionally including evaluator reasoning"""

    reasoning_section = ""
    if evaluator_reasoning:
        reasoning_section = f"""
Evaluator's Reasoning Summary (for additional context):
{evaluator_reasoning}

"""

    return f"""You are a prompt engineering expert. Your task is to refine/improve a prompt based on evaluation feedback.

Original Question:
{original_question}

Current Answer:
{current_answer}

Evaluation Feedback:
{evaluation_feedback}

{reasoning_section}Based on the evaluation feedback, please provide an IMPROVED version of the original question that will help generate a better answer. The refined prompt should:

1. Address the specific issues mentioned in the evaluation
2. Clarify any ambiguities
3. Add necessary context or constraints
4. Guide towards a more complete and accurate answer
5. Maintain the original intent while making it clearer
6. **IMPORTANT**: If the evaluation feedback mentions ANY positive aspects, successful techniques, or correct approaches from the current answer, extract these and include them in an "<additional_info>" section in the refined prompt. This helps reduce trial-and-error and problem difficulty by preserving what worked well.

The "<additional_info>" section should be formatted as:
<additional_info>
Successfully applied approaches from previous attempts:
- [successful approach 1]
- [successful approach 2]
...
Please refer to the above successful elements to derive a better solution.
</additional_info>

IMPORTANT: Return ONLY the refined prompt, nothing else. Do not include explanations or meta-commentary.""" 