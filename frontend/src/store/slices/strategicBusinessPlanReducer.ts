import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SBPSection {
  key: string;
  title: string;
  status: 'pending' | 'drafting' | 'drafted' | 'revision_requested' | 'approved';
  content: string | null;
  strategic_implications: string | null;
  revision_notes: string | null;
  revision_history: Record<string, any>[];
  approved_at: string | null;
  draft_count: number;
}

export interface StrategicBusinessPlan {
  id: string;
  engagement_id?: string | null;
  diagnostic_id?: string | null;
  diagnostic_context?: Record<string, any> | null;
  created_by_user_id: string;
  status: string;
  current_step: number | null;
  max_step_reached: number | null;
  client_name: string | null;
  industry: string | null;
  planning_horizon: string | null;
  target_audience: string | null;
  additional_context: string | null;
  file_ids: string[] | null;
  file_mappings: Record<string, string> | null;
  file_tags: Record<string, string> | null;
  stored_files: Record<string, string> | null;
  cross_analysis: Record<string, any> | null;
  cross_analysis_advisor_notes: string | null;
  sections: SBPSection[] | null;
  current_section_index: number | null;
  emerging_themes: Record<string, any> | null;
  final_plan: Record<string, any> | null;
  report_version: number;
  generated_report_path: string | null;
  employee_variant_requested: boolean;
  presentation_slides: Record<string, any> | null;
  ai_model_used: string | null;
  ai_tokens_used: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface UploadedFileInfo {
  filename: string;
  file_id: string;
  tag: string;
  size: number;
}

interface SBPState {
  currentPlan: StrategicBusinessPlan | null;
  isLoading: boolean;
  isAnalysing: boolean;
  isDraftingSection: boolean;
  isExporting: boolean;
  isGeneratingPresentation: boolean;
  error: string | null;
  uploadedFiles: UploadedFileInfo[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const getAuthHeaders = (json = true) => {
  const token = localStorage.getItem('auth_token');
  const headers: Record<string, string> = { 'Authorization': `Bearer ${token}` };
  if (json) headers['Content-Type'] = 'application/json';
  return headers;
};

// ---------------------------------------------------------------------------
// Async thunks
// ---------------------------------------------------------------------------

export const createPlan = createAsyncThunk(
  'sbp/createPlan',
  async ({ engagementId }: { engagementId?: string }, { rejectWithValue }) => {
    try {
      const url = new URL(`${API_BASE_URL}/api/strategic-business-plan/create`);
      if (engagementId) url.searchParams.set('engagement_id', engagementId);
      const res = await fetch(url.toString(), { method: 'POST', headers: getAuthHeaders() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to create plan');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to create plan');
    }
  },
);

export const createPlanFromDiagnostic = createAsyncThunk(
  'sbp/createPlanFromDiagnostic',
  async ({ diagnosticId }: { diagnosticId: string }, { rejectWithValue }) => {
    try {
      const url = `${API_BASE_URL}/api/strategic-business-plan/create-from-diagnostic?diagnostic_id=${diagnosticId}`;
      const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to create plan');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to create plan');
    }
  },
);

export const getPlan = createAsyncThunk(
  'sbp/getPlan',
  async (planId: string, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}`, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to get plan');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to get plan');
    }
  },
);

export const uploadFiles = createAsyncThunk(
  'sbp/uploadFiles',
  async ({ planId, files }: { planId: string; files: File[] }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const formData = new FormData();
      files.forEach((f) => formData.append('files', f));
      const url = `${API_BASE_URL}/api/strategic-business-plan/${planId}/upload`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Upload failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Upload failed');
    }
  },
);

export const saveSetup = createAsyncThunk(
  'sbp/saveSetup',
  async ({ planId, data }: { planId: string; data: Record<string, any> }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/setup`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to save setup');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to save setup');
    }
  },
);

export const triggerCrossAnalysis = createAsyncThunk(
  'sbp/triggerCrossAnalysis',
  async ({ planId, customInstructions }: { planId: string; customInstructions?: string }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/cross-analysis`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ custom_instructions: customInstructions }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Cross-analysis failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Cross-analysis failed');
    }
  },
);

export const saveCrossAnalysisNotes = createAsyncThunk(
  'sbp/saveCrossAnalysisNotes',
  async ({ planId, notes }: { planId: string; notes: string }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/cross-analysis`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ notes }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to save notes');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to save notes');
    }
  },
);

