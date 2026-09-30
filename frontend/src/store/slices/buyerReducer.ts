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

/** A released folder. Names come from the engagement's DD items; no advisor metadata. */
export interface BuyerFolder {
  category_code: string;
  category: string | null;
  sub_item_code: string;
  sub_item: string | null;
}

/** A document a buyer may open. Carries no Drive id and no storage path. */
export interface BuyerDocument {
  id: string;
  file_name: string;
  file_size: number | null;
  file_type: string | null;
  created_at: string | null;
  /** PDF, image or text: can be opened in the browser, not only downloaded. */
  viewable: boolean;
}

export interface BuyerFolderContents extends BuyerFolder {
  documents: BuyerDocument[];
}

interface BuyerState {
  engagement: BuyerEngagement | null;
  folders: BuyerFolder[];
  /** Contents of the folders the buyer has opened, keyed 'category|sub_item'. */
  contents: Record<string, BuyerDocument[]>;
  isLoading: boolean;
  error: string | null;
}

const initialState: BuyerState = {
  engagement: null,
  folders: [],
  contents: {},
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

export const fetchBuyerFolderContents = createAsyncThunk<
  BuyerFolderContents,
  { categoryCode: string; subItemCode: string },
  { rejectValue: string }
>('buyer/fetchFolderContents', async ({ categoryCode, subItemCode }, { rejectWithValue }) => {
  try {
    return await request<BuyerFolderContents>(
      `/me/folders/${categoryCode}/${subItemCode}`,
      'Failed to open the folder'
    );
  } catch (e) {
    return rejectWithValue(e instanceof Error ? e.message : 'Failed to open the folder');
  }
});

/**
 * Download a released document through Trinity.
 *
 * The endpoint is authenticated, so a plain anchor cannot carry the token;
 * the bytes are fetched and handed to the browser as a blob. Trinity streams
 * them from Drive - the buyer never receives a Drive URL.
 */
export async function downloadBuyerDocument(mediaId: string, fileName: string): Promise<void> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch(`${BASE}/me/documents/${mediaId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: 'include',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'Failed to download the document');
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/**
 * Fetch a released document for viewing in the page, as a blob.
 *
 * Same authenticated stream as a download, from the view endpoint, which only
 * serves types a browser renders by itself. The caller owns the object URL and
 * must revoke it. No Drive URL is involved at any point.
 */
export async function fetchBuyerDocumentForView(mediaId: string): Promise<Blob> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch(`${BASE}/me/documents/${mediaId}/view`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: 'include',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'Failed to open the document');
  }
  return response.blob();
}

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
    builder.addCase(fetchBuyerFolderContents.fulfilled, (state, action) => {
      const key = `${action.payload.category_code}|${action.payload.sub_item_code}`;
      state.contents[key] = action.payload.documents;
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
