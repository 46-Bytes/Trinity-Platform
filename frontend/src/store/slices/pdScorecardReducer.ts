import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

// Types

/**
 * A source matrix row. Keys map to the Job Roles columns:
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

/** A role's matrix rows, grouped by flag. */
export interface SourceResponsibilities {
  retain?: MatrixRow[];
  gain?: MatrixRow[];
  lose?: MatrixRow[];
}

export interface PDResponsibilityTheme {
  theme: string;
  responsibilities: string[];
}

/** The seven Position Description sections. */
export interface PDContent {
  position_purpose?: string | null;
  key_responsibilities?: PDResponsibilityTheme[];
  decision_making_authority?: string[];
  key_relationships?: string[];
  kpis?: string[];
  behavioural_expectations?: string[];
  transition_focus?: string[];
}

export interface ScorecardResponsibilityRow {
  focus_area?: string | null;
  core_accountability?: string | null;
  performance_indicators?: string | null;
}

export interface ScorecardBehaviourRow {
  behavioural_focus?: string | null;
  expected_demonstration?: string | null;
}

export interface ScorecardMilestoneRow {
  milestone?: string | null;
  target_date?: string | null;
}

/** The four scorecard sections. */
export interface ScorecardContent {
  role_purpose?: string | null;
  responsibilities?: ScorecardResponsibilityRow[];
  behaviours?: ScorecardBehaviourRow[];
  milestones?: ScorecardMilestoneRow[];
}

export type DraftStatus = 'not_started' | 'draft' | 'approved';

export interface PDScorecardRole {
  id: string;
  pd_scorecard_id: string;
  role_title: string;
  person_name?: string | null;
  sort_order: number;
  included: boolean;
  source_responsibilities?: SourceResponsibilities | null;
  pd_content?: PDContent | null;
  pd_status: DraftStatus;
  pd_approved_at?: string | null;
  scorecard_content?: ScorecardContent | null;
  scorecard_status: DraftStatus;
  scorecard_approved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PDScorecard {
  id: string;
  engagement_id?: string | null;
  created_by_user_id: string;
  status: 'inputs' | 'roles_identified' | 'in_progress' | 'completed';
  current_step?: number | null;
  max_step_reached?: number | null;
  client_name?: string | null;
  fy_range?: string | null;
  file_ids?: string[] | null;
  file_mappings?: Record<string, string> | null;
  stored_files?: Record<string, string> | null;
  reference_pd_files?: string[] | null;
  pasted_notes?: string | null;
  matrix_rows?: MatrixRow[] | null;
  roles?: PDScorecardRole[];
  ai_model_used?: string | null;
  ai_tokens_used?: number | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

/** A role suggested by extraction, before the advisor confirms it. */
export interface SuggestedRole {
  role_title?: string | null;
  person_name?: string | null;
}

export interface RoleInput {
  id?: string;
  role_title: string;
  person_name?: string | null;
  included: boolean;
}

export interface UploadedFileResult {
  filename: string;
  file_id: string | null;
  status: 'success' | 'error';
  size?: number;
  error?: string;
}

interface PDScorecardState {
  currentBuild: PDScorecard | null;
  suggestedRoles: SuggestedRole[];
  activeRoleId: string | null;
  isLoading: boolean;
  isUploading: boolean;
  isExtracting: boolean;
  isGeneratingPD: boolean;
  isGeneratingScorecard: boolean;
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

/** Pull the filename out of Content-Disposition, falling back to a supplied name. */
const filenameFromResponse = (response: Response, fallback: string): string => {
  const header = response.headers.get('Content-Disposition') || '';
  const match = header.match(/filename="?([^"]+)"?/);
  return match ? match[1] : fallback;
};

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

// Async thunks

export const createBuild = createAsyncThunk(
  'pdScorecard/create',
  async ({ engagementId }: { engagementId?: string } = {}, { rejectWithValue }) => {
    try {
      const query = engagementId ? `?engagement_id=${engagementId}` : '';
      const response = await fetch(`${API_BASE_URL}/api/pd-scorecard/create-project${query}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to create the PD & scorecard build'));
      }

      return await response.json();
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to create the PD & scorecard build'
      );
    }
  }
);

export const getBuild = createAsyncThunk(
  'pdScorecard/get',
  async (buildId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/pd-scorecard/${buildId}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to load the build'));
      }

      const data = await response.json();
      return data.build as PDScorecard;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to load the build');
    }
  }
);

export const uploadDocuments = createAsyncThunk(
  'pdScorecard/uploadDocuments',
  async ({ buildId, files }: { buildId: string; files: File[] }, { rejectWithValue }) => {
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));

      const response = await fetch(`${API_BASE_URL}/api/pd-scorecard/${buildId}/upload`, {
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
  'pdScorecard/saveInputs',
  async (
    {
      buildId,
      clientName,
      fyRange,
      referencePdFiles,
      pastedNotes,
    }: {
      buildId: string;
      clientName?: string | null;
      fyRange?: string | null;
      referencePdFiles: string[];
      pastedNotes?: string | null;
    },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/pd-scorecard/${buildId}/inputs`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          client_name: clientName || null,
          fy_range: fyRange || null,
          reference_pd_files: referencePdFiles,
          pasted_notes: pastedNotes || null,
        }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to save inputs'));
      }

      const data = await response.json();
      return data.build as PDScorecard;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to save inputs');
    }
  }
);

export const extractRoles = createAsyncThunk(
  'pdScorecard/extract',
  async (
    { buildId, customInstructions }: { buildId: string; customInstructions?: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/pd-scorecard/${buildId}/extract`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ custom_instructions: customInstructions || null }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to read the roles matrix'));
      }

      const data = await response.json();
      return {
        build: data.build as PDScorecard,
        suggestedRoles: (data.suggested_roles || []) as SuggestedRole[],
      };
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to read the roles matrix'
      );
    }
  }
);

export const saveRoles = createAsyncThunk(
  'pdScorecard/saveRoles',
  async ({ buildId, roles }: { buildId: string; roles: RoleInput[] }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/pd-scorecard/${buildId}/roles`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ roles }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to save the roles'));
      }

      const data = await response.json();
      return data.build as PDScorecard;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to save the roles');
    }
  }
);

