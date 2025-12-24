# Background Processing Guide

## Overview

The diagnostic submission process now runs asynchronously in the background to avoid HTTP timeout issues on Render (30-second limit) and provide better user experience.

## How It Works

1. **Submit Endpoint** (`POST /api/diagnostics/{diagnostic_id}/submit`)
   - Returns immediately with status `"processing"`
   - Starts background job that processes the diagnostic
   - No timeout issues - processing can take 10-15 minutes

2. **Background Processing**
   - Runs all AI processing steps
   - Generates PDF report automatically
   - Updates status to `"completed"` when done
   - Updates status to `"failed"` if errors occur

3. **Status Polling** (`GET /api/diagnostics/{diagnostic_id}/status`)
   - Lightweight endpoint for frontend polling
   - Returns current status: `"processing"`, `"completed"`, or `"failed"`

4. **Download Report** (`GET /api/diagnostics/{diagnostic_id}/download`)
   - Available once status is `"completed"`
   - Downloads the generated PDF report

## Frontend Implementation

### 1. Submit Diagnostic

```typescript
const submitDiagnostic = async (diagnosticId: string, userId: string) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        completed_by_user_id: userId
      })
    });
    
    if (!response.ok) {
      throw new Error('Failed to submit diagnostic');
    }
    
    const diagnostic = await response.json();
    console.log('Diagnostic submitted, status:', diagnostic.status); // Should be "processing"
    
    // Start polling for completion
    pollDiagnosticStatus(diagnosticId);
    
  } catch (error) {
    console.error('Error submitting diagnostic:', error);
  }
};
```

### 2. Poll for Status

```typescript
const pollDiagnosticStatus = (diagnosticId: string) => {
  const pollInterval = setInterval(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/status`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Failed to check status');
      }
      
      const statusData = await response.json();
      
      if (statusData.status === 'completed') {
        clearInterval(pollInterval);
        console.log('✅ Diagnostic processing completed!');
        
        // Show success notification
        showNotification('Diagnostic completed! PDF is ready for download.', 'success');
        
        // Refresh diagnostic data
        loadDiagnostic(diagnosticId);
        
        // Optionally auto-download PDF
        // downloadReport(diagnosticId);
        
      } else if (statusData.status === 'failed') {
        clearInterval(pollInterval);
        console.error('❌ Diagnostic processing failed');
        showNotification('Diagnostic processing failed. Please try again.', 'error');
        
      } else {
        // Still processing - show progress
        console.log('⏳ Processing...', statusData.status);
        updateProgressIndicator('Processing diagnostic...');
      }
      
    } catch (error) {
      console.error('Error checking status:', error);
      clearInterval(pollInterval);
    }
  }, 5000); // Poll every 5 seconds
  
  // Stop polling after 20 minutes (safety timeout)
  setTimeout(() => {
    clearInterval(pollInterval);
    console.warn('Polling timeout - check status manually');
  }, 20 * 60 * 1000);
};
```

### 3. Download Report

```typescript
const downloadReport = async (diagnosticId: string) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/download`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to download report');
    }
    
    // Get filename from Content-Disposition header
    const contentDisposition = response.headers.get('Content-Disposition');
    const filename = contentDisposition
      ? contentDisposition.split('filename=')[1].replace(/"/g, '')
      : `diagnostic-report-${diagnosticId}.pdf`;
    
    // Create blob and download
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    
    console.log('✅ Report downloaded:', filename);
    
  } catch (error) {
    console.error('Error downloading report:', error);
    showNotification('Failed to download report. Please try again.', 'error');
  }
};
```

### 4. Complete Example with React

```typescript
import { useState, useEffect } from 'react';

const DiagnosticSubmit = ({ diagnosticId, userId }) => {
  const [status, setStatus] = useState<'draft' | 'processing' | 'completed' | 'failed'>('draft');
  const [isPolling, setIsPolling] = useState(false);
  
  const submitDiagnostic = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          completed_by_user_id: userId
        })
      });
      
      const diagnostic = await response.json();
      setStatus(diagnostic.status);
      setIsPolling(true);
      startPolling();
      
    } catch (error) {
      console.error('Error submitting diagnostic:', error);
    }
  };
  
  const startPolling = () => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/status`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        const statusData = await response.json();
        setStatus(statusData.status);
        
        if (statusData.status === 'completed' || statusData.status === 'failed') {
          clearInterval(pollInterval);
          setIsPolling(false);
          
          if (statusData.status === 'completed') {
            // Show success notification
            alert('Diagnostic completed! PDF is ready for download.');
          }
        }
        
      } catch (error) {
        console.error('Error checking status:', error);
        clearInterval(pollInterval);
        setIsPolling(false);
      }
    }, 5000);
    
    // Safety timeout
    setTimeout(() => {
      clearInterval(pollInterval);
      setIsPolling(false);
    }, 20 * 60 * 1000);
  };
  
  return (
    <div>
      {status === 'draft' && (
        <button onClick={submitDiagnostic}>
          Submit Diagnostic
        </button>
      )}
      
      {status === 'processing' && (
        <div>
          <p>⏳ Processing diagnostic... This may take 10-15 minutes.</p>
          {isPolling && <p>Checking status...</p>}
        </div>
      )}
      
      {status === 'completed' && (
        <div>
          <p>✅ Diagnostic completed!</p>
          <button onClick={() => downloadReport(diagnosticId)}>
            Download PDF Report
          </button>
        </div>
      )}
      
      {status === 'failed' && (
        <div>
          <p>❌ Processing failed. Please try again.</p>
          <button onClick={submitDiagnostic}>
            Retry
          </button>
        </div>
      )}
    </div>
  );
};
```

## Status Values

- `"draft"` - Diagnostic not yet submitted
- `"processing"` - Background job is running
- `"completed"` - Processing finished, PDF ready
- `"failed"` - Error occurred during processing

## Benefits

1. **No Timeout Issues**: Returns immediately, no 30-second limit
2. **Better UX**: User can see progress and continue using the app
3. **Automatic PDF Generation**: PDF is generated during processing
4. **Error Handling**: Failed diagnostics are marked appropriately
5. **Scalable**: Multiple diagnostics can process simultaneously

## Notes

- Background tasks run in the same process as the API server
- If the server restarts, background tasks are lost (consider Celery for production)
- Polling interval: 5 seconds recommended
- Maximum processing time: ~15 minutes (adjust timeout accordingly)

