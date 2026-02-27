import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export interface StrategyWorkbook {
  id: string;
  engagement_id?: string | null;
  diagnostic_id?: string | null;
  created_by_user_id?: string | null;
  diagnostic_context?: Record<string, any> | null;
  status: 'draft' | 'extracting' | 'ready' | 'failed';
  uploaded_media_ids?: string[];
  template_path?: string;
  generated_workbook_path?: string;
  extracted_data?: Record<string, any>;
  notes?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface UploadedFile {
  id: string;
  file_name: string;
  file_size?: number;
  file_type?: string;
  openai_file_id?: string;
  description?: string;
  question_field_name?: string;
  tag?: string;
  created_at?: string;
}

interface StrategyWorkbookState {
  currentWorkbook: StrategyWorkbook | null;
  isLoading: boolean;
  isExtracting: boolean;
  isGenerating: boolean;
  error: string | null;
  uploadedFiles: UploadedFile[];
  clarificationNotes: string;
  clarificationAnswers: Record<number, string>;
  clarificationQuestions: string[];
  isPrechecking: boolean;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Helper function to get auth headers
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
};

// Async thunks
export const uploadDocuments = createAsyncThunk(
  'strategyWorkbook/uploadDocuments',
  async ({ files, workbookId }: { files: File[]; workbookId?: string }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const formData = new FormData();
      files.forEach((file) => {
        formData.append('files', file);
      });
      if (workbookId) {
        formData.append('workbook_id', workbookId);
      }

      const response = await fetch(`${API_BASE_URL}/api/strategy-workbook/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to upload documents' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to upload documents`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to upload documents');
    }
  }
);

export const precheckWorkbook = createAsyncThunk(
  'strategyWorkbook/precheckWorkbook',
  async (workbookId: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/strategy-workbook/precheck`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ workbook_id: workbookId }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to run precheck' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to run precheck`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to run precheck');
    }
  }
);

export const extractData = createAsyncThunk(
  'strategyWorkbook/extractData',
  async (workbookId: string, { rejectWithValue, getState }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Build clarification notes from per-question answers + free-text notes
      const state: any = getState();
      const answers: Record<number, string> = state?.strategyWorkbook?.clarificationAnswers || {};
      const questions: string[] = state?.strategyWorkbook?.clarificationQuestions || [];
      const freeTextNotes: string = state?.strategyWorkbook?.clarificationNotes || '';

      // Format per-question answers into a single string
      const formattedAnswers = questions
        .map((q: string, i: number) => {
          const answer = (answers[i] || '').trim();
          return answer ? `Q: ${q}\nA: ${answer}` : null;
        })
        .filter(Boolean)
        .join('\n\n');

      const clarificationNotes: string | undefined =
        [formattedAnswers, freeTextNotes.trim()].filter(Boolean).join('\n\n') || undefined;

      const response = await fetch(`${API_BASE_URL}/api/strategy-workbook/extract`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          workbook_id: workbookId,
          clarification_notes:
            clarificationNotes && clarificationNotes.trim().length > 0
              ? clarificationNotes
              : undefined,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to extract data' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to extract data`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to extract data');
    }
  }
);

export const generateWorkbook = createAsyncThunk(
  'strategyWorkbook/generateWorkbook',
  async ({ workbookId, reviewNotes }: { workbookId: string; reviewNotes?: string }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/strategy-workbook/generate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          workbook_id: workbookId,
          review_notes: reviewNotes 
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to generate workbook' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to generate workbook`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to generate workbook');
    }
  }
);

export const getWorkbook = createAsyncThunk(
  'strategyWorkbook/getWorkbook',
  async (workbookId: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/strategy-workbook/${workbookId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to get workbook' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to get workbook`);
      }

      const data = await response.json();
      return data as StrategyWorkbook;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to get workbook');
    }
  }
);

// Initial state
const initialState: StrategyWorkbookState = {
  currentWorkbook: null,
  isLoading: false,
  isExtracting: false,
  isGenerating: false,
  error: null,
  uploadedFiles: [],
  clarificationNotes: '',
  clarificationAnswers: {},
  clarificationQuestions: [],
  isPrechecking: false,
};

// Slice
const strategyWorkbookSlice = createSlice({
  name: 'strategyWorkbook',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    clearWorkbook: (state) => {
      state.currentWorkbook = null;
      state.uploadedFiles = [];
      state.error = null;
      state.clarificationNotes = '';
      state.clarificationAnswers = {};
      state.clarificationQuestions = [];
      state.isPrechecking = false;
    },
    setReviewNotes: (state, action: PayloadAction<string>) => {
      if (state.currentWorkbook) {
        state.currentWorkbook.notes = action.payload;
      }
    },
    setClarificationNotes: (state, action: PayloadAction<string>) => {
      state.clarificationNotes = action.payload;
    },
    setClarificationAnswer: (state, action: PayloadAction<{ index: number; value: string }>) => {
      state.clarificationAnswers[action.payload.index] = action.payload.value;
    },
  },
  extraReducers: (builder) => {
    builder
      // Precheck workbook
      .addCase(precheckWorkbook.pending, (state) => {
        state.isPrechecking = true;
        state.error = null;
        state.clarificationQuestions = [];
      })
      .addCase(precheckWorkbook.fulfilled, (state, action) => {
        state.isPrechecking = false;
        state.clarificationQuestions = action.payload.clarification_questions || [];
      })
      .addCase(precheckWorkbook.rejected, (state, action) => {
        state.isPrechecking = false;
        state.error = action.payload as string;
      })
      // Upload documents
      .addCase(uploadDocuments.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(uploadDocuments.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentWorkbook = {
          id: action.payload.workbook_id,
          status: action.payload.status,
          uploaded_media_ids: action.payload.uploaded_files?.map((f: any) => f.id) || [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        state.uploadedFiles = action.payload.uploaded_files || [];
      })
      .addCase(uploadDocuments.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Extract data
      .addCase(extractData.pending, (state) => {
        state.isExtracting = true;
        state.error = null;
      })
      .addCase(extractData.fulfilled, (state, action) => {
        state.isExtracting = false;
        if (state.currentWorkbook) {
          state.currentWorkbook.status = action.payload.status;
          state.currentWorkbook.extracted_data = action.payload.extracted_data;
        }
      })
      .addCase(extractData.rejected, (state, action) => {
        state.isExtracting = false;
        state.error = action.payload as string;
        if (state.currentWorkbook) {
          state.currentWorkbook.status = 'failed';
        }
      })
      // Generate workbook
      .addCase(generateWorkbook.pending, (state) => {
        state.isGenerating = true;
        state.error = null;
      })
      .addCase(generateWorkbook.fulfilled, (state, action) => {
        state.isGenerating = false;
        if (state.currentWorkbook) {
          state.currentWorkbook.status = action.payload.status;
          state.currentWorkbook.generated_workbook_path = action.payload.download_url;
          state.currentWorkbook.completed_at = new Date().toISOString();
        }
      })
      .addCase(generateWorkbook.rejected, (state, action) => {
        state.isGenerating = false;
        state.error = action.payload as string;
        if (state.currentWorkbook) {
          state.currentWorkbook.status = 'failed';
        }
      })
      // Get workbook
      .addCase(getWorkbook.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(getWorkbook.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentWorkbook = action.payload;
      })
      .addCase(getWorkbook.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError, clearWorkbook, setReviewNotes, setClarificationNotes, setClarificationAnswer } =
  strategyWorkbookSlice.actions;
export default strategyWorkbookSlice.reducer;

