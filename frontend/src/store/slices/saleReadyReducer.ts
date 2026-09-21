import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

import type {
  Closeout,
  CloseoutUpdate,
  DDChecklist,
  DDItem,
  DDItemUpdate,
  DDStats,
  SalePlanner,
  SalePlannerUpdate,
  SaleReadyRoadmap,
  StageDetail,
  StageTaskUpdate,
  StageUpdate,
} from '@/components/engagement/sale-ready/types';

interface SaleReadyState {
  roadmap: SaleReadyRoadmap | null;
  checklist: DDChecklist | null;
  stage: StageDetail | null;
  salePlanner: SalePlanner | null;
  closeout: Closeout | null;
  isLoadingRoadmap: boolean;
  isLoadingChecklist: boolean;
  isLoadingStage: boolean;
  isReordering: boolean;
  /** A stage action (start, complete, reopen, edits) is in flight. */
  isSaving: boolean;
  error: string | null;
}

const initialState: SaleReadyState = {
  roadmap: null,
  checklist: null,
  stage: null,
  salePlanner: null,
  closeout: null,
  isLoadingRoadmap: false,
  isLoadingChecklist: false,
  isLoadingStage: false,
  isReordering: false,
  isSaving: false,
  error: null,
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const getAuthHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
  'Content-Type': 'application/json',
});