export const generatePD = createAsyncThunk(
  'pdScorecard/generatePD',
  async (
    {
      buildId,
      roleId,
      customInstructions,
    }: { buildId: string; roleId: string; customInstructions?: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pd-scorecard/${buildId}/roles/${roleId}/pd/generate`,
        {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ custom_instructions: customInstructions || null }),
        }
      );

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to generate the position description'));
      }

      const data = await response.json();
      return data.role as PDScorecardRole;
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to generate the position description'
      );
    }
  }
);

export const savePD = createAsyncThunk(
  'pdScorecard/savePD',
  async (
    { buildId, roleId, pdContent }: { buildId: string; roleId: string; pdContent: PDContent },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/pd-scorecard/${buildId}/roles/${roleId}/pd`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ pd_content: pdContent }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to save the position description'));
      }

      const data = await response.json();
      return data.role as PDScorecardRole;
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to save the position description'
      );
    }
  }
);

export const approvePD = createAsyncThunk(
  'pdScorecard/approvePD',
  async ({ buildId, roleId }: { buildId: string; roleId: string }, { rejectWithValue }) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pd-scorecard/${buildId}/roles/${roleId}/pd/approve`,
        { method: 'POST', headers: getAuthHeaders() }
      );

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to approve the position description'));
      }

      const data = await response.json();
      return data.role as PDScorecardRole;
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to approve the position description'
      );
    }
  }
);

export const exportPD = createAsyncThunk(
  'pdScorecard/exportPD',
  async (
    { buildId, roleId, roleTitle }: { buildId: string; roleId: string; roleTitle: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pd-scorecard/${buildId}/roles/${roleId}/pd/export`,
        { method: 'POST', headers: { Authorization: `Bearer ${getAuthToken()}` } }
      );

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to export the position description'));
      }

      const filename = filenameFromResponse(response, `${roleTitle} - Position Description.docx`);
      downloadBlob(await response.blob(), filename);
      return true;
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to export the position description'
      );
    }
  }
);