export const initialiseSections = createAsyncThunk(
  'sbp/initialiseSections',
  async (planId: string, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/initialise-sections`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Failed to initialise sections');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to initialise sections');
    }
  },
);

export const draftSection = createAsyncThunk(
  'sbp/draftSection',
  async ({ planId, sectionKey, customInstructions }: { planId: string; sectionKey: string; customInstructions?: string }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/draft-section/${sectionKey}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ custom_instructions: customInstructions }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Section drafting failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Section drafting failed');
    }
  },
);

export const reviseSection = createAsyncThunk(
  'sbp/reviseSection',
  async ({ planId, sectionKey, revisionNotes }: { planId: string; sectionKey: string; revisionNotes: string }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/revise-section/${sectionKey}`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ revision_notes: revisionNotes }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Section revision failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Section revision failed');
    }
  },
);

export const editSection = createAsyncThunk(
  'sbp/editSection',
  async ({ planId, sectionKey, content, strategicImplications }: {
    planId: string; sectionKey: string; content?: string; strategicImplications?: string;
  }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/section/${sectionKey}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ content, strategic_implications: strategicImplications }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Edit failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Edit failed');
    }
  },
);

export const approveSection = createAsyncThunk(
  'sbp/approveSection',
  async ({ planId, sectionKey }: { planId: string; sectionKey: string }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/approve-section/${sectionKey}`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Approval failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Approval failed');
    }
  },
);

export const surfaceThemes = createAsyncThunk(
  'sbp/surfaceThemes',
  async (planId: string, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/surface-themes`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Theme surfacing failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Theme surfacing failed');
    }
  },
);

export const assemblePlan = createAsyncThunk(
  'sbp/assemblePlan',
  async ({ planId, sectionOrder }: { planId: string; sectionOrder?: string[] }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/assemble`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ section_order: sectionOrder }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Assembly failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Assembly failed');
    }
  },
);

export const resetPlanData = createAsyncThunk(
  'sbp/resetPlanData',
  async (planId: string, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/reset`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Reset failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Reset failed');
    }
  },
);

export const updateStepProgress = createAsyncThunk(
  'sbp/updateStepProgress',
  async ({ planId, currentStep, maxStepReached }: { planId: string; currentStep?: number; maxStepReached?: number }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/step-progress`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ current_step: currentStep, max_step_reached: maxStepReached }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Step update failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Step update failed');
    }
  },
);

export const generatePresentation = createAsyncThunk(
  'sbp/generatePresentation',
  async (planId: string, { rejectWithValue }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/strategic-business-plan/${planId}/presentation/generate`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Presentation generation failed');
      return await res.json();
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Presentation generation failed');
    }
  },
);

// ---------------------------------------------------------------------------
// Slice
// ---------------------------------------------------------------------------

const initialState: SBPState = {
  currentPlan: null,
  isLoading: false,
  isAnalysing: false,
  isDraftingSection: false,
  isExporting: false,
  isGeneratingPresentation: false,
  error: null,
  uploadedFiles: [],
};

