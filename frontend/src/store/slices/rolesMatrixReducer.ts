import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

// Types
export interface StaffMember {
  name: string;
  role_title?: string | null;
}

/**
 * A single matrix row. Keys map to the Job Roles columns:
 * Name | Role Descriptions | Time | Priorities | Retain | Gain | Lose | Action | Resp | When
 */
export interface MatrixRow {
  name?: string | null;
  role_description?: string | null;
  time?: string | null;
  priorities?: string | null;
  retain?: string | null;
  gain?: string | null;
  lose?: string | null;
  action?: string | null;
  resp?: string | null;
  when?: string | null;
}

/** A responsibility as pulled out of the source material, before it becomes a matrix row. */
export interface ExtractedResponsibility {
  description?: string | null;
  time?: string | null;
  priority?: string | null;
  retain?: boolean;
  gain?: boolean;
  lose?: boolean;
  action?: string | null;
  resp?: string | null;
  when?: string | null;
  source?: string | null;
}

export interface ExtractedPerson {
  name?: string | null;
  role_title?: string | null;
  responsibilities?: ExtractedResponsibility[];
}

export interface ExtractedResponsibilities {
  people?: ExtractedPerson[];
}

export interface RolesMatrix {
  id: string;
  engagement_id?: string | null;
  created_by_user_id: string;
  status: 'inputs' | 'extracted' | 'matrix_built' | 'completed';
  current_step?: number | null;
  max_step_reached?: number | null;
  file_ids?: string[] | null;
  file_mappings?: Record<string, string> | null;
  stored_files?: Record<string, string> | null;
  staff?: StaffMember[] | null;
  included_roles?: string[] | null;
  pasted_notes?: string | null;
  extracted_responsibilities?: ExtractedResponsibilities | null;
  matrix_rows?: MatrixRow[] | null;
  matrix_edited: boolean;
  ai_model_used?: string | null;
  ai_tokens_used?: number | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface UploadedFileResult {
  filename: string;
  file_id: string | null;
  status: 'success' | 'error';
  size?: number;
  error?: string;
}

interface RolesMatrixState {
  currentMatrix: RolesMatrix | null;
  isLoading: boolean;
  isUploading: boolean;
  isExtracting: boolean;
  isGenerating: boolean;
  isSaving: boolean;
  isExporting: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const getAuthToken = (): string => {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    throw new Error('No authentication token found');
  }
  return token;
};

const getAuthHeaders = () => ({
  Authorization: `Bearer ${getAuthToken()}`,
  'Content-Type': 'application/json',
});

const readError = async (response: Response, fallback: string): Promise<string> => {
  const data = await response.json().catch(() => ({ detail: fallback }));
  return data.detail || `HTTP ${response.status}: ${fallback}`;
};

// Async thunks
export const createMatrix = createAsyncThunk(
  'rolesMatrix/create',
  async ({ engagementId }: { engagementId?: string } = {}, { rejectWithValue }) => {
    try {
      const query = engagementId ? `?engagement_id=${engagementId}` : '';
      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/create-project${query}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to create roles matrix'));
      }

      return await response.json();
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create roles matrix');
    }
  }
);

export const getMatrix = createAsyncThunk(
  'rolesMatrix/get',
  async (matrixId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/${matrixId}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to load roles matrix'));
      }

      const data = await response.json();
      return data.matrix as RolesMatrix;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to load roles matrix');
    }
  }
);

export const uploadDocuments = createAsyncThunk(
  'rolesMatrix/uploadDocuments',
  async ({ matrixId, files }: { matrixId: string; files: File[] }, { rejectWithValue }) => {
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));

      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/${matrixId}/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getAuthToken()}` },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to upload documents'));
      }

      return await response.json();
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to upload documents');
    }
  }
);

export const saveInputs = createAsyncThunk(
  'rolesMatrix/saveInputs',
  async (
    {
      matrixId,
      staff,
      includedRoles,
      pastedNotes,
    }: { matrixId: string; staff: StaffMember[]; includedRoles: string[]; pastedNotes?: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/${matrixId}/inputs`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          staff,
          included_roles: includedRoles,
          pasted_notes: pastedNotes || null,
        }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to save inputs'));
      }

      const data = await response.json();
      return data.matrix as RolesMatrix;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to save inputs');
    }
  }
);

