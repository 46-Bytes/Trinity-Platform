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

// Initial state
const initialState: DiagnosticState = {
  diagnostic: null,
  isLoading: false,
  isSaving: false,
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
      });
  },
});

export const { clearDiagnostic, clearError, updateLocalResponses } = diagnosticSlice.actions;
export default diagnosticSlice.reducer;

