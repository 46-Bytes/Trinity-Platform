# Global Diagnostic Polling & Notifications

## Overview

The system now tracks processing diagnostics **globally across all pages** and automatically notifies users when diagnostics complete, even if they navigate away from the diagnostic page.

## How It Works

### 1. **When Diagnostic is Submitted**

When a user submits a diagnostic:
- Diagnostic status is set to `"processing"`
- Diagnostic ID and engagement ID are stored in `localStorage` under `processing_diagnostics`
- This allows tracking even after page refresh

### 2. **Global Polling Hook**

The `useGlobalDiagnosticPolling` hook:
- Runs in `DashboardLayout` (applies to all dashboard pages)
- Checks `localStorage` for processing diagnostics
- Polls each diagnostic's status every 5 seconds
- Continues polling even when user navigates to other pages

### 3. **Status Checking**

For each processing diagnostic:
- Calls `GET /api/diagnostics/{id}/status` every 5 seconds
- Lightweight endpoint that only returns status
- Doesn't block other requests (non-blocking)

### 4. **Completion Notification**

When status becomes `"completed"`:
- ✅ Shows success toast notification with "View Report" button
- Removes diagnostic from `localStorage`
- Stops polling for that diagnostic
- Refreshes engagements list to update status
- User can click "View Report" to navigate to engagement

### 5. **Failure Handling**

When status becomes `"failed"`:
- ❌ Shows error toast notification
- Removes diagnostic from `localStorage`
- Stops polling for that diagnostic

## Files Modified

### Frontend

1. **`frontend/src/hooks/useGlobalDiagnosticPolling.ts`** (NEW)
   - Global polling hook that runs across all pages
   - Tracks processing diagnostics from localStorage
   - Shows notifications on completion/failure

2. **`frontend/src/components/layout/DashboardLayout.tsx`**
   - Added `useGlobalDiagnosticPolling()` hook
   - Ensures polling runs on all dashboard pages

3. **`frontend/src/store/slices/diagnosticReducer.ts`**
   - Stores diagnostic in localStorage when submitted
   - Updates state when status changes

4. **`frontend/src/components/engagement/tools/ToolSurvey.tsx`**
   - Removes diagnostic from localStorage when completed
   - Shows immediate notification (in addition to global one)

## User Experience

### Scenario 1: User Stays on Diagnostic Page
1. User submits diagnostic
2. Sees "Processing..." message
3. Local polling checks status every 5 seconds
4. Gets notification when complete ✅

### Scenario 2: User Navigates Away
1. User submits diagnostic
2. Navigates to Tasks page (or any other page)
3. **Global polling continues in background**
4. Gets notification when complete ✅
5. Can click "View Report" to go back

### Scenario 3: User Refreshes Page
1. User submits diagnostic
2. Refreshes browser
3. Global polling checks localStorage on mount
4. Finds processing diagnostic
5. Continues polling ✅
6. Gets notification when complete

## Notification Details

### Success Notification
```
✅ Diagnostic Processing Completed!
Your diagnostic report is ready for download.

[View Report] button → Navigates to engagement page
```

### Error Notification
```
❌ Diagnostic Processing Failed
Please try submitting the diagnostic again.
```

## Technical Details

### localStorage Structure
```json
{
  "processing_diagnostics": [
    {
      "id": "diagnostic-uuid",
      "engagementId": "engagement-uuid",
      "timestamp": 1234567890
    }
  ]
}
```

### Polling Interval
- **5 seconds** - Checks status every 5 seconds
- **30 minutes** - Auto-cleans diagnostics older than 30 minutes
- **20 minutes** - Safety timeout (stops polling after 20 minutes)

### Cleanup
- Removes from localStorage when completed/failed
- Cleans up old diagnostics on mount
- Clears intervals on component unmount

## Benefits

1. **Persistent Tracking**: Works across page navigation
2. **Automatic Notifications**: User doesn't need to check manually
3. **Non-Intrusive**: Polling doesn't block other requests
4. **Survives Refresh**: Continues tracking after page refresh
5. **Multiple Diagnostics**: Can track multiple processing diagnostics simultaneously

## Testing

To test the global polling:

1. Submit a diagnostic
2. Navigate to Tasks page (or any other page)
3. Wait 10-15 minutes
4. You should receive a notification when it completes
5. Click "View Report" to navigate back to the engagement

The notification should appear regardless of which page you're on!

