# Manual UI Test Guide: LMStudio Provider Integration

This document provides step-by-step instructions for manually testing the LMStudio provider integration in the Crux Agent UI.

## Prerequisites

1. **LMStudio Local Server**: Have LMStudio running locally on `http://localhost:1234` (or configured URL)
2. **Crux Agent Backend**: Backend service running with LMStudio provider configured
3. **Crux Agent Frontend**: Frontend application accessible in browser
4. **Test Model**: At least one model loaded in LMStudio (e.g., `phi-3-mini-4k-instruct`)

## Test Scenarios

### Test 1: Provider Switching to LMStudio

**Objective**: Verify that users can switch to LMStudio provider in the UI

**Steps**:
1. Open the Crux Agent web interface
2. Navigate to Settings or Provider selection area
3. Look for LMStudio in the available providers list
4. Select "LMStudio" as the provider
5. Verify the selection is saved and reflected in the UI

**Expected Results**:
- [x] LMStudio appears in the provider dropdown/selection
- [x] Selecting LMStudio updates the active provider
- [x] UI shows LMStudio-specific configuration options
- [x] Provider change is persisted (remains after page refresh)

**Test Data**: N/A

---

### Test 2: Model Selection for LMStudio

**Objective**: Verify that LMStudio models are properly listed and selectable

**Steps**:
1. Ensure LMStudio is selected as the provider
2. Navigate to model selection area
3. View the available LMStudio models list
4. Select a specific model (e.g., `phi-3-mini-4k-instruct`)
5. Verify the model selection is saved

**Expected Results**:
- [x] LMStudio models are displayed in the model dropdown
- [x] Models match those configured in `LMSTUDIO_MODELS` environment variable
- [x] Selected model is highlighted/indicated in the UI
- [x] Model selection is persisted across sessions

**Test Data**: 
```
Expected models (from default config):
- phi-3-mini-4k-instruct
- mistral-7b-instruct
```

---

### Test 3: Task Submission with LMStudio (Mock Job Path)

**Objective**: Test complete workflow of submitting a task using LMStudio provider

**Steps**:
1. Ensure LMStudio provider is selected
2. Ensure a LMStudio model is selected
3. Navigate to the "New Task" or task submission page
4. Enter a test question: "What is the capital of France?"
5. Submit the task
6. Monitor the task progress/status
7. Wait for completion and review results

**Expected Results**:
- [x] Task submission form accepts the input
- [x] Task is queued and shows "processing" status
- [x] Job ID is generated and displayed
- [x] Task progresses through expected states (queued → running → completed)
- [x] Final response is received from LMStudio
- [x] Response quality is reasonable and relevant to the question

**Test Data**:
```
Input: "What is the capital of France?"
Expected Output: Should mention "Paris" and provide accurate information
```

---

### Test 4: Error Handling - LMStudio Server Unavailable

**Objective**: Test UI behavior when LMStudio server is not available

**Steps**:
1. Stop the LMStudio local server
2. Ensure LMStudio is selected as provider in the UI
3. Submit a test task
4. Observe error handling and user feedback

**Expected Results**:
- [x] UI displays appropriate error message
- [x] Error indicates connection/server issues
- [x] User is not left in a hanging/loading state
- [x] Error message is user-friendly (not raw technical errors)

**Test Data**: Same as Test 3, but with server stopped

---

### Test 5: Settings Endpoint Integration

**Objective**: Verify that settings API properly exposes LMStudio configuration

**Steps**:
1. Open browser developer tools (Network tab)
2. Refresh the Crux Agent page or navigate to settings
3. Look for GET request to `/settings` endpoint
4. Examine the response data
5. Verify LMStudio information is included

**Expected Results**:
- [x] `/settings` endpoint returns status 200
- [x] Response includes `lmstudio_models` array
- [x] Response includes `"lmstudio"` in `available_providers`
- [x] When LMStudio is active provider, `llm_provider` field shows `"lmstudio"`
- [x] Response structure matches expected schema

