import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export interface Diagnostic {
  id: string;
  engagementId: string;
  createdByUserId: string;
  completedByUserId?: string;
  status: 'draft' | 'in_progress' | 'processing' | 'completed' | 'archived';
  diagnosticType: string;
  diagnosticVersion: string;
  questions?: Record<string, any>;
  userResponses?: Record<string, any>;
  scoringData?: Record<string, any>;
  aiAnalysis?: Record<string, any>;
  moduleScores?: Record<string, any>;
  overallScore?: number;
  reportUrl?: string;
  reportHtml?: string;
  tasksGeneratedCount?: number;
  aiModelUsed?: string;
  aiTokensUsed?: number;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  updatedAt: string;
}

export interface DiagnosticResponseUpdate {
  userResponses: Record<string, any>;
  status?: 'draft' | 'in_progress' | 'processing' | 'completed' | 'archived';
}

interface DiagnosticState {
  diagnostic: Diagnostic | null;
  isLoading: boolean;
  isSaving: boolean;
  isSubmitting: boolean;
  isPolling: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Helper function to map backend diagnostic to frontend format
function mapBackendDiagnosticToFrontend(item: any): Diagnostic {
  return {
    id: item.id,
    engagementId: item.engagement_id,
    createdByUserId: item.created_by_user_id,
    completedByUserId: item.completed_by_user_id,
    status: item.status || 'draft',
    diagnosticType: item.diagnostic_type || 'business_health_assessment',
    diagnosticVersion: item.diagnostic_version || '1.0',
    questions: item.questions,
    userResponses: item.user_responses || {},
    scoringData: item.scoring_data,
    aiAnalysis: item.ai_analysis,
    moduleScores: item.module_scores,
    overallScore: item.overall_score ? parseFloat(item.overall_score) : undefined,
    reportUrl: item.report_url,
    reportHtml: item.report_html,
    tasksGeneratedCount: item.tasks_generated_count || 0,
    aiModelUsed: item.ai_model_used,
    aiTokensUsed: item.ai_tokens_used,
    createdAt: item.created_at,
    startedAt: item.started_at,
    completedAt: item.completed_at,
    updatedAt: item.updated_at,
  };
}

// Helper function to map frontend diagnostic update to backend format
function mapFrontendResponseUpdateToBackend(update: DiagnosticResponseUpdate): any {
  return {
    user_responses: update.userResponses,
    status: update.status || undefined,
  };
}

// Async thunks
export const fetchDiagnosticByEngagement = createAsyncThunk(
  'diagnostic/fetchDiagnosticByEngagement',
  async (engagementId: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Get diagnostic by engagement_id using the engagement-specific endpoint
      const response = await fetch(`${API_BASE_URL}/api/diagnostics/engagement/${engagementId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch diagnostic' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch diagnostic`);
      }

      const data = await response.json();
      
      // If we get a list, take the first one (most recent)
      const diagnostics = Array.isArray(data) ? data : [data];
      if (diagnostics.length === 0) {
        throw new Error('No diagnostic found for this engagement');
      }

      // Get the first diagnostic (most recent) - this is just a list item without full details
      const diagnosticListItem = diagnostics[0];
      
      // Fetch the full diagnostic detail to get userResponses
      const detailResponse = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticListItem.id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!detailResponse.ok) {
        const errorData = await detailResponse.json().catch(() => ({ detail: 'Failed to fetch diagnostic details' }));
        throw new Error(errorData.detail || `HTTP ${detailResponse.status}: Failed to fetch diagnostic details`);
      }

      const detailData = await detailResponse.json();
      return mapBackendDiagnosticToFrontend(detailData);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch diagnostic');
    }
  }
);

export const fetchDiagnosticById = createAsyncThunk(
  'diagnostic/fetchDiagnosticById',
  async (diagnosticId: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch diagnostic' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch diagnostic`);
      }

      const data = await response.json();
      return mapBackendDiagnosticToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch diagnostic');
    }
  }
);

export const updateDiagnosticResponses = createAsyncThunk(
  'diagnostic/updateResponses',
  async (
    { diagnosticId, updates }: { diagnosticId: string; updates: DiagnosticResponseUpdate },
    { rejectWithValue }
  ) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const backendPayload = mapFrontendResponseUpdateToBackend(updates);

      const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/responses`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backendPayload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to update diagnostic responses' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to update diagnostic responses`);
      }

      const data = await response.json();
      return mapBackendDiagnosticToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update diagnostic responses');
    }
  }
);

export const submitDiagnostic = createAsyncThunk(
  'diagnostic/submit',
  async (
    { diagnosticId, completedByUserId }: { diagnosticId: string; completedByUserId: string },
    { rejectWithValue }
  ) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/submit`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          completed_by_user_id: completedByUserId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to submit diagnostic' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to submit diagnostic`);
      }

      const data = await response.json();
      return mapBackendDiagnosticToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to submit diagnostic');
    }
  }
);

