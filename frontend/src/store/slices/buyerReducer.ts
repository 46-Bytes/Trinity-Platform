import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

/**
 * The buyer's own read-only view of their one engagement.
 *
 * Every endpoint here is GET. The engagement is resolved by the backend from
 * the buyer's binding, never sent from here, so there is no engagement id to
 * pass and no way for this slice to ask for a different one.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const BASE = `${API_BASE_URL}/api/buyer`;

export interface BuyerEngagement {
  engagement_id: string;
  engagement_name: string | null;
  business_name: string | null;
  nda_signed_date: string | null;
  released_folder_count: number;
}

export interface BuyerFolder {
  category_code: string;
  sub_item_code: string;
  released_at: string | null;
}

interface BuyerState {
  engagement: BuyerEngagement | null;
  folders: BuyerFolder[];
  isLoading: boolean;
  error: string | null;
}

const initialState: BuyerState = {
  engagement: null,
  folders: [],
  isLoading: false,
  error: null,
};

async function request<T>(path: string, fallback: string): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch(`${BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: 'include',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallback);
  }
  return (await response.json()) as T;
}

export const fetchBuyerEngagement = createAsyncThunk<BuyerEngagement, void, { rejectValue: string }>(
  'buyer/fetchEngagement',
  async (_, { rejectWithValue }) => {
    try {
      return await request<BuyerEngagement>('/me/engagement', 'Failed to load the data room');
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to load the data room');
    }
  }
);

export const fetchBuyerFolders = createAsyncThunk<BuyerFolder[], void, { rejectValue: string }>(
  'buyer/fetchFolders',
  async (_, { rejectWithValue }) => {
    try {
      return await request<BuyerFolder[]>('/me/folders', 'Failed to load the documents');
    } catch (e) {
      return rejectWithValue(e instanceof Error ? e.message : 'Failed to load the documents');
    }
  }
);

const slice = createSlice({
  name: 'buyer',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder.addCase(fetchBuyerEngagement.fulfilled, (state, action) => {
      state.engagement = action.payload;
    });
    builder.addCase(fetchBuyerFolders.fulfilled, (state, action) => {
      state.folders = action.payload;
    });
    builder.addMatcher(
      (a) => a.type.startsWith('buyer/') && a.type.endsWith('/pending'),
      (state) => {
        state.isLoading = true;
        state.error = null;
      }
    );
    builder.addMatcher(
      (a) => a.type.startsWith('buyer/') && a.type.endsWith('/fulfilled'),
      (state) => {
        state.isLoading = false;
      }
    );
    builder.addMatcher(
      (a) => a.type.startsWith('buyer/') && a.type.endsWith('/rejected'),
      (state, action: { payload?: string }) => {
        state.isLoading = false;
        state.error = action.payload ?? 'Something went wrong';
      }
    );
  },
});

export default slice.reducer;