export const generateScorecard = createAsyncThunk(
  'pdScorecard/generateScorecard',
  async (
    {
      buildId,
      roleId,
      customInstructions,
    }: { buildId: string; roleId: string; customInstructions?: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pd-scorecard/${buildId}/roles/${roleId}/scorecard/generate`,
        {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ custom_instructions: customInstructions || null }),
        }
      );

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to generate the scorecard'));
      }

      const data = await response.json();
      return data.role as PDScorecardRole;
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to generate the scorecard'
      );
    }
  }
);

export const saveScorecard = createAsyncThunk(
  'pdScorecard/saveScorecard',
  async (
    {
      buildId,
      roleId,
      scorecardContent,
    }: { buildId: string; roleId: string; scorecardContent: ScorecardContent },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pd-scorecard/${buildId}/roles/${roleId}/scorecard`,
        {
          method: 'PATCH',
          headers: getAuthHeaders(),
          body: JSON.stringify({ scorecard_content: scorecardContent }),
        }
      );

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to save the scorecard'));
      }

      const data = await response.json();
      return data.role as PDScorecardRole;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to save the scorecard');
    }
  }
);

export const approveScorecard = createAsyncThunk(
  'pdScorecard/approveScorecard',
  async ({ buildId, roleId }: { buildId: string; roleId: string }, { rejectWithValue }) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pd-scorecard/${buildId}/roles/${roleId}/scorecard/approve`,
        { method: 'POST', headers: getAuthHeaders() }
      );

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to approve the scorecard'));
      }

      const data = await response.json();
      return data.role as PDScorecardRole;
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to approve the scorecard'
      );
    }
  }
);

export const exportScorecard = createAsyncThunk(
  'pdScorecard/exportScorecard',
  async (
    { buildId, roleId, roleTitle }: { buildId: string; roleId: string; roleTitle: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/pd-scorecard/${buildId}/roles/${roleId}/scorecard/export`,
        { method: 'POST', headers: { Authorization: `Bearer ${getAuthToken()}` } }
      );

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to export the scorecard'));
      }

      const filename = filenameFromResponse(
        response,
        `${roleTitle} - Role Scorecard - Half-Yearly.xlsx`
      );
      downloadBlob(await response.blob(), filename);
      return true;
    } catch (error) {
      return rejectWithValue(
        error instanceof Error ? error.message : 'Failed to export the scorecard'
      );
    }
  }
);