**Test Data**:
```json
Expected response structure:
{
  "llm_provider": "lmstudio",
  "model_name": "phi-3-mini-4k-instruct",
  "available_providers": ["openai", "openrouter", "lmstudio"],
  "lmstudio_models": ["phi-3-mini-4k-instruct", "mistral-7b-instruct"],
  ...
}
```

---

### Test 6: Enhanced Mode with LMStudio

**Objective**: Test enhanced mode functionality with LMStudio provider

**Steps**:
1. Select LMStudio as provider
2. Navigate to Enhanced mode task submission
3. Enter a complex question requiring multiple iterations
4. Submit the task and monitor progress
5. Verify specialist and professor interactions work with LMStudio

**Expected Results**:
- [x] Enhanced mode accepts the task with LMStudio provider
- [x] Multiple iterations are executed using LMStudio
- [x] Specialists and Professor agents all use LMStudio successfully
- [x] Final result shows improvement through iterations

**Test Data**:
```
Input: "Explain quantum computing principles and their applications in cryptography"
Expected: Multi-iteration response with increasing detail and accuracy
```

---

### Test 7: Performance and Responsiveness

**Objective**: Verify UI performance when using LMStudio provider

**Steps**:
1. Select LMStudio provider
2. Submit multiple tasks in quick succession
3. Monitor UI responsiveness during processing
4. Check for any UI freezing or blocking behavior

**Expected Results**:
- [x] UI remains responsive during task processing
- [x] Multiple tasks can be queued without UI issues
- [x] Task status updates appear promptly
- [x] No unexpected loading states or UI glitches

**Test Data**: Multiple simple questions submitted rapidly

---

## Mock Job Path Testing

For testing without a real LMStudio server, you can use the following mock approaches:

### Option 1: Mock Server Response
Set up a simple HTTP server on `localhost:1234` that returns mock OpenAI-compatible responses:

```json
{
  "choices": [
    {
      "message": {
        "content": "This is a mock response from LMStudio for testing purposes."
      }
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  }
}
```

### Option 2: Environment Variable Override
Temporarily set test environment variables:
```bash
LMSTUDIO_MODELS="test-model-1,test-model-2,mock-phi-3"
LLM_PROVIDER=lmstudio
```

### Option 3: Backend Configuration
Modify the backend to point to a mock endpoint or use test configuration.

## Troubleshooting Common Issues

### Issue 1: LMStudio Not Appearing in Provider List
- Check backend configuration for LMStudio support
- Verify `/settings` endpoint includes LMStudio
- Check browser console for JavaScript errors

### Issue 2: Models Not Loading
- Verify `LMSTUDIO_MODELS` environment variable is set
- Check that backend can access LMStudio configuration
- Ensure models list is not empty in settings response

### Issue 3: Task Submission Fails
- Check LMStudio server is running on correct port
- Verify API key configuration (if required)
- Check browser network tab for HTTP errors
- Review backend logs for detailed error messages

### Issue 4: UI Freezing During Processing
- Check for JavaScript errors in browser console
- Verify WebSocket connections (if used for real-time updates)
- Monitor backend performance and resource usage

## Test Results Documentation

Use this checklist to document your test results:

```
Test 1 (Provider Switching): [ ] Pass [ ] Fail
Test 2 (Model Selection): [ ] Pass [ ] Fail  
Test 3 (Task Submission): [ ] Pass [ ] Fail
Test 4 (Error Handling): [ ] Pass [ ] Fail
Test 5 (Settings API): [ ] Pass [ ] Fail
Test 6 (Enhanced Mode): [ ] Pass [ ] Fail
Test 7 (Performance): [ ] Pass [ ] Fail

Notes:
- Browser: ________________
- LMStudio Version: ________________
- Backend Version: ________________
- Test Date: ________________
- Issues Found: ________________
```

## Additional Notes

- Test on multiple browsers (Chrome, Firefox, Safari) if possible
- Test with different screen sizes/mobile devices
- Consider testing with slow network conditions
- Document any unexpected behavior or edge cases discovered
- Take screenshots of successful test results for documentation
