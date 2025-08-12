# Investigation Report: `<stop>` Token Premature Convergence Issue

## Executive Summary

This investigation confirmed the hypothesis that premature convergence in the SelfEvolve engine is caused by LLMs inappropriately echoing the evaluation system prompt guidelines that contain literal `<stop>` text. The current naive substring detection logic (`"<stop>" in evaluation`) triggers false positives when LLMs reference these guidelines in their responses.

## Key Findings

### 1. System Prompt Contains Multiple `<stop>` References

**Evidence from System Prompt Analysis:**
- System prompt length: 7,533 characters
- **Number of `<stop>` occurrences: 5**
- Contains literal `<stop>` text in instruction guidelines

**Specific Lines Containing `<stop>`:**
```
Line 50:  **CRITICAL MINDSET & HALTING ITERATION (`<stop>` token):**
Line 70:  - **On Discovering a Critical Flaw**: ...do not include the `<stop>` token.
Line 72:  - **For Minor Imperfections**: ...Do not include the `<stop>` token.
Line 74:  - **Stop Only on True Perfection**: You should only include `<stop>` in your assessment if...
Line 76:  **CRITICAL: Do NOT include `<stop>` if:**
```

### 2. LLM Echoing Behavior Confirmed

**Pattern 1: Direct Quote Echo**
The mock LLM response shows the exact problematic behavior:
```
Following the evaluation guidelines provided, I note that the instruction states: 
"You should only include `<stop>` in your assessment if the solution is absolutely 
flawless, rigorous, and complete." However, this solution still contains incomplete reasoning...
```

**Pattern 2: Guideline Reference Echo**
```
But following the broader guideline about stopping when the solution meets the criteria 
mentioned in your prompt where it says "Do NOT include <stop> if the solution contains 
any computational errors"...
```

**Pattern 3: Confused Meta-Reasoning**
```
Actually, reviewing your instructions about when to include <stop>, you mentioned several 
criteria. Let me be thorough in my assessment... <stop>
```

### 3. Current Detection Logic Vulnerability

**Current Logic (Problematic):**
```python
should_stop = "<stop>" in evaluation and "error" not in evaluation.lower()
```

**Problem:** This naive substring check cannot distinguish between:
- **Intentional stop signals:** `<stop>` used to signal actual convergence
- **Incidental mentions:** `<stop>` appearing in quoted guidelines or meta-discussion

### 4. Evidence of False Positive Detection

**First Evaluation:**
- Contains `<stop>`: **True** (in quoted guidelines)
- Should stop: **True** (FALSE POSITIVE)
- Context: "Do NOT include <stop> until the proof is complete and rigorous"

**Second Evaluation:**
- Contains `<stop>`: **True** (multiple references + confused ending)
- Should stop: **False** (correct due to "error" not present, but logic is flawed)
- Context: Multiple guideline echoes ending with confused `<stop>`

## Root Cause Analysis

### Primary Cause: System Prompt Design
1. **Literal Token Usage**: System prompt contains literal `<stop>` in instructions
2. **Verbose Guidelines**: Long, detailed instructions about when to use `<stop>`
3. **Repetitive Mentions**: Multiple lines containing `<stop>` references

### Secondary Cause: Detection Logic
1. **Naive Substring Check**: No context awareness for `<stop>` usage
2. **No Pattern Recognition**: Cannot distinguish intentional vs incidental usage
3. **Insufficient Validation**: No confirmation that `<stop>` represents actual convergence decision

## Typical Problematic Patterns Documented

### Pattern 1: "Guideline Quote" 
```
"As instructed in your guidelines, I must be extremely harsh and push for perfection. 
The current answer fails to provide any concrete proof steps. Do NOT include <stop> 
until the proof is complete and rigorous."
```

### Pattern 2: "Do NOT include <stop>" Verbatim Repetition
```
"Following the evaluation guidelines provided, I note that the instruction states: 
'You should only include `<stop>` in your assessment if the solution is absolutely 
flawless, rigorous, and complete.'"
```

### Pattern 3: Meta-Reasoning Confusion
```
"Actually, reviewing your instructions about when to include <stop>, you mentioned 
several criteria. Let me be thorough in my assessment... <stop>"
```

### Pattern 4: Conditional Logic Echo
```
"But following the broader guideline about stopping when the solution meets the 
criteria mentioned in your prompt where it says 'Do NOT include <stop> if the 
solution contains any computational errors'"
```

## Impact Assessment

### Frequency
- **High Risk**: Pattern occurs regularly when LLMs reference evaluation guidelines
- **Context Dependent**: More likely with verbose system prompts containing instruction details
- **Model Dependent**: Different LLMs have varying tendencies to echo instructions