export const updateStepProgress = createAsyncThunk(
  'pdScorecard/updateStepProgress',
  async (
    {
      buildId,
      currentStep,
      maxStepReached,
    }: { buildId: string; currentStep: number; maxStepReached?: number },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/pd-scorecard/${buildId}/step-progress`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ current_step: currentStep, max_step_reached: maxStepReached }),
      });

      if (!response.ok) {
        throw new Error(await readError(response, 'Failed to save progress'));
      }

      const data = await response.json();
      return data.build as PDScorecard;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to save progress');
    }
  }
);

// Initial state
const initialState: PDScorecardState = {
  currentBuild: null,
  suggestedRoles: [],
  activeRoleId: null,
  isLoading: false,
  isUploading: false,
  isExtracting: false,
  isGeneratingPD: false,
  isGeneratingScorecard: false,
  isSaving: false,
  isExporting: false,
  error: null,
};

/** Replace one role in the current build, leaving the rest untouched. */
const mergeRole = (state: PDScorecardState, role: PDScorecardRole) => {
  if (!state.currentBuild?.roles) return;
  state.currentBuild.roles = state.currentBuild.roles.map((r) => (r.id === role.id ? role : r));
};

// Slice
const pdScorecardSlice = createSlice({
  name: 'pdScorecard',
  initialState,
  reducers: {
    clearBuild: (state) => {
      state.currentBuild = null;
      state.suggestedRoles = [];
      state.activeRoleId = null;
      state.error = null;
    },
    setActiveRole: (state, action: { payload: string | null }) => {
      state.activeRoleId = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Create
      .addCase(createBuild.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(createBuild.fulfilled, (state) => {
        state.isLoading = false;
      })
      .addCase(createBuild.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Get
      .addCase(getBuild.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(getBuild.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentBuild = action.payload;
      })
      .addCase(getBuild.rejected, (state, action) => {
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
        if (action.payload.build) {
          state.currentBuild = action.payload.build;
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
        state.currentBuild = action.payload;
      })
      .addCase(saveInputs.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      // Extract
      .addCase(extractRoles.pending, (state) => {
        state.isExtracting = true;
        state.error = null;
      })
      .addCase(extractRoles.fulfilled, (state, action) => {
        state.isExtracting = false;
        state.currentBuild = action.payload.build;
        state.suggestedRoles = action.payload.suggestedRoles;
      })
      .addCase(extractRoles.rejected, (state, action) => {
        state.isExtracting = false;
        state.error = action.payload as string;
      })
      // Save roles
      .addCase(saveRoles.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(saveRoles.fulfilled, (state, action) => {
        state.isSaving = false;
        state.currentBuild = action.payload;
      })
      .addCase(saveRoles.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      // Generate PD
      .addCase(generatePD.pending, (state) => {
        state.isGeneratingPD = true;
        state.error = null;
      })
      .addCase(generatePD.fulfilled, (state, action) => {
        state.isGeneratingPD = false;
        mergeRole(state, action.payload);
      })
      .addCase(generatePD.rejected, (state, action) => {
        state.isGeneratingPD = false;
        state.error = action.payload as string;
      })
      // Save / approve PD
      .addCase(savePD.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(savePD.fulfilled, (state, action) => {
        state.isSaving = false;
        mergeRole(state, action.payload);
      })
      .addCase(savePD.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      .addCase(approvePD.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(approvePD.fulfilled, (state, action) => {
        state.isSaving = false;
        mergeRole(state, action.payload);
      })
      .addCase(approvePD.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      // Generate scorecard
      .addCase(generateScorecard.pending, (state) => {
        state.isGeneratingScorecard = true;
        state.error = null;
      })
      .addCase(generateScorecard.fulfilled, (state, action) => {
        state.isGeneratingScorecard = false;
        mergeRole(state, action.payload);
      })
      .addCase(generateScorecard.rejected, (state, action) => {
        state.isGeneratingScorecard = false;
        state.error = action.payload as string;
      })
      // Save / approve scorecard
      .addCase(saveScorecard.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(saveScorecard.fulfilled, (state, action) => {
        state.isSaving = false;
        mergeRole(state, action.payload);
      })
      .addCase(saveScorecard.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      .addCase(approveScorecard.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(approveScorecard.fulfilled, (state, action) => {
        state.isSaving = false;
        mergeRole(state, action.payload);
      })
      .addCase(approveScorecard.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      // Exports
      .addCase(exportPD.pending, (state) => {
        state.isExporting = true;
        state.error = null;
      })
      .addCase(exportPD.fulfilled, (state) => {
        state.isExporting = false;
      })
      .addCase(exportPD.rejected, (state, action) => {
        state.isExporting = false;
        state.error = action.payload as string;
      })
      .addCase(exportScorecard.pending, (state) => {
        state.isExporting = true;
        state.error = null;
      })
      .addCase(exportScorecard.fulfilled, (state) => {
        state.isExporting = false;
      })
      .addCase(exportScorecard.rejected, (state, action) => {
        state.isExporting = false;
        state.error = action.payload as string;
      })
      // Step progress
      .addCase(updateStepProgress.fulfilled, (state, action) => {
        state.currentBuild = action.payload;
      });
  },
});

export const { clearBuild, setActiveRole } = pdScorecardSlice.actions;
export default pdScorecardSlice.reducer;
