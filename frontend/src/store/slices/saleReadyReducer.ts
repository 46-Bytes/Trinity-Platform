import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// ---- Types ----
export type StageType = 'pre_module' | 'module' | 'post_module';
export type StageStatus = 'not_started' | 'in_progress' | 'complete';

export interface SaleReadyStage {
  id: string;
  program_type: string;
  stage_code: string;
  stage_type: StageType;
  default_order: number;
  title: string;
  description?: string | null;
  is_active: boolean;
  status: StageStatus;
  start_date?: string | null;
  due_date?: string | null;
  lead_advisor_id?: string | null;
  priority_order?: number | null;
}

export interface DDItem {
  id: string;
  engagement_id: string;
  module_code: string;
  category: string;
  sub_item?: string | null;
  document_required?: string | null;
  action_step?: string | null;
  responsible_user_id?: string | null;
  completed: boolean;
  date_completed?: string | null;
  notes?: string | null;
  media_id?: string | null;
  file_link?: string | null;
  display_order: number;
}

export interface DocumentEntry {
  id: string;
  engagement_id: string;
  stage_code: string;
  document_name: string;
  creation_date?: string | null;
  document_id?: string | null;
  renewal_date?: string | null;
  renewal_cost?: number | null;
  notes?: string | null;
  media_id?: string | null;
  file_link?: string | null;
}

interface SaleReadyState {
  stages: SaleReadyStage[];
  ddItems: DDItem[];
  documents: DocumentEntry[];
  isLoading: boolean;
  isReordering: boolean;
  error: string | null;
}

const initialState: SaleReadyState = {
  stages: [],
  ddItems: [],
  documents: [],
  isLoading: false,
  isReordering: false,
  error: null,
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const BASE = `${API_BASE_URL}/api/sale-ready`;

const getAuthHeaders = () => ({
  Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
  'Content-Type': 'application/json',
});

async function request<T>(url: string, init: RequestInit, fallbackMsg: string): Promise<T> {
  const response = await fetch(url, { headers: getAuthHeaders(), credentials: 'include', ...init });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: fallbackMsg }));
    throw new Error(errorData.detail || `HTTP ${response.status}: ${fallbackMsg}`);
  }
  if (response.status === 204) return undefined as unknown as T;
  return (await response.json()) as T;
}

// ---- Read thunks (state holders) ----
export const fetchStages = createAsyncThunk('saleReady/fetchStages', async (engagementId: string, { rejectWithValue }) => {
  try {
    const data = await request<{ stages: SaleReadyStage[] }>(`${BASE}/engagements/${engagementId}/stages`, {}, 'Failed to load stages');
    return data.stages;
  } catch (e) {
    return rejectWithValue(e instanceof Error ? e.message : 'Failed to load stages');
  }
});

export const fetchDDItems = createAsyncThunk('saleReady/fetchDDItems', async (engagementId: string, { rejectWithValue }) => {
  try {
    return await request<DDItem[]>(`${BASE}/engagements/${engagementId}/dd-items`, {}, 'Failed to load DD items');
  } catch (e) {
    return rejectWithValue(e instanceof Error ? e.message : 'Failed to load DD items');
  }
});

export const fetchDocuments = createAsyncThunk('saleReady/fetchDocuments', async (engagementId: string, { rejectWithValue }) => {
  try {
    return await request<DocumentEntry[]>(`${BASE}/engagements/${engagementId}/documents`, {}, 'Failed to load documents');
  } catch (e) {
    return rejectWithValue(e instanceof Error ? e.message : 'Failed to load documents');
  }
});

// ---- Mutation thunks (component re-dispatches the relevant fetch on success) ----
export const updateStage = createAsyncThunk(
  'saleReady/updateStage',
  async (
    { engagementId, stageCode, updates }: { engagementId: string; stageCode: string; updates: Partial<Pick<SaleReadyStage, 'status' | 'start_date' | 'due_date' | 'lead_advisor_id'>> },
    { dispatch, rejectWithValue },
  ) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/stages/${stageCode}`, { method: 'PATCH', body: JSON.stringify(updates) }, 'Failed to update stage');
      dispatch(fetchStages(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to update stage');
    }
  },
);

export const setModuleOrder = createAsyncThunk(
  'saleReady/setModuleOrder',
  async ({ engagementId, moduleOrder }: { engagementId: string; moduleOrder: string[] }, { dispatch, rejectWithValue }) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/order`, { method: 'PUT', body: JSON.stringify({ module_order: moduleOrder }) }, 'Failed to reorder modules');
      dispatch(fetchStages(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to reorder modules');
    }
  },
);