// Check diagnostic status (lightweight endpoint for polling)
export const checkDiagnosticStatus = createAsyncThunk(
  'diagnostic/checkStatus',
  async (diagnosticId: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/status`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to check status' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to check status`);
      }

      const statusData = await response.json();
      
      // If completed, fetch full diagnostic data
      if (statusData.status === 'completed' || statusData.status === 'failed') {
        const detailResponse = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (detailResponse.ok) {
          const detailData = await detailResponse.json();
          return {
            status: statusData.status,
            completedAt: statusData.completed_at,
            diagnostic: mapBackendDiagnosticToFrontend(detailData),
          };
        }
      }

      return {
        status: statusData.status,
        completedAt: statusData.completed_at,
        diagnostic: null,
      };
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to check status');
    }
  }
);

// Initial state
const initialState: DiagnosticState = {
  diagnostic: null,
  isLoading: false,
  isSaving: false,
  isSubmitting: false,
  isPolling: false,
  error: null,
};

// Slice
const diagnosticSlice = createSlice({
  name: 'diagnostic',
  initialState,
  reducers: {
    clearDiagnostic: (state) => {
      state.diagnostic = null;
      state.error = null;
    },
    clearError: (state) => {
      state.error = null;
    },
    stopPolling: (state) => {
      state.isPolling = false;
    },
    // Update local responses without API call (for optimistic updates)
    updateLocalResponses: (state, action: PayloadAction<Record<string, any>>) => {
      if (state.diagnostic) {
        state.diagnostic.userResponses = {
          ...state.diagnostic.userResponses,
          ...action.payload,
        };
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch diagnostic by engagement
      .addCase(fetchDiagnosticByEngagement.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchDiagnosticByEngagement.fulfilled, (state, action) => {
        state.isLoading = false;
        state.diagnostic = action.payload;
        // Start polling if status is processing
        if (action.payload.status === 'processing') {
          state.isPolling = true;
          
          // Store in localStorage for global polling
          try {
            const stored = localStorage.getItem('processing_diagnostics');
            const diagnostics = stored ? JSON.parse(stored) : [];
            const exists = diagnostics.some((d: { id: string }) => d.id === action.payload.id);
            if (!exists) {
              diagnostics.push({
                id: action.payload.id,
                engagementId: action.payload.engagementId,
                timestamp: Date.now(),
              });
              localStorage.setItem('processing_diagnostics', JSON.stringify(diagnostics));
            }
          } catch (e) {
            console.error('Error storing processing diagnostic:', e);
          }
        }
      })
      .addCase(fetchDiagnosticByEngagement.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Fetch diagnostic by ID
      .addCase(fetchDiagnosticById.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchDiagnosticById.fulfilled, (state, action) => {
        state.isLoading = false;
        state.diagnostic = action.payload;
      })
      .addCase(fetchDiagnosticById.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Update responses
      .addCase(updateDiagnosticResponses.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(updateDiagnosticResponses.fulfilled, (state, action) => {
        state.isSaving = false;
        state.diagnostic = action.payload;
      })
      .addCase(updateDiagnosticResponses.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      // Submit diagnostic
      .addCase(submitDiagnostic.pending, (state) => {
        state.isSubmitting = true;
        state.error = null;
      })
      .addCase(submitDiagnostic.fulfilled, (state, action) => {
        state.isSubmitting = false;
        state.diagnostic = action.payload;
        // Start polling if status is processing
        if (action.payload.status === 'processing') {
          state.isPolling = true;
          
          // Store in localStorage for global polling
          try {
            const stored = localStorage.getItem('processing_diagnostics');
            const diagnostics = stored ? JSON.parse(stored) : [];
            const exists = diagnostics.some((d: { id: string }) => d.id === action.payload.id);
            if (!exists) {
              diagnostics.push({
                id: action.payload.id,
                engagementId: action.payload.engagementId,
                timestamp: Date.now(),
              });
              localStorage.setItem('processing_diagnostics', JSON.stringify(diagnostics));
            }
          } catch (e) {
            console.error('Error storing processing diagnostic:', e);
          }
        }
      })
      .addCase(submitDiagnostic.rejected, (state, action) => {
        state.isSubmitting = false;
        state.error = action.payload as string;
      })
      // Check diagnostic status
      .addCase(checkDiagnosticStatus.pending, (state) => {
        // Don't set isPolling here - it's managed by the component/hook
        // This allows global polling to work independently
      })
      .addCase(checkDiagnosticStatus.fulfilled, (state, action) => {
        // Update diagnostic if we got full data
        if (action.payload.diagnostic) {
          // If this is the current diagnostic, update it
          if (state.diagnostic && state.diagnostic.id === action.payload.diagnostic.id) {
            state.diagnostic = action.payload.diagnostic;
          } else {
            // Otherwise, just update the status if it matches
            state.diagnostic = action.payload.diagnostic;
          }
        } else if (state.diagnostic) {
          // Update status only if we have a current diagnostic
          // Note: We don't know which diagnostic this is for, so we only update if it matches
          state.diagnostic.status = action.payload.status as Diagnostic['status'];
          if (action.payload.completedAt) {
            state.diagnostic.completedAt = action.payload.completedAt;
          }
        }
        
        // Note: isPolling is managed by the global hook, not here
        // This allows polling to continue even if user navigates away
      })
      .addCase(checkDiagnosticStatus.rejected, (state, action) => {
        // Don't stop polling on error, just log it
        state.error = action.payload as string;
      });
  },
});

export const { clearDiagnostic, clearError, updateLocalResponses, stopPolling } = diagnosticSlice.actions;
export default diagnosticSlice.reducer;