export const extractResponsibilities = createAsyncThunk(
  'rolesMatrix/extract',
  async (
    { matrixId, customInstructions }: { matrixId: string; customInstructions?: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/${matrixId}/extract`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ custom_instructions: customInstructions || null }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to extract responsibilities'));
      }

      const data = await response.json();
      return data.matrix as RolesMatrix;
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to extract responsibilities'
      );
    }
  }
);

export const generateMatrix = createAsyncThunk(
  'rolesMatrix/generate',
  async (
    { matrixId, customInstructions }: { matrixId: string; customInstructions?: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/${matrixId}/matrix/generate`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ custom_instructions: customInstructions || null }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to build the matrix'));
      }

      const data = await response.json();
      return data.matrix as RolesMatrix;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to build the matrix');
    }
  }
);

export const saveMatrixRows = createAsyncThunk(
  'rolesMatrix/saveRows',
  async ({ matrixId, rows }: { matrixId: string; rows: MatrixRow[] }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/${matrixId}/matrix`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ matrix_rows: rows }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to save the matrix'));
      }

      const data = await response.json();
      return data.matrix as RolesMatrix;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to save the matrix');
    }
  }
);

export const updateStepProgress = createAsyncThunk(
  'rolesMatrix/updateStepProgress',
  async (
    { matrixId, currentStep, maxStepReached }: { matrixId: string; currentStep: number; maxStepReached?: number },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/${matrixId}/step-progress`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ current_step: currentStep, max_step_reached: maxStepReached }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to save progress'));
      }

      const data = await response.json();
      return data.matrix as RolesMatrix;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to save progress');
    }
  }
);

export const exportMatrix = createAsyncThunk(
  'rolesMatrix/export',
  async (matrixId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/roles-matrix/${matrixId}/export/excel`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to export the matrix'));
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'Roles_and_Responsibilities_Matrix.xlsx';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      return true;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to export the matrix');
    }
  }
);

// Initial state
const initialState: RolesMatrixState = {
  currentMatrix: null,
  isLoading: false,
  isUploading: false,
  isExtracting: false,
  isGenerating: false,
  isSaving: false,
  isExporting: false,
  error: null,
};

// Slice
const rolesMatrixSlice = createSlice({
  name: 'rolesMatrix',
  initialState,
  reducers: {
    clearMatrix: (state) => {
      state.currentMatrix = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Create
      .addCase(createMatrix.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(createMatrix.fulfilled, (state) => {
        state.isLoading = false;
      })
      .addCase(createMatrix.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Get
      .addCase(getMatrix.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(getMatrix.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentMatrix = action.payload;
      })
      .addCase(getMatrix.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Upload
      .addCase(uploadDocuments.pending, (state) => {
        state.isUploading = true;
        state.error = null;
      })
      .addCase(uploadDocuments.fulfilled, (state, action) => {
        state.isUploading = false;
        if (action.payload.matrix) {
          state.currentMatrix = action.payload.matrix;
        }
      })
      .addCase(uploadDocuments.rejected, (state, action) => {
        state.isUploading = false;
        state.error = action.payload as string;
      })
      // Save inputs
      .addCase(saveInputs.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(saveInputs.fulfilled, (state, action) => {
        state.isSaving = false;
        state.currentMatrix = action.payload;
      })
      .addCase(saveInputs.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      // Extract
      .addCase(extractResponsibilities.pending, (state) => {
        state.isExtracting = true;
        state.error = null;
      })
      .addCase(extractResponsibilities.fulfilled, (state, action) => {
        state.isExtracting = false;
        state.currentMatrix = action.payload;
      })
      .addCase(extractResponsibilities.rejected, (state, action) => {
        state.isExtracting = false;
        state.error = action.payload as string;
      })
      // Generate matrix
      .addCase(generateMatrix.pending, (state) => {
        state.isGenerating = true;
        state.error = null;
      })
      .addCase(generateMatrix.fulfilled, (state, action) => {
        state.isGenerating = false;
        state.currentMatrix = action.payload;
      })
      .addCase(generateMatrix.rejected, (state, action) => {
        state.isGenerating = false;
        state.error = action.payload as string;
      })
      // Save rows
      .addCase(saveMatrixRows.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(saveMatrixRows.fulfilled, (state, action) => {
        state.isSaving = false;
        state.currentMatrix = action.payload;
      })
      .addCase(saveMatrixRows.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      // Step progress
      .addCase(updateStepProgress.fulfilled, (state, action) => {
        state.currentMatrix = action.payload;
      })
      // Export
      .addCase(exportMatrix.pending, (state) => {
        state.isExporting = true;
        state.error = null;
      })
      .addCase(exportMatrix.fulfilled, (state) => {
        state.isExporting = false;
        if (state.currentMatrix) {
          state.currentMatrix.status = 'completed';
        }
      })
      .addCase(exportMatrix.rejected, (state, action) => {
        state.isExporting = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearMatrix } = rolesMatrixSlice.actions;
export default rolesMatrixSlice.reducer;