export const applyRecommendedOrder = createAsyncThunk(
  'saleReady/applyRecommendedOrder',
  async (engagementId: string, { dispatch, rejectWithValue }) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/order/recommended`, { method: 'POST' }, 'Failed to apply recommended order');
      dispatch(fetchStages(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to apply recommended order');
    }
  },
);

export const createDDItem = createAsyncThunk(
  'saleReady/createDDItem',
  async ({ engagementId, data }: { engagementId: string; data: Partial<DDItem> }, { dispatch, rejectWithValue }) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/dd-items`, { method: 'POST', body: JSON.stringify(data) }, 'Failed to create DD item');
      dispatch(fetchDDItems(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to create DD item');
    }
  },
);

export const updateDDItem = createAsyncThunk(
  'saleReady/updateDDItem',
  async ({ engagementId, itemId, updates }: { engagementId: string; itemId: string; updates: Partial<DDItem> }, { dispatch, rejectWithValue }) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/dd-items/${itemId}`, { method: 'PATCH', body: JSON.stringify(updates) }, 'Failed to update DD item');
      dispatch(fetchDDItems(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to update DD item');
    }
  },
);

export const deleteDDItem = createAsyncThunk(
  'saleReady/deleteDDItem',
  async ({ engagementId, itemId }: { engagementId: string; itemId: string }, { dispatch, rejectWithValue }) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/dd-items/${itemId}`, { method: 'DELETE' }, 'Failed to delete DD item');
      dispatch(fetchDDItems(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to delete DD item');
    }
  },
);

export const createDocument = createAsyncThunk(
  'saleReady/createDocument',
  async ({ engagementId, data }: { engagementId: string; data: Partial<DocumentEntry> }, { dispatch, rejectWithValue }) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/documents`, { method: 'POST', body: JSON.stringify(data) }, 'Failed to create document');
      dispatch(fetchDocuments(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to create document');
    }
  },
);

export const updateDocument = createAsyncThunk(
  'saleReady/updateDocument',
  async ({ engagementId, entryId, updates }: { engagementId: string; entryId: string; updates: Partial<DocumentEntry> }, { dispatch, rejectWithValue }) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/documents/${entryId}`, { method: 'PATCH', body: JSON.stringify(updates) }, 'Failed to update document');
      dispatch(fetchDocuments(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to update document');
    }
  },
);

export const deleteDocument = createAsyncThunk(
  'saleReady/deleteDocument',
  async ({ engagementId, entryId }: { engagementId: string; entryId: string }, { dispatch, rejectWithValue }) => {
    try {
      await request(`${BASE}/engagements/${engagementId}/documents/${entryId}`, { method: 'DELETE' }, 'Failed to delete document');
      dispatch(fetchDocuments(engagementId));
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to delete document');
    }
  },
);

const saleReadySlice = createSlice({
  name: 'saleReady',
  initialState,
  reducers: {
    clearSaleReady: (state) => {
      state.stages = [];
      state.ddItems = [];
      state.documents = [];
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchStages.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchStages.fulfilled, (state, action: PayloadAction<SaleReadyStage[]>) => {
        state.isLoading = false;
        state.stages = action.payload;
      })
      .addCase(fetchStages.rejected, (state, action) => {
        state.isLoading = false;
        state.error = (action.payload as string) || 'Failed to load stages';
      })
      .addCase(fetchDDItems.fulfilled, (state, action: PayloadAction<DDItem[]>) => {
        state.ddItems = action.payload;
      })
      .addCase(fetchDocuments.fulfilled, (state, action: PayloadAction<DocumentEntry[]>) => {
        state.documents = action.payload;
      })
      .addCase(setModuleOrder.pending, (state) => {
        state.isReordering = true;
      })
      .addCase(setModuleOrder.fulfilled, (state) => {
        state.isReordering = false;
      })
      .addCase(setModuleOrder.rejected, (state, action) => {
        state.isReordering = false;
        state.error = (action.payload as string) || 'Failed to reorder modules';
      })
      .addCase(applyRecommendedOrder.pending, (state) => {
        state.isReordering = true;
      })
      .addCase(applyRecommendedOrder.fulfilled, (state) => {
        state.isReordering = false;
      })
      .addCase(applyRecommendedOrder.rejected, (state, action) => {
        state.isReordering = false;
        state.error = (action.payload as string) || 'Failed to apply recommended order';
      });
  },
});

export const { clearSaleReady } = saleReadySlice.actions;
export default saleReadySlice.reducer;
