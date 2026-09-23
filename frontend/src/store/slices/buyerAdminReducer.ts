import { createAsyncThunk, createSlice, type PayloadAction } from '@reduxjs/toolkit';

/**
 * The advisor's controls over buyer access on one engagement.
 *
 * Separate from buyerReducer, which is the buyer's own read-only view: these
 * endpoints sit behind the engagement access check and are never reachable by a
 * buyer. Kept off the Sale Ready slice because buyer access is engagement-level
 * rather than part of the Sale Ready program state.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const BASE = `${API_BASE_URL}/api/engagements`;

export interface EngagementBuyer {
  id: string;
  engagement_id: string;
  user_id: string;
  email: string | null;
  name: string | null;
  status: 'active' | 'revoked';
  nda_signed_date: string | null;
  invited_by_user_id: string | null;
  created_at: string | null;
}

export interface ReleasedFolder {
  category_code: string;
  sub_item_code: string;
  released_at?: string | null;
}

interface BuyerAdminState {
  buyers: EngagementBuyer[];
  releasedFolders: ReleasedFolder[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
}

const initialState: BuyerAdminState = {
  buyers: [],
  releasedFolders: [],
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
    credentials: 'include',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallback);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const thunk = <Arg, Result>(name: string, fallback: string, run: (arg: Arg) => Promise<Result>) =>
  createAsyncThunk<Result, Arg, { rejectValue: string }>(`buyerAdmin/${name}`, async (arg, { rejectWithValue }) => {
    try {
      return await run(arg);
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : fallback);
    }
  });

export const fetchEngagementBuyers = thunk<string, EngagementBuyer[]>(
  'fetchBuyers', 'Failed to load the buyers',
  (engagementId) => request<EngagementBuyer[]>(`/${engagementId}/buyers`, 'Failed to load the buyers'));

export const inviteBuyer = thunk<
  { engagementId: string; email: string; nda_signed_date?: string | null },
  EngagementBuyer
>('inviteBuyer', 'Failed to invite the buyer', ({ engagementId, ...body }) =>
  request<EngagementBuyer>(`/${engagementId}/buyers`, 'Failed to invite the buyer', {
    method: 'POST',
    body: JSON.stringify(body),
  }));

export const revokeBuyer = thunk<{ engagementId: string; id: string }, EngagementBuyer>(
  'revokeBuyer', 'Failed to revoke access',
  ({ engagementId, id }) =>
    request<EngagementBuyer>(`/${engagementId}/buyers/${id}/revoke`, 'Failed to revoke access', {
      method: 'POST',
    }));

export const restoreBuyer = thunk<{ engagementId: string; id: string }, EngagementBuyer>(
  'restoreBuyer', 'Failed to restore access',
  ({ engagementId, id }) =>
    request<EngagementBuyer>(`/${engagementId}/buyers/${id}/restore`, 'Failed to restore access', {
      method: 'POST',
    }));

export const updateBuyerNda = thunk<
  { engagementId: string; id: string; nda_signed_date: string | null },
  EngagementBuyer
>('updateBuyerNda', 'Failed to save the NDA date', ({ engagementId, id, nda_signed_date }) =>
  request<EngagementBuyer>(`/${engagementId}/buyers/${id}`, 'Failed to save the NDA date', {
    method: 'PATCH',
    body: JSON.stringify({ nda_signed_date }),
  }));

export const fetchReleasedFolders = thunk<string, ReleasedFolder[]>(
  'fetchFolders', 'Failed to load the released folders',
  (engagementId) =>
    request<ReleasedFolder[]>(`/${engagementId}/released-folders`, 'Failed to load the released folders'));

export const setReleasedFolders = thunk<
  { engagementId: string; folders: ReleasedFolder[] },
  ReleasedFolder[]
>('setFolders', 'Failed to save the released folders', ({ engagementId, folders }) =>
  request<ReleasedFolder[]>(`/${engagementId}/released-folders`, 'Failed to save the released folders', {
    method: 'PUT',
    body: JSON.stringify({
      folders: folders.map((f) => ({ category_code: f.category_code, sub_item_code: f.sub_item_code })),
    }),
  }));

function upsert(list: EngagementBuyer[], row: EngagementBuyer): EngagementBuyer[] {
  const index = list.findIndex((b) => b.id === row.id);
  if (index === -1) return [...list, row];
  const next = [...list];
  next[index] = row;
  return next;
}

const slice = createSlice({
  name: 'buyerAdmin',
  initialState,
  reducers: {
    clearBuyerAdminError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder.addCase(fetchEngagementBuyers.fulfilled, (state, action) => {
      state.buyers = action.payload;
    });
    for (const t of [inviteBuyer, revokeBuyer, restoreBuyer, updateBuyerNda]) {
      builder.addCase(t.fulfilled, (state, action: PayloadAction<EngagementBuyer>) => {
        state.buyers = upsert(state.buyers, action.payload);
      });
    }
    for (const t of [fetchReleasedFolders, setReleasedFolders]) {
      builder.addCase(t.fulfilled, (state, action: PayloadAction<ReleasedFolder[]>) => {
        state.releasedFolders = action.payload;
      });
    }

    builder.addMatcher(
      (a) => a.type.startsWith('buyerAdmin/') && a.type.endsWith('/pending'),
      (state, action: { type: string }) => {
        state.error = null;
        if (action.type.includes('/fetch')) state.isLoading = true;
        else state.isSaving = true;
      }
    );
    builder.addMatcher(
      (a) => a.type.startsWith('buyerAdmin/') && a.type.endsWith('/fulfilled'),
      (state) => {
        state.isLoading = false;
        state.isSaving = false;
      }
    );
    builder.addMatcher(
      (a) => a.type.startsWith('buyerAdmin/') && a.type.endsWith('/rejected'),
      (state, action: { payload?: string }) => {
        state.isLoading = false;
        state.isSaving = false;
        state.error = action.payload ?? 'Something went wrong';
      }
    );
  },
});

export const { clearBuyerAdminError } = slice.actions;
export default slice.reducer;
