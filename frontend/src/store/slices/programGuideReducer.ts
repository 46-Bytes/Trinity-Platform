import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

/**
 * The authored sections of a module card.
 *
 * Every field below is served by GET /api/program-guide/engagements/{id} and
 * always was - this interface simply declared four of them and dropped the
 * rest on the floor. Names are snake_case because they mirror the FastAPI
 * response verbatim, which is the convention this slice already follows.
 *
 * The nested shapes are JSONB on the backend and typed `Dict[str, Any]` in
 * Pydantic, so nothing validates them server-side. They are written out in full
 * here because this file is the only place their shape is stated at all.
 */

/** A question group inside an agenda item. `label` is present on only a few. */
export interface AgendaQuestionGroup {
  label?: string | null;
  items: string[];
}

/** A term/definition pair, used where an agenda step branches by business shape. */
export interface AgendaOption {
  key: string;
  term: string;
  definition: string;
}

export interface SessionAgendaItem {
  key: string;
  title: string;
  duration?: string | null;
  intro?: string | null;
  detail?: string | null;
  questions?: AgendaQuestionGroup[] | null;
  options?: AgendaOption[] | null;
  note?: string | null;
}

export interface ModuleSession {
  key: string;
  title: string;
  duration?: string | null;
  format?: string | null;
  note?: string | null;
  agenda: SessionAgendaItem[];
}

/** Where an input comes from. The three literals are authored, not derived. */
export type RequiredInputSource = 'Held in Trinity' | 'Advisor to upload' | 'From an earlier module';

export interface RequiredInput {
  key: string;
  label: string;
  source: RequiredInputSource | string;
  source_note?: string | null;
  /** Part A's "stated fallback" for an input from a module that may not have run. */
  fallback?: string | null;
}

/**
 * A note attached to the module, or to one section of it.
 *
 * `title` and `section` are independently optional: a note may be titled or
 * not, and belong to a named section or to the module as a whole. An untitled
 * note with no section renders as loose prose.
 */
export interface ModuleNote {
  key: string;
  title?: string | null;
  section?: string | null;
  text: string;
  items?: string[] | null;
}

/** A reference matrix. Cells align to columns by index. */
export interface ModuleTable {
  key: string;
  title?: string | null;
  intro?: string | null;
  section?: string | null;
  columns: Array<{ key: string; label: string }>;
  rows: Array<{ key: string; label: string; cells: string[] }>;
}

export interface RecommendedTool {
  tool_key: string;
  label: string;
  /** 'pre' | 'post' | 'pre, post' | 'between sessions' - free text. */
  when?: string | null;
  /** 'Existing Trinity tool' | 'To build, Feature 3'. Drives the pending badge. */
  status?: string | null;
}

/** An owner-and-duration block with a list of actions. */
export interface OwnedActionBlock {
  owner?: string | null;
  duration?: string | null;
  items?: string[] | null;
}

export interface ProgramGuideModule {
  id: string;
  program_type: string;
  module_code: string;
  display_order: number;
  title: string;
  focus?: string | null;
  purpose?: string | null;
  core_outcomes?: string[] | null;
  required_inputs?: RequiredInput[] | null;
  preparation_summary?: Omit<OwnedActionBlock, 'items'> | null;
  preparation_checklist?: Array<{ key: string; text: string }> | null;
  sessions?: ModuleSession[] | null;
  between_sessions?: OwnedActionBlock | null;
  post_session_actions?: OwnedActionBlock | null;
  recommended_tools?: RecommendedTool[] | null;
  guardrails?: { must_not?: string[] | null; note?: string | null } | null;
  quality_standards?: string[] | null;
  notes?: ModuleNote[] | null;
  tables?: ModuleTable[] | null;
  /**
   * Display-only titles derived by the seed script. The deliverables the status
   * engine reads come from /api/deliverables - see deliverablesReducer.
   */
  deliverables?: string[] | null;
  is_active: boolean;
  effective_rank?: number | null;
}

export interface ProgramGuideView {
  program_type: string;
  order_source: 'diagnostic' | 'custom' | 'default' | 'unsupported';
  /** The completed diagnostic whose module scores set the order. */
  source_diagnostic_id?: string | null;
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

export interface ModuleInsight {
  module_code: string;
  module_name: string;
  score?: number | null;
  rag?: 'Red' | 'Amber' | 'Green' | null;
  severity?: 'Critical' | 'High' | 'Moderate' | 'Low' | 'Strong' | null;
  answered_questions?: number | null;
  effective_rank?: number | null;
}

/**
 * The diagnostic layer of the guide.
 *
 * `has_scores` is false until the engagement has a completed diagnostic, which
 * is an ordinary state rather than a failure. `modules` always carries all
 * eleven entries regardless, with nulls where nothing was measured - a module
 * with no score reports null, never 0.
 */
export interface ProgramGuideInsights {
  program_type: string;
  has_scores: boolean;
  diagnostic_id?: string | null;
  diagnostic_completed_at?: string | null;
  overall_score?: number | null;
  modules: ModuleInsight[];
}

interface ProgramGuideState {
  view: ProgramGuideView | null;
  valueMovement: ValueMovement | null;
  insights: ProgramGuideInsights | null;
  isLoading: boolean;
  isReordering: boolean;
  error: string | null;
}

const initialState: ProgramGuideState = {
  view: null,
  valueMovement: null,
  insights: null,
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

export const fetchModuleInsights = createAsyncThunk(
  'programGuide/fetchInsights',
  async (engagementId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/program-guide/engagements/${engagementId}/insights`, {
        headers: getAuthHeaders(),
        credentials: 'include',
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to load diagnostic insights' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to load diagnostic insights`);
      }
      return (await response.json()) as ProgramGuideInsights;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to load diagnostic insights');
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
      state.insights = null;
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
      })
      .addCase(fetchModuleInsights.fulfilled, (state, action: PayloadAction<ProgramGuideInsights>) => {
        state.insights = action.payload;
      })
      // Deliberately does not set state.error. Insights are supplementary - an
      // engagement with no completed diagnostic is a normal state, not a
      // failure, and surfacing it as a page-level error would bury a module
      // list that is otherwise perfectly readable.
      .addCase(fetchModuleInsights.rejected, (state) => {
        state.insights = null;
      });
  },
});

export const { clearError, clearProgramGuide } = programGuideSlice.actions;
export default programGuideSlice.reducer;
