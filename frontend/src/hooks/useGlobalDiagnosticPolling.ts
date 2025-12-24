import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { checkDiagnosticStatus } from '@/store/slices/diagnosticReducer';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { toast } from 'sonner';

/**
 * Global hook that polls for processing diagnostics across all pages.
 * This ensures users get notified when diagnostics complete, even if they
 * navigate away from the diagnostic page.
 */
export function useGlobalDiagnosticPolling() {
  const dispatch = useAppDispatch();
  const { engagements } = useAppSelector((state) => state.engagement);
  const pollingIntervalsRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const notifiedDiagnosticsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    // Find all diagnostics that are currently processing
    const processingDiagnostics: Array<{ diagnosticId: string; engagementId: string }> = [];

    // Check localStorage for recently submitted diagnostics
    // This is the primary source since we store diagnostics here when they're submitted
    const storedProcessingDiagnostics = localStorage.getItem('processing_diagnostics');
    if (storedProcessingDiagnostics) {
      try {
        const diagnostics = JSON.parse(storedProcessingDiagnostics);
        const now = Date.now();
        
        diagnostics.forEach((diag: { id: string; engagementId: string; timestamp: number }) => {
          // Only include diagnostics that are less than 30 minutes old
          if (now - diag.timestamp < 30 * 60 * 1000) {
            if (!notifiedDiagnosticsRef.current.has(diag.id)) {
              processingDiagnostics.push({
                diagnosticId: diag.id,
                engagementId: diag.engagementId,
              });
            }
          }
        });
      } catch (e) {
        console.error('Error parsing stored diagnostics:', e);
      }
    }

    // Start polling for each processing diagnostic
    processingDiagnostics.forEach(({ diagnosticId, engagementId }) => {
      // Skip if already polling
      if (pollingIntervalsRef.current.has(diagnosticId)) {
        return;
      }

      const pollInterval = setInterval(async () => {
        try {
          const result = await dispatch(checkDiagnosticStatus(diagnosticId)).unwrap();

          if (result.status === 'completed') {
            // Stop polling for this diagnostic
            const interval = pollingIntervalsRef.current.get(diagnosticId);
            if (interval) {
              clearInterval(interval);
              pollingIntervalsRef.current.delete(diagnosticId);
            }

            // Remove from localStorage
            const stored = localStorage.getItem('processing_diagnostics');
            if (stored) {
              try {
                const diagnostics = JSON.parse(stored);
                const updated = diagnostics.filter((d: { id: string }) => d.id !== diagnosticId);
                if (updated.length > 0) {
                  localStorage.setItem('processing_diagnostics', JSON.stringify(updated));
                } else {
                  localStorage.removeItem('processing_diagnostics');
                }
              } catch (e) {
                // Ignore parse errors
              }
            }

            // Show notification (only once)
            if (!notifiedDiagnosticsRef.current.has(diagnosticId)) {
              notifiedDiagnosticsRef.current.add(diagnosticId);
              
              toast.success('✅ Diagnostic Processing Completed!', {
                description: 'Your diagnostic report is ready for download.',
                duration: 10000,
                action: {
                  label: 'View Report',
                  onClick: () => {
                    window.location.href = `/dashboard/engagements/${engagementId}`;
                  },
                },
              });

              // Refresh engagements to update status
              dispatch(fetchEngagements({}));
            }
          } else if (result.status === 'failed') {
            // Stop polling for failed diagnostics
            const interval = pollingIntervalsRef.current.get(diagnosticId);
            if (interval) {
              clearInterval(interval);
              pollingIntervalsRef.current.delete(diagnosticId);
            }

            // Remove from localStorage
            const stored = localStorage.getItem('processing_diagnostics');
            if (stored) {
              try {
                const diagnostics = JSON.parse(stored);
                const updated = diagnostics.filter((d: { id: string }) => d.id !== diagnosticId);
                if (updated.length > 0) {
                  localStorage.setItem('processing_diagnostics', JSON.stringify(updated));
                } else {
                  localStorage.removeItem('processing_diagnostics');
                }
              } catch (e) {
                // Ignore parse errors
              }
            }

            // Show error notification
            if (!notifiedDiagnosticsRef.current.has(diagnosticId)) {
              notifiedDiagnosticsRef.current.add(diagnosticId);
              
              toast.error('❌ Diagnostic Processing Failed', {
                description: 'Please try submitting the diagnostic again.',
                duration: 10000,
              });
            }
          }
        } catch (error) {
          console.error(`Error checking status for diagnostic ${diagnosticId}:`, error);
          // Continue polling on error
        }
      }, 5000); // Poll every 5 seconds

      pollingIntervalsRef.current.set(diagnosticId, pollInterval);
    });

    // Cleanup: Clear all intervals on unmount
    return () => {
      pollingIntervalsRef.current.forEach((interval) => clearInterval(interval));
      pollingIntervalsRef.current.clear();
    };
  }, [dispatch, engagements]);

  // Also check on mount for any stored processing diagnostics
  useEffect(() => {
    const stored = localStorage.getItem('processing_diagnostics');
    if (stored) {
      try {
        const diagnostics = JSON.parse(stored);
        // Filter out old diagnostics (older than 30 minutes)
        const now = Date.now();
        const validDiagnostics = diagnostics.filter((d: { id: string; timestamp: number }) => {
          return now - d.timestamp < 30 * 60 * 1000; // 30 minutes
        });

        if (validDiagnostics.length !== diagnostics.length) {
          if (validDiagnostics.length > 0) {
            localStorage.setItem('processing_diagnostics', JSON.stringify(validDiagnostics));
          } else {
            localStorage.removeItem('processing_diagnostics');
          }
        }
      } catch (e) {
        // Ignore parse errors
      }
    }
  }, []);
}