const sbpSlice = createSlice({
  name: 'strategicBusinessPlan',
  initialState,
  reducers: {
    clearPlan: (state) => {
      state.currentPlan = null;
      state.uploadedFiles = [];
      state.error = null;
      state.isLoading = false;
      state.isAnalysing = false;
      state.isDraftingSection = false;
      state.isExporting = false;
      state.isGeneratingPresentation = false;
    },
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
  },
  extraReducers: (builder) => {
    // createPlan
    builder
      .addCase(createPlan.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(createPlan.fulfilled, (state, action) => { state.isLoading = false; })
      .addCase(createPlan.rejected, (state, action) => { state.isLoading = false; state.error = action.payload as string; });

    // createPlanFromDiagnostic
    builder
      .addCase(createPlanFromDiagnostic.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(createPlanFromDiagnostic.fulfilled, (state) => { state.isLoading = false; })
      .addCase(createPlanFromDiagnostic.rejected, (state, action) => { state.isLoading = false; state.error = action.payload as string; });

    // getPlan
    builder
      .addCase(getPlan.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(getPlan.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentPlan = action.payload;
      })
      .addCase(getPlan.rejected, (state, action) => { state.isLoading = false; state.error = action.payload as string; });

    // uploadFiles
    builder
      .addCase(uploadFiles.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(uploadFiles.fulfilled, (state, action) => {
        state.isLoading = false;
        if (action.payload.uploaded_files) {
          state.uploadedFiles = [...state.uploadedFiles, ...action.payload.uploaded_files];
        }
      })
      .addCase(uploadFiles.rejected, (state, action) => { state.isLoading = false; state.error = action.payload as string; });

    // saveSetup
    builder
      .addCase(saveSetup.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(saveSetup.fulfilled, (state, action) => {
        state.isLoading = false;
        if (action.payload.plan) state.currentPlan = action.payload.plan;
      })
      .addCase(saveSetup.rejected, (state, action) => { state.isLoading = false; state.error = action.payload as string; });

    // triggerCrossAnalysis
    builder
      .addCase(triggerCrossAnalysis.pending, (state) => { state.isAnalysing = true; state.error = null; })
      .addCase(triggerCrossAnalysis.fulfilled, (state, action) => {
        state.isAnalysing = false;
        if (state.currentPlan && action.payload.cross_analysis) {
          state.currentPlan.cross_analysis = action.payload.cross_analysis;
        }
      })
      .addCase(triggerCrossAnalysis.rejected, (state, action) => { state.isAnalysing = false; state.error = action.payload as string; });

    // initialiseSections
    builder
      .addCase(initialiseSections.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(initialiseSections.fulfilled, (state, action) => {
        state.isLoading = false;
        if (state.currentPlan && action.payload.sections) {
          state.currentPlan.sections = action.payload.sections;
        }
      })
      .addCase(initialiseSections.rejected, (state, action) => { state.isLoading = false; state.error = action.payload as string; });

    // draftSection
    builder
      .addCase(draftSection.pending, (state) => { state.isDraftingSection = true; state.error = null; })
      .addCase(draftSection.fulfilled, (state, action) => {
        state.isDraftingSection = false;
        if (state.currentPlan && action.payload.section) {
          const idx = state.currentPlan.sections?.findIndex(
            (s) => s.key === action.payload.section.key
          );
          if (idx !== undefined && idx >= 0 && state.currentPlan.sections) {
            state.currentPlan.sections[idx] = action.payload.section;
          }
        }
      })
      .addCase(draftSection.rejected, (state, action) => { state.isDraftingSection = false; state.error = action.payload as string; });

    // reviseSection
    builder
      .addCase(reviseSection.pending, (state) => { state.isDraftingSection = true; state.error = null; })
      .addCase(reviseSection.fulfilled, (state, action) => {
        state.isDraftingSection = false;
        if (state.currentPlan && action.payload.section) {
          const idx = state.currentPlan.sections?.findIndex(
            (s) => s.key === action.payload.section.key
          );
          if (idx !== undefined && idx >= 0 && state.currentPlan.sections) {
            state.currentPlan.sections[idx] = action.payload.section;
          }
        }
      })
      .addCase(reviseSection.rejected, (state, action) => { state.isDraftingSection = false; state.error = action.payload as string; });

    // editSection
    builder
      .addCase(editSection.fulfilled, (state, action) => {
        if (state.currentPlan && action.payload.section) {
          const idx = state.currentPlan.sections?.findIndex(
            (s) => s.key === action.payload.section.key
          );
          if (idx !== undefined && idx >= 0 && state.currentPlan.sections) {
            state.currentPlan.sections[idx] = action.payload.section;
          }
        }
      });

    // approveSection
    builder
      .addCase(approveSection.fulfilled, (state, action) => {
        if (state.currentPlan && action.payload.sections) {
          state.currentPlan.sections = action.payload.sections;
        }
      });

    // surfaceThemes
    builder
      .addCase(surfaceThemes.fulfilled, (state, action) => {
        if (state.currentPlan && action.payload.emerging_themes) {
          state.currentPlan.emerging_themes = action.payload.emerging_themes;
        }
      });

    // resetPlanData
    builder
      .addCase(resetPlanData.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(resetPlanData.fulfilled, (state, action) => {
        state.isLoading = false;
        state.uploadedFiles = [];
        if (action.payload.plan) state.currentPlan = action.payload.plan;
      })
      .addCase(resetPlanData.rejected, (state, action) => { state.isLoading = false; state.error = action.payload as string; });

    // assemblePlan
    builder
      .addCase(assemblePlan.pending, (state) => { state.isLoading = true; state.error = null; })
      .addCase(assemblePlan.fulfilled, (state, action) => {
        state.isLoading = false;
        if (state.currentPlan && action.payload.final_plan) {
          state.currentPlan.final_plan = action.payload.final_plan;
          state.currentPlan.status = 'reviewing';
        }
      })
      .addCase(assemblePlan.rejected, (state, action) => { state.isLoading = false; state.error = action.payload as string; });

    // generatePresentation
    builder
      .addCase(generatePresentation.pending, (state) => { state.isGeneratingPresentation = true; state.error = null; })
      .addCase(generatePresentation.fulfilled, (state, action) => {
        state.isGeneratingPresentation = false;
        if (state.currentPlan && action.payload.slides) {
          state.currentPlan.presentation_slides = { slides: action.payload.slides };
        }
      })
      .addCase(generatePresentation.rejected, (state, action) => { state.isGeneratingPresentation = false; state.error = action.payload as string; });
  },
});

export const { clearPlan, setError } = sbpSlice.actions;
export default sbpSlice.reducer;
