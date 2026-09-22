import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';

/**
 * Sale Ready Management: the master content admins edit for future engagements.
 *
 * Every endpoint here is admin and super admin only, enforced by the backend.
 * Nothing in this slice touches a live engagement - an engagement's tasks, DD
 * items and guide are copies taken when it was created.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const BASE = `${API_BASE_URL}/api/sale-ready/admin`;

export interface StageGuide {
  purpose: string;
  steps: string[];
  watch: string[];
  templates: string[];
  run_with: string | null;
}

export interface AdminStage {
  stage_code: string;
  display_code: string | null;
  stage_type: string;
  title: string;
  description: string | null;
  default_order: number;
  task_creation: string;
  ui_variant: string | null;
  guide: StageGuide;
}

export interface WorkflowStep {
  stage: string;
  label: string;
}

export interface ProgramRule {
  title: string;
  body: string;
}

export interface AdminGuide {
  program: { workflow: WorkflowStep[]; rules: ProgramRule[] };
  stages: AdminStage[];
}

export interface AdminTaskTemplate {
  id: string;
  stage_code: string;
  template_key: string;
  section: 'must_do' | 'optional';
  group_title: string | null;
  title: string;
  description: string | null;
  priority: string;
  default_order: number;
  due_offset_days: number | null;
  is_active: boolean;
}

export interface AdminDDTemplate {
  id: string;
  item_key: string;
  stage_code: string;
  category_code: string;
  category: string;
  sub_item_code: string;
  sub_item: string | null;
  document_required: string | null;
  action_step: string | null;
  default_order: number;
  is_active: boolean;
}

export interface DDCategoryOption {
  category_code: string;
  category: string;
  sub_items: { sub_item_code: string; sub_item: string; stage_code: string }[];
}

interface SaleReadyAdminState {
  guide: AdminGuide | null;
  taskTemplates: AdminTaskTemplate[];
  ddTemplates: AdminDDTemplate[];
  ddCategories: DDCategoryOption[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
}

const initialState: SaleReadyAdminState = {
  guide: null,
  taskTemplates: [],
  ddTemplates: [],
  ddCategories: [],
  isLoading: false,
  isSaving: false,
  error: null,
};

async function request<T>(path: string, fallback: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
    // Matches saleReadyReducer and programGuideReducer: the backend accepts a
    // bearer token or a session cookie, so an admin signed in by cookie works too.
    credentials: 'include',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallback);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const thunk = <Arg, Result>(name: string, fallback: string, run: (arg: Arg) => Promise<Result>) =>
  createAsyncThunk<Result, Arg, { rejectValue: string }>(`saleReadyAdmin/${name}`, async (arg, { rejectWithValue }) => {
    try {
      return await run(arg);
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : fallback);
    }
  });

// ---------------------------------------------------------------- guide
export const fetchAdminGuide = thunk<void, AdminGuide>('fetchGuide', 'Failed to load the program guide', () =>
  request<AdminGuide>('/guide', 'Failed to load the program guide'));

export const updateProgramGuide = thunk<
  { workflow?: WorkflowStep[]; rules?: ProgramRule[] },
  AdminGuide
>('updateProgramGuide', 'Failed to save the program guide', (changes) =>
  request<AdminGuide>('/guide/program', 'Failed to save the program guide', {
    method: 'PATCH',
    body: JSON.stringify(changes),
  }));

export const updateStageGuide = thunk<
  { stageCode: string; changes: Partial<StageGuide> },
  AdminGuide
>('updateStageGuide', 'Failed to save the stage guide', ({ stageCode, changes }) =>
  request<AdminGuide>(`/guide/stages/${stageCode}`, 'Failed to save the stage guide', {
    method: 'PATCH',
    body: JSON.stringify(changes),
  }));

// ------------------------------------------------------- task templates
export const fetchTaskTemplates = thunk<void, AdminTaskTemplate[]>(
  'fetchTaskTemplates', 'Failed to load the task templates',
  () => request<AdminTaskTemplate[]>('/task-templates', 'Failed to load the task templates'));

export const createTaskTemplate = thunk<Record<string, unknown>, AdminTaskTemplate>(
  'createTaskTemplate', 'Failed to add the task template',
  (body) => request<AdminTaskTemplate>('/task-templates', 'Failed to add the task template', {
    method: 'POST', body: JSON.stringify(body),
  }));

export const updateTaskTemplate = thunk<
  { id: string; changes: Record<string, unknown> },
  AdminTaskTemplate
>('updateTaskTemplate', 'Failed to save the task template', ({ id, changes }) =>
  request<AdminTaskTemplate>(`/task-templates/${id}`, 'Failed to save the task template', {
    method: 'PATCH', body: JSON.stringify(changes),
  }));

export const retireTaskTemplate = thunk<string, string>(
  'retireTaskTemplate', 'Failed to remove the task template',
  async (id) => {
    await request<void>(`/task-templates/${id}`, 'Failed to remove the task template', { method: 'DELETE' });
    return id;
  });

export const reorderTaskTemplates = thunk<string[], AdminTaskTemplate[]>(
  'reorderTaskTemplates', 'Failed to reorder the task templates',
  (ids) => request<AdminTaskTemplate[]>('/task-templates/reorder', 'Failed to reorder the task templates', {
    method: 'POST', body: JSON.stringify({ ids }),
  }));

// --------------------------------------------------------- dd templates
export const fetchDDCategories = thunk<void, DDCategoryOption[]>(
  'fetchDDCategories', 'Failed to load the DD categories',
  () => request<DDCategoryOption[]>('/dd-categories', 'Failed to load the DD categories'));

export const fetchDDTemplates = thunk<void, AdminDDTemplate[]>(
  'fetchDDTemplates', 'Failed to load the DD checklist',
  () => request<AdminDDTemplate[]>('/dd-templates', 'Failed to load the DD checklist'));

export const createDDTemplate = thunk<Record<string, unknown>, AdminDDTemplate>(
  'createDDTemplate', 'Failed to add the checklist item',
  (body) => request<AdminDDTemplate>('/dd-templates', 'Failed to add the checklist item', {
    method: 'POST', body: JSON.stringify(body),
  }));

export const updateDDTemplate = thunk<
  { id: string; changes: Record<string, unknown> },
  AdminDDTemplate
>('updateDDTemplate', 'Failed to save the checklist item', ({ id, changes }) =>
  request<AdminDDTemplate>(`/dd-templates/${id}`, 'Failed to save the checklist item', {
    method: 'PATCH', body: JSON.stringify(changes),
  }));

export const retireDDTemplate = thunk<string, string>(
  'retireDDTemplate', 'Failed to remove the checklist item',
  async (id) => {
    await request<void>(`/dd-templates/${id}`, 'Failed to remove the checklist item', { method: 'DELETE' });
    return id;
  });

export const reorderDDTemplates = thunk<string[], AdminDDTemplate[]>(
  'reorderDDTemplates', 'Failed to reorder the checklist',
  (ids) => request<AdminDDTemplate[]>('/dd-templates/reorder', 'Failed to reorder the checklist', {
    method: 'POST', body: JSON.stringify({ ids }),
  }));

function upsert<T extends { id: string }>(list: T[], row: T): T[] {
  const index = list.findIndex((x) => x.id === row.id);
  if (index === -1) return [...list, row];
  const next = [...list];
  next[index] = row;
  return next;
}

const slice = createSlice({
  name: 'saleReadyAdmin',
  initialState,
  reducers: {
    clearSaleReadyAdminError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    for (const t of [fetchAdminGuide, updateProgramGuide, updateStageGuide]) {
      builder.addCase(t.fulfilled, (state, action: PayloadAction<AdminGuide>) => {
        state.guide = action.payload;
      });
    }
    builder.addCase(fetchTaskTemplates.fulfilled, (state, action) => {
      state.taskTemplates = action.payload;
    });
    for (const t of [createTaskTemplate, updateTaskTemplate]) {
      builder.addCase(t.fulfilled, (state, action: PayloadAction<AdminTaskTemplate>) => {
        state.taskTemplates = upsert(state.taskTemplates, action.payload);
      });
    }
    builder.addCase(retireTaskTemplate.fulfilled, (state, action: PayloadAction<string>) => {
      state.taskTemplates = state.taskTemplates.map((t) =>
        t.id === action.payload ? { ...t, is_active: false } : t
      );
    });
    builder.addCase(reorderTaskTemplates.fulfilled, (state, action) => {
      state.taskTemplates = action.payload.reduce(upsert, state.taskTemplates);
    });
    builder.addCase(fetchDDCategories.fulfilled, (state, action) => {
      state.ddCategories = action.payload;
    });
    builder.addCase(fetchDDTemplates.fulfilled, (state, action) => {
      state.ddTemplates = action.payload;
    });
    for (const t of [createDDTemplate, updateDDTemplate]) {
      builder.addCase(t.fulfilled, (state, action: PayloadAction<AdminDDTemplate>) => {
        state.ddTemplates = upsert(state.ddTemplates, action.payload);
      });
    }
    builder.addCase(retireDDTemplate.fulfilled, (state, action: PayloadAction<string>) => {
      state.ddTemplates = state.ddTemplates.map((d) =>
        d.id === action.payload ? { ...d, is_active: false } : d
      );
    });
    builder.addCase(reorderDDTemplates.fulfilled, (state, action) => {
      state.ddTemplates = action.payload.reduce(upsert, state.ddTemplates);
    });

    builder.addMatcher(
      (a) => a.type.startsWith('saleReadyAdmin/') && a.type.endsWith('/pending'),
      (state, action: { type: string }) => {
        state.error = null;
        if (action.type.includes('/fetch')) state.isLoading = true;
        else state.isSaving = true;
      }
    );
    builder.addMatcher(
      (a) => a.type.startsWith('saleReadyAdmin/') && a.type.endsWith('/fulfilled'),
      (state) => {
        state.isLoading = false;
        state.isSaving = false;
      }
    );
    builder.addMatcher(
      (a) => a.type.startsWith('saleReadyAdmin/') && a.type.endsWith('/rejected'),
      (state, action: { payload?: string }) => {
        state.isLoading = false;
        state.isSaving = false;
        state.error = action.payload ?? 'Something went wrong';
      }
    );
  },
});

export const { clearSaleReadyAdminError } = slice.actions;
export default slice.reducer;