async function request<T>(path: string, fallback: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/sale-ready/engagements/${path}`, {
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

function thunk<Arg, T>(type: string, fallback: string, call: (arg: Arg) => Promise<T>) {
  return createAsyncThunk<T, Arg, { rejectValue: string }>(`saleReady/${type}`, async (arg, { rejectWithValue }) => {
    try {
      return await call(arg);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : fallback);
    }
  });
}

// ---------------------------------------------------------------- roadmap
export const fetchSaleReadyRoadmap = thunk('fetchRoadmap', 'Failed to load the Sale Ready roadmap',
  (engagementId: string) =>
    request<SaleReadyRoadmap>(`${engagementId}/roadmap`, 'Failed to load the Sale Ready roadmap'));

export const reorderSaleReadyModules = thunk('reorder', 'Failed to reorder modules',
  ({ engagementId, moduleOrder }: { engagementId: string; moduleOrder: string[] }) =>
    request<SaleReadyRoadmap>(`${engagementId}/order`, 'Failed to reorder modules', {
      method: 'PUT',
      body: JSON.stringify({ module_order: moduleOrder }),
    }));

export const resetSaleReadyOrder = thunk('resetOrder', 'Failed to reset the module order',
  (engagementId: string) =>
    request<SaleReadyRoadmap>(`${engagementId}/order/reset`, 'Failed to reset the module order', { method: 'POST' }));

// ---------------------------------------------------------------- stages
type StageArg = { engagementId: string; stageCode: string };

export const fetchStageDetail = thunk('fetchStage', 'Failed to load the stage',
  ({ engagementId, stageCode }: StageArg) =>
    request<StageDetail>(`${engagementId}/stages/${stageCode}`, 'Failed to load the stage'));

export const updateStage = thunk('updateStage', 'Failed to update the stage',
  ({ engagementId, stageCode, changes }: StageArg & { changes: StageUpdate }) =>
    request<StageDetail>(`${engagementId}/stages/${stageCode}`, 'Failed to update the stage', {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }));

const stageAction = (action: 'start' | 'complete' | 'reopen', fallback: string) =>
  thunk(`${action}Stage`, fallback, ({ engagementId, stageCode }: StageArg) =>
    request<StageDetail>(`${engagementId}/stages/${stageCode}/${action}`, fallback, { method: 'POST' }));

export const startStage = stageAction('start', 'Failed to start the stage');
export const completeStage = stageAction('complete', 'Failed to mark the stage complete');
export const reopenStage = stageAction('reopen', 'Failed to reopen the stage');

export const addStageTask = thunk('addTask', 'Failed to add the task',
  ({ engagementId, stageCode, title }: StageArg & { title: string }) =>
    request<StageDetail>(`${engagementId}/stages/${stageCode}/tasks`, 'Failed to add the task', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }));

export const updateStageTask = thunk('updateTask', 'Failed to update the task',
  ({ engagementId, taskId, changes }: { engagementId: string; taskId: string; changes: StageTaskUpdate }) =>
    request<StageDetail>(`${engagementId}/tasks/${taskId}`, 'Failed to update the task', {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }));

// ---------------------------------------------------------------- DD checklist
export const fetchDDChecklist = thunk('fetchDD', 'Failed to load the due diligence checklist',
  (engagementId: string) =>
    request<DDChecklist>(`${engagementId}/dd`, 'Failed to load the due diligence checklist'));

export const updateDDItem = thunk('updateDD', 'Failed to update the DD item',
  ({ engagementId, itemId, changes }: { engagementId: string; itemId: string; changes: DDItemUpdate }) =>
    request<DDItem>(`${engagementId}/dd/${itemId}`, 'Failed to update the DD item', {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }));

// ---------------------------------------------------------------- Sale Planner and Close-out
export const fetchSalePlanner = thunk('fetchSalePlanner', 'Failed to load the Sale Planner',
  (engagementId: string) => request<SalePlanner>(`${engagementId}/sale-planner`, 'Failed to load the Sale Planner'));

export const updateSalePlanner = thunk('updateSalePlanner', 'Failed to save the Sale Planner',
  ({ engagementId, changes }: { engagementId: string; changes: SalePlannerUpdate }) =>
    request<SalePlanner>(`${engagementId}/sale-planner`, 'Failed to save the Sale Planner', {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }));

export const fetchCloseout = thunk('fetchCloseout', 'Failed to load the close-out',
  (engagementId: string) => request<Closeout>(`${engagementId}/closeout`, 'Failed to load the close-out'));

export const updateCloseout = thunk('updateCloseout', 'Failed to save the close-out',
  ({ engagementId, changes }: { engagementId: string; changes: CloseoutUpdate }) =>
    request<Closeout>(`${engagementId}/closeout`, 'Failed to save the close-out', {
      method: 'PATCH',
      body: JSON.stringify(changes),
    }));

export const closeProgram = thunk('closeProgram', 'Failed to close the program',
  ({ engagementId, changes, confirmWithoutReferral }: {
    engagementId: string;
    changes: CloseoutUpdate;
    confirmWithoutReferral: boolean;
  }) =>
    request<Closeout>(`${engagementId}/closeout/close`, 'Failed to close the program', {
      method: 'POST',
      body: JSON.stringify({ ...changes, confirm_without_referral: confirmWithoutReferral }),
    }));

export const reopenProgram = thunk('reopenProgram', 'Failed to reopen the program',
  (engagementId: string) =>
    request<Closeout>(`${engagementId}/closeout/reopen`, 'Failed to reopen the program', { method: 'POST' }));

/** Same counts as the server's DDStats, recomputed after an in-place edit. */
function statsOf(items: DDItem[]): DDStats {
  const count = (status: DDItem['status']) => items.filter((i) => i.status === status).length;
  return {
    total: items.length,
    yes: count('yes'),
    in_progress: count('in_progress'),
    no: count('no'),
    not_applicable: count('not_applicable'),
    no_status: count(null),
    flagged: items.filter((i) => i.flag_for_m8).length,
    referred: items.filter((i) => i.status === 'no' && i.gap_handling === 'refer').length,
  };
}

const replaceItem = (items: DDItem[], item: DDItem) => items.map((i) => (i.id === item.id ? item : i));

const stageMutations = [updateStage, startStage, completeStage, reopenStage, addStageTask, updateStageTask];

const saleReadySlice = createSlice({
  name: 'saleReady',
  initialState,
  reducers: {
    clearSaleReady: () => initialState,
    closeStage: (state) => {
      state.stage = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchSaleReadyRoadmap.pending, (state) => {
        state.isLoadingRoadmap = true;
        state.error = null;
      })
      .addCase(fetchSaleReadyRoadmap.fulfilled, (state, action) => {
        state.isLoadingRoadmap = false;
        state.roadmap = action.payload;
      })
      .addCase(fetchSaleReadyRoadmap.rejected, (state, action) => {
        state.isLoadingRoadmap = false;
        state.error = action.payload ?? 'Failed to load the Sale Ready roadmap';
      })
      .addCase(fetchDDChecklist.pending, (state) => {
        state.isLoadingChecklist = true;
        state.error = null;
      })
      .addCase(fetchDDChecklist.fulfilled, (state, action) => {
        state.isLoadingChecklist = false;
        state.checklist = action.payload;
      })
      .addCase(fetchDDChecklist.rejected, (state, action) => {
        state.isLoadingChecklist = false;
        state.error = action.payload ?? 'Failed to load the due diligence checklist';
      })
      .addCase(fetchStageDetail.pending, (state) => {
        state.isLoadingStage = true;
        state.error = null;
      })
      .addCase(fetchStageDetail.fulfilled, (state, action) => {
        state.isLoadingStage = false;
        state.stage = action.payload;
      })
      .addCase(fetchStageDetail.rejected, (state, action) => {
        state.isLoadingStage = false;
        state.error = action.payload ?? 'Failed to load the stage';
      })
      // One DD record, shown in the master list and in its stage: patch both.
      .addCase(updateDDItem.fulfilled, (state, action) => {
        const item = action.payload;
        if (state.checklist) {
          state.checklist.items = replaceItem(state.checklist.items, item);
          state.checklist.stats = statsOf(state.checklist.items);
        }
        if (state.stage) {
          state.stage.dd_items = replaceItem(state.stage.dd_items, item);
          if (state.stage.stage.is_pinned_last) {
            const others = state.stage.flagged_for_review.filter((i) => i.id !== item.id);
            state.stage.flagged_for_review = item.flag_for_m8 ? [...others, item] : others;
          }
        }
      });

    builder
      .addCase(reorderSaleReadyModules.pending, (state) => {
        state.isReordering = true;
      })
      .addCase(resetSaleReadyOrder.pending, (state) => {
        state.isReordering = true;
      });
    for (const t of [reorderSaleReadyModules, resetSaleReadyOrder]) {
      builder
        .addCase(t.fulfilled, (state, action) => {
          state.isReordering = false;
          state.roadmap = action.payload;
        })
        .addCase(t.rejected, (state) => {
          state.isReordering = false;
        });
    }

    for (const t of [fetchSalePlanner, updateSalePlanner]) {
      builder.addCase(t.fulfilled, (state, action) => {
        state.salePlanner = action.payload;
      });
    }
    for (const t of [fetchCloseout, updateCloseout]) {
      builder.addCase(t.fulfilled, (state, action) => {
        state.closeout = action.payload;
      });
    }
    for (const t of [closeProgram, reopenProgram]) {
      builder
        .addCase(t.pending, (state) => {
          state.isSaving = true;
        })
        .addCase(t.fulfilled, (state, action) => {
          state.isSaving = false;
          state.closeout = action.payload;
        })
        .addCase(t.rejected, (state) => {
          state.isSaving = false;
        });
    }

    for (const t of stageMutations) {
      builder
        .addCase(t.pending, (state) => {
          state.isSaving = true;
        })
        .addCase(t.fulfilled, (state, action) => {
          state.isSaving = false;
          state.stage = action.payload;
        })
        .addCase(t.rejected, (state) => {
          state.isSaving = false;
        });
    }
  },
});

export const { clearSaleReady, closeStage } = saleReadySlice.actions;
export default saleReadySlice.reducer;
