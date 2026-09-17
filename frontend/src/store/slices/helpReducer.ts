import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import type { CategoryWithVideos, HelpVideo, HelpVideoCategory } from '@/types/help';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token');
  return {
    Authorization: `Bearer ${token ?? ''}`,
    'Content-Type': 'application/json',
  };
}

/** Normalise FastAPI error responses (string detail or 422 validation array). */
async function parseError(response: Response, fallback: string): Promise<string> {
  const data = await response.json().catch(() => null);
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first?.msg) return String(first.msg).replace(/^Value error,\s*/, '');
    return JSON.stringify(first);
  }
  return `HTTP ${response.status}: ${fallback}`;
}

// ------------------------------ Thunks ------------------------------

export const fetchCategoriesWithVideos = createAsyncThunk(
  'help/fetchCategoriesWithVideos',
  async (_: void, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/help/categories`, {
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error(await parseError(response, 'Failed to load help videos'));
      return (await response.json()) as CategoryWithVideos[];
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to load help videos');
    }
  }
);

export const createCategory = createAsyncThunk(
  'help/createCategory',
  async (payload: { name: string; description?: string }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/help/categories`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await parseError(response, 'Failed to create category'));
      return (await response.json()) as HelpVideoCategory;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create category');
    }
  }
);

export const updateCategory = createAsyncThunk(
  'help/updateCategory',
  async (payload: { id: string; name?: string; description?: string }, { rejectWithValue }) => {
    try {
      const { id, ...body } = payload;
      const response = await fetch(`${API_BASE_URL}/api/help/categories/${id}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await parseError(response, 'Failed to update category'));
      return (await response.json()) as HelpVideoCategory;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update category');
    }
  }
);

export const deleteCategory = createAsyncThunk(
  'help/deleteCategory',
  async (categoryId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/help/categories/${categoryId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error(await parseError(response, 'Failed to delete category'));
      return categoryId;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to delete category');
    }
  }
);

export const reorderCategories = createAsyncThunk(
  'help/reorderCategories',
  async (orderedIds: string[], { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/help/categories/reorder`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ ordered_ids: orderedIds }),
      });
      if (!response.ok) throw new Error(await parseError(response, 'Failed to reorder categories'));
      return (await response.json()) as HelpVideoCategory[];
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to reorder categories');
    }
  }
);

export const createVideo = createAsyncThunk(
  'help/createVideo',
  async (
    payload: { category_id: string; youtube_url: string; title: string; description?: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/help/videos`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error(await parseError(response, 'Failed to create video'));
      return (await response.json()) as HelpVideo;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create video');
    }
  }
);

export const updateVideo = createAsyncThunk(
  'help/updateVideo',
  async (
    payload: { id: string; title?: string; description?: string; category_id?: string; youtube_url?: string },
    { rejectWithValue }
  ) => {
    try {
      const { id, ...body } = payload;
      const response = await fetch(`${API_BASE_URL}/api/help/videos/${id}`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error(await parseError(response, 'Failed to update video'));
      return (await response.json()) as HelpVideo;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update video');
    }
  }
);

export const deleteVideo = createAsyncThunk(
  'help/deleteVideo',
  async (videoId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/help/videos/${videoId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error(await parseError(response, 'Failed to delete video'));
      return videoId;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to delete video');
    }
  }
);

export const reorderVideos = createAsyncThunk(
  'help/reorderVideos',
  async (payload: { categoryId: string; orderedIds: string[] }, { rejectWithValue }) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/help/categories/${payload.categoryId}/videos/reorder`,
        {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({ ordered_ids: payload.orderedIds }),
        }
      );
      if (!response.ok) throw new Error(await parseError(response, 'Failed to reorder videos'));
      return (await response.json()) as HelpVideo[];
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to reorder videos');
    }
  }
);

// ------------------------------ State ------------------------------

interface HelpState {
  categories: CategoryWithVideos[];
  isLoading: boolean;
  isSaving: boolean;
  error: string | null;
}

const initialState: HelpState = {
  categories: [],
  isLoading: false,
  isSaving: false,
  error: null,
};

const helpSlice = createSlice({
  name: 'help',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCategoriesWithVideos.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchCategoriesWithVideos.fulfilled, (state, action) => {
        state.isLoading = false;
        state.categories = action.payload;
      })
      .addCase(fetchCategoriesWithVideos.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // All mutating thunks share the saving/error lifecycle. The page re-fetches
    // categories after each success to keep ordering and grouping authoritative.
    const mutations = [
      createCategory,
      updateCategory,
      deleteCategory,
      reorderCategories,
      createVideo,
      updateVideo,
      deleteVideo,
      reorderVideos,
    ];
    mutations.forEach((thunk) => {
      builder
        .addCase(thunk.pending, (state) => {
          state.isSaving = true;
          state.error = null;
        })
        .addCase(thunk.fulfilled, (state) => {
          state.isSaving = false;
        })
        .addCase(thunk.rejected, (state, action) => {
          state.isSaving = false;
          state.error = action.payload as string;
        });
    });
  },
});

export const { clearError } = helpSlice.actions;
export default helpSlice.reducer;
