import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

export interface ProgramGuideModule {
  id: string;
  program_type: string;
  module_code: string;
  display_order: number;
  title: string;
  purpose?: string | null;
  preparation_checklist?: Array<{ key: string; text: string }> | null;
  recommended_tools?: Array<{ tool_key: string; label: string }> | null;
  deliverables?: string[] | null;
  is_active: boolean;
  effective_rank?: number | null;
  is_gateway: boolean;
  is_capstone: boolean;
}

export interface ProgramGuideView {
  program_type: string;
  order_source: 'bba' | 'custom' | 'default' | 'unsupported';
  source_bba_id?: string | null;
  unmapped_priority_areas: string[];
  custom_order_set_at?: string | null;
  custom_order_set_by_user_id?: string | null;
  modules: ProgramGuideModule[];
}

export interface ModuleMovement {
  module_code: string;
  module_name: string;
  previous_score?: number | null;
  current_score?: number | null;
  delta?: number | null;
  previous_rag?: string | null;
  current_rag?: string | null;
}

export interface ValueMovement {
  has_comparison: boolean;
  previous_diagnostic_id?: string | null;
  current_diagnostic_id?: string | null;
  overall_score_previous?: number | null;
  overall_score_current?: number | null;
  overall_score_delta?: number | null;
  module_movements: ModuleMovement[];
}

interface ProgramGuideState {
  view: ProgramGuideView | null;
  valueMovement: ValueMovement | null;
  isLoading: boolean;
  isReordering: boolean;
  error: string | null;
}

const initialState: ProgramGuideState = {
  view: null,
  valueMovement: null,
  isLoading: false,
  isReordering: false,
  error: null,
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const getAuthHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
  'Content-Type': 'application/json',
});

export const fetchProgramGuide = createAsyncThunk(
  'programGuide/fetch',
  async (engagementId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/program-guide/engagements/${engagementId}`, {
        headers: getAuthHeaders(),
        credentials: 'include',
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to load Program Guide' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to load Program Guide`);
      }
      return (await response.json()) as ProgramGuideView;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to load Program Guide');
    }
  }
);

export const reorderModules = createAsyncThunk(
  'programGuide/reorder',
  async ({ engagementId, moduleOrder }: { engagementId: string; moduleOrder: string[] }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/program-guide/engagements/${engagementId}/order`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        credentials: 'include',
        body: JSON.stringify({ module_order: moduleOrder }),
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to reorder modules' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to reorder modules`);
      }
      return (await response.json()) as ProgramGuideView;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to reorder modules');
    }
  }
);

export const resetModuleOrder = createAsyncThunk(
  'programGuide/resetOrder',
  async (engagementId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/program-guide/engagements/${engagementId}/order/reset`, {
        method: 'POST',
        headers: getAuthHeaders(),
        credentials: 'include',
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to reset module order' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to reset module order`);
      }
      return (await response.json()) as ProgramGuideView;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to reset module order');
    }
  }
);

export const fetchValueMovement = createAsyncThunk(
  'programGuide/fetchValueMovement',
  async (engagementId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/program-guide/engagements/${engagementId}/value-movement`, {
        headers: getAuthHeaders(),
        credentials: 'include',
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to load value movement' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to load value movement`);
      }
      return (await response.json()) as ValueMovement;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to load value movement');
    }
  }
);

const programGuideSlice = createSlice({
  name: 'programGuide',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    clearProgramGuide: (state) => {
      state.view = null;
      state.valueMovement = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchProgramGuide.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchProgramGuide.fulfilled, (state, action: PayloadAction<ProgramGuideView>) => {
        state.isLoading = false;
        state.view = action.payload;
      })
      .addCase(fetchProgramGuide.rejected, (state, action) => {
        state.isLoading = false;
        state.error = (action.payload as string) || 'Failed to load Program Guide';
      })
      .addCase(reorderModules.pending, (state) => {
        state.isReordering = true;
        state.error = null;
      })
      .addCase(reorderModules.fulfilled, (state, action: PayloadAction<ProgramGuideView>) => {
        state.isReordering = false;
        state.view = action.payload;
      })
      .addCase(reorderModules.rejected, (state, action) => {
        state.isReordering = false;
        state.error = (action.payload as string) || 'Failed to reorder modules';
      })
      .addCase(resetModuleOrder.pending, (state) => {
        state.isReordering = true;
        state.error = null;
      })
      .addCase(resetModuleOrder.fulfilled, (state, action: PayloadAction<ProgramGuideView>) => {
        state.isReordering = false;
        state.view = action.payload;
      })
      .addCase(resetModuleOrder.rejected, (state, action) => {
        state.isReordering = false;
        state.error = (action.payload as string) || 'Failed to reset module order';
      })
      .addCase(fetchValueMovement.fulfilled, (state, action: PayloadAction<ValueMovement>) => {
        state.valueMovement = action.payload;
      })
      .addCase(fetchValueMovement.rejected, (state, action) => {
        state.error = (action.payload as string) || 'Failed to load value movement';
      });
  },
});

export const { clearError, clearProgramGuide } = programGuideSlice.actions;
export default programGuideSlice.reducer;
