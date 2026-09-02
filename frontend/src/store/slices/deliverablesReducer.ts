/**
 * Deliverables slice.
 *
 * The backend for this has been complete and unconsumed since the deliverables
 * API landed: six endpoints, a derived module status, and nothing in the
 * frontend calling any of it. This is that missing half.
 *
 * Two things shape the design.
 *
 * Every endpoint - reads and mutations alike - returns the whole DeliverableView,
 * so every fulfilled case simply replaces state. There is no patching, and
 * therefore no way for the client's idea of a module's status to drift from the
 * server's derivation of it. Module status is never computed here.
 *
 * `deliverable_id` is polymorphic. For a preset it is the LIBRARY row id, because
 * an untouched preset has no per-engagement instance and so no instance id; for
 * an advisor-added deliverable it is the instance id. Both are addressed
 * identically in the URL, and `source` says which one is in hand.
 */
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

export type DeliverableSource = 'preset' | 'advisor';
export type ModuleStatus = 'not_started' | 'in_progress' | 'completed';

export interface DeliverableItem {
  deliverable_id: string;
  source: DeliverableSource;
  title: string;
  description?: string | null;
  is_mandatory: boolean;
  /** False means scoped out: retained on the engagement but excluded from completion. */
  is_in_scope: boolean;
  is_complete: boolean;
  /**
   * Tasks generated from this deliverable. Display only - a task's status never
   * moves is_complete, and completing a deliverable never touches its tasks.
   */
  task_count: number;
}

export interface ModuleDeliverables {
  module_code: string;
  status: ModuleStatus;
  deliverables: DeliverableItem[];
}

export interface DeliverableView {
  engagement_id: string;
  program_type: string;
  /**
   * Only modules that have at least one deliverable, and ordered by module_code
   * as a STRING - so 'M0, M12, V1, V10, V11, V2...', not program order. Read it
   * by code via selectModuleDeliverables; never render this array as given.
   */
  modules: ModuleDeliverables[];
}

export interface TaskGenerationResult {
  created_count: number;
  skipped_count: number;
  view: DeliverableView;
}

interface DeliverablesState {
  view: DeliverableView | null;
  isLoading: boolean;
  /** Ids with a mutation in flight, so one row can spin without disabling the rest. */
  pendingIds: string[];
  /** Module codes with a task generation in flight. */
  generatingModules: string[];
  error: string | null;
}

const initialState: DeliverablesState = {
  view: null,
  isLoading: false,
  pendingIds: [],
  generatingModules: [],
  error: null,
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const getAuthHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
  'Content-Type': 'application/json',
});

/**
 * FastAPI answers errors as `{ detail }`, but not every failure has a JSON body
 * - a 502 from a proxy does not. The catch keeps a non-JSON response from
 * throwing a parse error over the top of the real status.
 */
async function request<T>(path: string, init: RequestInit, fallback: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: fallback }));
    throw new Error(errorData.detail || `HTTP ${response.status}: ${fallback}`);
  }
  return (await response.json()) as T;
}

const base = (engagementId: string) => `/api/deliverables/engagements/${engagementId}`;

export const fetchDeliverables = createAsyncThunk(
  'deliverables/fetch',
  async (engagementId: string, { rejectWithValue }) => {
    try {
      return await request<DeliverableView>(base(engagementId), {}, 'Failed to load deliverables');
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to load deliverables');
    }
  }
);

export const setDeliverableComplete = createAsyncThunk(
  'deliverables/setComplete',
  async (
    { engagementId, deliverableId, isComplete }: { engagementId: string; deliverableId: string; isComplete: boolean },
    { rejectWithValue }
  ) => {
    try {
      return await request<DeliverableView>(
        `${base(engagementId)}/items/${deliverableId}/complete`,
        { method: 'PUT', body: JSON.stringify({ is_complete: isComplete }) },
        'Failed to update the deliverable'
      );
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update the deliverable');
    }
  }
);

export const setDeliverableScope = createAsyncThunk(
  'deliverables/setScope',
  async (
    { engagementId, deliverableId, isInScope }: { engagementId: string; deliverableId: string; isInScope: boolean },
    { rejectWithValue }
  ) => {
    try {
      return await request<DeliverableView>(
        `${base(engagementId)}/items/${deliverableId}/scope`,
        { method: 'PUT', body: JSON.stringify({ is_in_scope: isInScope }) },
        'Failed to change the deliverable scope'
      );
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to change the deliverable scope');
    }
  }
);