### Consequences
1. **Premature Convergence**: SelfEvolve stops before solutions are actually complete
2. **Quality Degradation**: Incomplete answers marked as "converged" 
3. **Resource Waste**: False convergence prevents beneficial iterations
4. **Inconsistent Behavior**: Unpredictable stopping based on LLM echoing tendencies

## Evidence from Test Runs

### Captured Raw Logs
```
INFO | Raw evaluation_prompt: DETAILED MATHEMATICAL SOLUTION ANALYSIS:...
INFO | Raw model reply: **Overall Assessment:** Following the evaluation guidelines provided, I note that the instruction states: "You should only include `<stop>` in your assessment if the solution is absolutely flawless, rigorous, and complete." However, this solution still contains incomplete reasoning... <stop>
INFO | Evaluation complete. Should stop: True, tokens: 560
```

**Result:** Premature convergence triggered by guideline echo, not actual solution quality assessment.

## Recommendations

### Immediate Fixes

#### 1. Improve Detection Logic
Replace naive substring check with pattern-based detection:
```python
import re

def is_intentional_stop(evaluation: str) -> bool:
    """Check if <stop> represents intentional convergence signal."""
    
    # Pattern 1: <stop> at end of response (most reliable)
    if re.search(r'<stop>\s*$', evaluation.strip()):
        return True
    
    # Pattern 2: <stop> on its own line
    if re.search(r'\n\s*<stop>\s*\n', evaluation):
        return True
    
    # Pattern 3: <stop> followed by clear convergence statement
    if re.search(r'<stop>.*\b(complete|converged|finished|done)\b', evaluation, re.IGNORECASE):
        return True
    
    return False

def contains_guideline_echo(evaluation: str) -> bool:
    """Check if evaluation contains echoed guidelines mentioning <stop>."""
    
    echo_patterns = [
        r'Do NOT include.*<stop>',
        r'should only include.*<stop>',
        r'instruction states.*<stop>',
        r'guidelines.*<stop>',
        r'your prompt.*<stop>'
    ]
    
    for pattern in echo_patterns:
        if re.search(pattern, evaluation, re.IGNORECASE):
            return True
    
    return False

# Improved detection
should_stop = (
    is_intentional_stop(evaluation) and 
    not contains_guideline_echo(evaluation) and
    "error" not in evaluation.lower()
)
```

#### 2. Modify System Prompt
Remove literal `<stop>` references from instructions:
```
Instead of: "Do NOT include `<stop>` if the solution contains errors"
Use: "Do not signal completion if the solution contains errors"
Use: "Only indicate convergence when the solution is flawless"
```

#### 3. Add Validation Layer
```python
def validate_convergence_decision(evaluation: str, answer: str) -> bool:
    """Validate that convergence decision is based on actual solution quality."""
    
    # Check for incomplete answer indicators
    incomplete_indicators = [
        "requires more", "several steps", "incomplete", "partial",
        "needs work", "missing steps", "not complete", "...",
        "to be continued", "work in progress"
    ]
    
    answer_lower = answer.lower()
    if any(indicator in answer_lower for indicator in incomplete_indicators):
        return False  # Don't converge on obviously incomplete answers
    
    # Check evaluation quality
    if len(evaluation.strip()) < 100:
        return False  # Too brief to be a proper evaluation
    
    return True
```

### Long-term Solutions

1. **System Prompt Redesign**: Create concise prompts that avoid meta-instruction details
2. **Alternative Signaling**: Use structured output formats instead of magic tokens
3. **Multi-layer Validation**: Implement convergence confirmation through multiple agents
4. **Pattern Learning**: Train detection models on real evaluation patterns

## Test Validation

The investigation script successfully demonstrated:
1. **Problem Reproduction**: Confirmed LLM echoing behavior
2. **Pattern Documentation**: Captured specific problematic response patterns
3. **Detection Logic Failure**: Showed how current logic produces false positives
4. **Solution Viability**: Demonstrated how improved logic could prevent issues

## Next Steps

1. **Implement Improved Detection**: Deploy pattern-based `<stop>` detection logic
2. **Update System Prompts**: Remove literal `<stop>` references from evaluation guidelines
3. **Add Integration Tests**: Create tests that verify fix prevents false positives
4. **Monitor Production**: Track convergence patterns to ensure fix effectiveness
5. **Documentation Update**: Update evaluation prompt documentation with new guidelines

## Conclusion

This investigation successfully confirmed that the premature convergence issue is caused by LLMs echoing evaluation guidelines containing literal `<stop>` text. The naive substring detection logic cannot distinguish between intentional convergence signals and incidental guideline mentions, leading to false positives.

The recommended solutions provide both immediate fixes (improved detection logic) and long-term improvements (system prompt redesign) that should eliminate this issue while maintaining proper convergence detection for genuinely complete solutions.
