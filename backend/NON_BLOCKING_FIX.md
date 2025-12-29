# Non-Blocking Request Fix

## Problem
When the diagnostic scoring process was running, it was blocking **all other requests** to the API server. This meant:
- Users couldn't fetch tasks while scoring was running
- Other API endpoints were unresponsive
- The entire server was blocked for 10-15 minutes

## Root Cause
The OpenAI Python SDK uses **synchronous (blocking) HTTP calls** by default. Even though we were using `async` functions and `BackgroundTasks`, the actual OpenAI API call (`self.client.responses.create()`) was blocking the event loop, preventing FastAPI from processing other requests.

## Solution
Wrapped all OpenAI API calls in `asyncio.run_in_executor()` to run them in a **thread pool**. This allows:
- The blocking OpenAI call to run in a separate thread
- The event loop to continue processing other requests
- Multiple requests to be handled concurrently

## Changes Made

### `backend/app/services/openai_service.py`

1. **Added `asyncio` import**
   ```python
   import asyncio
   ```

2. **Wrapped OpenAI API calls in thread pool**
   ```python
   # Before (blocking):
   response = self.client.responses.create(**params)
   
   # After (non-blocking):
   loop = asyncio.get_event_loop()
   response = await loop.run_in_executor(
       None,  # Use default ThreadPoolExecutor
       lambda: self.client.responses.create(**params)
   )
   ```

3. **Applied to both:**
   - `generate_completion()` - Main API call for scoring
   - `upload_file()` - File uploads

## How It Works

```
Request 1: Submit Diagnostic (Background Task)
    ↓
OpenAI API Call → Runs in Thread Pool
    ↓
Event Loop Continues → Can Process Other Requests
    ↓
Request 2: Fetch Tasks → Processed Immediately ✅
Request 3: Get Diagnostic Status → Processed Immediately ✅
Request 4: Other API Calls → All Processed ✅
```

## Benefits

1. **Non-Blocking**: Other requests can be processed while OpenAI is running
2. **Better UX**: Users can continue using the app during processing
3. **Scalable**: Multiple diagnostics can process simultaneously
4. **No Timeout Issues**: Background tasks still work correctly

## Testing

To verify the fix works:
1. Submit a diagnostic (starts background processing)
2. While it's processing, try to:
   - Fetch tasks → Should work immediately
   - Check diagnostic status → Should work immediately
   - Use other API endpoints → Should all work

All requests should be processed without waiting for the OpenAI call to complete.

## Technical Details

- **Thread Pool**: Uses Python's default `ThreadPoolExecutor`
- **Event Loop**: FastAPI's async event loop continues running
- **Concurrency**: Multiple requests can be handled concurrently
- **Background Tasks**: Still run after response is sent, but now non-blocking

## Notes

- The OpenAI calls still take 10-15 minutes, but they no longer block other requests
- Background tasks continue to work as expected
- No changes needed to the frontend or API endpoints