export const addAdvisorDeliverable = createAsyncThunk(
  'deliverables/add',
  async (
    {
      engagementId,
      moduleCode,
      title,
      isMandatory,
      description,
    }: {
      engagementId: string;
      moduleCode: string;
      title: string;
      isMandatory: boolean;
      description?: string | null;
    },
    { rejectWithValue }
  ) => {
    try {
      return await request<DeliverableView>(
        `${base(engagementId)}/items`,
        {
          method: 'POST',
          body: JSON.stringify({
            module_code: moduleCode,
            title,
            is_mandatory: isMandatory,
            description: description || null,
          }),
        },
        'Failed to add the deliverable'
      );
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to add the deliverable');
    }
  }
);

export const updateAdvisorDeliverable = createAsyncThunk(
  'deliverables/update',
  async (
    {
      engagementId,
      deliverableId,
      fields,
    }: {
      engagementId: string;
      deliverableId: string;
      /**
       * Sent as given, so omitting a key leaves it unchanged server-side. Do
       * not send an explicit null for title or is_mandatory - the service
       * rejects nulling a required field with a 400.
       */
      fields: { title?: string; description?: string | null; is_mandatory?: boolean };
    },
    { rejectWithValue }
  ) => {
    try {
      return await request<DeliverableView>(
        `${base(engagementId)}/items/${deliverableId}`,
        { method: 'PATCH', body: JSON.stringify(fields) },
        'Failed to update the deliverable'
      );
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update the deliverable');
    }
  }
);

export const removeAdvisorDeliverable = createAsyncThunk(
  'deliverables/remove',
  async (
    { engagementId, deliverableId }: { engagementId: string; deliverableId: string },
    { rejectWithValue }
  ) => {
    try {
      return await request<DeliverableView>(
        `${base(engagementId)}/items/${deliverableId}`,
        { method: 'DELETE' },
        'Failed to remove the deliverable'
      );
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to remove the deliverable');
    }
  }
);

export const generateModuleTasks = createAsyncThunk(
  'deliverables/generateTasks',
  async (
    { engagementId, moduleCode }: { engagementId: string; moduleCode: string },
    { rejectWithValue }
  ) => {
    try {
      return await request<TaskGenerationResult>(
        `${base(engagementId)}/modules/${moduleCode}/tasks`,
        { method: 'POST' },
        'Failed to create tasks'
      );
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create tasks');
    }
  }
);

/** Every mutation answers with the full view, so they all settle the same way. */
const MUTATIONS = [
  setDeliverableComplete,
  setDeliverableScope,
  addAdvisorDeliverable,
  updateAdvisorDeliverable,
  removeAdvisorDeliverable,
];

const deliverablesSlice = createSlice({
  name: 'deliverables',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    clearDeliverables: (state) => {
      state.view = null;
      state.pendingIds = [];
      state.generatingModules = [];
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchDeliverables.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchDeliverables.fulfilled, (state, action: PayloadAction<DeliverableView>) => {
        state.isLoading = false;
        state.view = action.payload;
      })
      .addCase(fetchDeliverables.rejected, (state, action) => {
        state.isLoading = false;
        state.error = (action.payload as string) || 'Failed to load deliverables';
      })
      .addCase(generateModuleTasks.pending, (state, action) => {
        state.generatingModules.push(action.meta.arg.moduleCode);
        state.error = null;
      })
      // No PayloadAction annotation here: it narrows the action to payload+type
      // and drops `meta`, which is where the module code being settled lives.
      .addCase(generateModuleTasks.fulfilled, (state, action) => {
        state.generatingModules = state.generatingModules.filter(
          (code) => code !== action.meta.arg.moduleCode
        );
        state.view = action.payload.view;
      })
      .addCase(generateModuleTasks.rejected, (state, action) => {
        state.generatingModules = state.generatingModules.filter(
          (code) => code !== action.meta.arg.moduleCode
        );
        state.error = (action.payload as string) || 'Failed to create tasks';
      });

    // Registered in a loop because all five behave identically: track the row
    // as pending, then replace the whole view. Writing them out five times
    // would be five chances for one to drift.
    MUTATIONS.forEach((thunk) => {
      builder
        .addCase(thunk.pending, (state, action) => {
          const id = (action.meta.arg as { deliverableId?: string }).deliverableId;
          if (id) state.pendingIds.push(id);
          state.error = null;
        })
        .addCase(thunk.fulfilled, (state, action) => {
          const id = (action.meta.arg as { deliverableId?: string }).deliverableId;
          if (id) state.pendingIds = state.pendingIds.filter((pending) => pending !== id);
          state.view = action.payload as DeliverableView;
        })
        .addCase(thunk.rejected, (state, action) => {
          const id = (action.meta.arg as { deliverableId?: string }).deliverableId;
          if (id) state.pendingIds = state.pendingIds.filter((pending) => pending !== id);
          state.error = (action.payload as string) || 'Failed to update the deliverable';
        });
    });
  },
});

export const { clearError, clearDeliverables } = deliverablesSlice.actions;
export default deliverablesSlice.reducer;
