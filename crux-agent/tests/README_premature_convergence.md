# Premature Convergence Tests

This directory contains tests designed to expose premature convergence issues in the SelfEvolve engine.

## Overview

The SelfEvolve engine is supposed to iteratively improve solutions through a generator-evaluator-refiner loop. However, there's a bug where the engine incorrectly claims convergence when the generator produces obviously incomplete answers.

## Test File: `test_premature_convergence.py`

This test file contains several test cases that demonstrate the premature convergence problem:

### Test Cases

1. **`test_premature_convergence_simple_math`** ❌ (XFAIL)
   - Tests a simple math problem: "Prove that 1+1=2"
   - Generator produces obviously incomplete answers like "To prove 1+1=2, we need to start with basic arithmetic principles..."
   - Evaluator incorrectly signals convergence after 2 iterations
   - **Expected**: Should NOT converge, should run all 3 iterations
   - **Actual**: Incorrectly converges after 2 iterations with `stop_reason="evaluator_stop"`

2. **`test_premature_convergence_complex_problem`** ❌ (XFAIL)
   - Tests a complex biology question about photosynthesis
   - Same pattern: incomplete answers incorrectly marked as complete
   - Demonstrates the issue affects various problem types

3. **`test_stop_reason_consistency`** ❌ (XFAIL)
   - Tests consistency between `converged` flag and `stop_reason` metadata
   - When `converged=False`, `stop_reason` should never be `"evaluator_stop"`
   - When `stop_reason="evaluator_stop"`, `converged` should be `True`

4. **`test_incomplete_answer_detection`** ❌ (XFAIL)
   - Tests the engine's ability to detect obviously incomplete/truncated answers
   - Uses answers like "The answer is..." or "Step 1: Start with basic principles"
   - Engine should recognize these as incomplete and continue iterating

5. **`test_proper_convergence_with_complete_answers`** ✅ (PASS)
   - **Control Test**: Ensures proper convergence behavior works correctly
   - Uses complete, detailed answers that should legitimately trigger convergence
   - This test passes to confirm the fix won't break legitimate convergence

## Running the Tests

### Run all premature convergence tests:
```bash
pypy -m pytest tests/test_premature_convergence.py -v
```

### Run a specific test:
```bash
pypy -m pytest tests/test_premature_convergence.py::test_premature_convergence_simple_math -v
```

### Run with detailed output to see the execution flow:
```bash
pypy -m pytest tests/test_premature_convergence.py::test_premature_convergence_simple_math -v -s
```

## Expected Test Results

Currently, these tests are marked with `@pytest.mark.xfail` because they expose existing bugs:

```
tests/test_premature_convergence.py::test_premature_convergence_simple_math XFAIL
tests/test_premature_convergence.py::test_premature_convergence_complex_problem XFAIL  
tests/test_premature_convergence.py::test_stop_reason_consistency XFAIL
tests/test_premature_convergence.py::test_incomplete_answer_detection XFAIL
tests/test_premature_convergence.py::test_proper_convergence_with_complete_answers PASSED
```

## The Bug

The logs from a failing test clearly show the problem:

```
Self-Evolve iteration 1/3
Iteration 1 complete. Should stop: False      # ✅ Correctly continues
Self-Evolve iteration 2/3  
Iteration 2 complete. Should stop: True       # ❌ Premature convergence!
Evaluator issued <stop> token after iteration 2. Solution is complete.  # ❌ Wrong!
Self-Evolve complete. Converged: True, Iterations: 2  # ❌ Should be False
```

The generator output at iteration 2 is: `"Starting from Peano axioms, we can define addition. The proof requires several steps..."` - clearly incomplete!

## What Should Happen After the Fix

Once the premature convergence bug is fixed:

1. The `@pytest.mark.xfail` decorators should be removed from the failing tests
2. All tests should pass
3. The engine should properly detect incomplete answers and continue iterating
4. `converged=False` and `stop_reason="max_iterations"` for incomplete answers
5. The control test should continue to pass (ensuring no regression)

## Integration with SelfEvolve.run()

The tests specifically follow the requirements:
- ✅ Call `SelfEvolve.run()` with `max_iters=3`
- ✅ Assert that `solution.metadata["converged"]` is `False` for incomplete answers  
- ✅ Assert that `stop_reason` ≠ `"evaluator_stop"` for incomplete answers
- ✅ Use simple multi-step problems that deliberately produce incomplete answers
- ✅ Tests are marked as `xfail` until the fix is implemented

## Mock Agent Design

The tests use carefully designed mock agents:

- **MockIncompleteGeneratorAgent**: Produces obviously incomplete answers
- **MockEagerEvaluatorAgent**: Incorrectly signals stop for incomplete answers (simulating the bug)
- **MockRefinerAgent**: Provides basic prompt refinements
- **CompleteGeneratorAgent**: Produces complete answers (for the control test)
- **AccurateEvaluatorAgent**: Correctly evaluates complete vs incomplete answers

This design isolates the convergence logic and makes the tests predictable and repeatable.
