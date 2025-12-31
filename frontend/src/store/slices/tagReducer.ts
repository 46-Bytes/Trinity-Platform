import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export interface TagUpdatePayload {
  fileId: string;
  tag: string | null;
  mediaId?: string;
  diagnosticId?: string;
}

interface TagState {
  // Map of mediaId -> tag
  mediaTags: Record<string, string>;
  // Map of diagnosticId -> tag
  diagnosticTags: Record<string, string>;
  isLoading: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Async thunks
export const fetchMediaTags = createAsyncThunk(
  'tag/fetchMediaTags',
  async (diagnosticIds: string[], { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const tagsMap: Record<string, string> = {};

      // Fetch tags for each diagnostic's media files
      await Promise.all(
        diagnosticIds.map(async (diagnosticId) => {
          try {
            const response = await fetch(`${API_BASE_URL}/api/files/diagnostic/${diagnosticId}`, {
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json',
              },
            });

            if (response.ok) {
              const data = await response.json();
              if (data.files && Array.isArray(data.files)) {
                data.files.forEach((file: any) => {
                  if (file.id && file.tag) {
                    tagsMap[file.id] = file.tag;
                  }
                });
              }
            }
          } catch (error) {
            console.error(`Failed to fetch media tags for diagnostic ${diagnosticId}:`, error);
          }
        })
      );

      return tagsMap;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch media tags');
    }
  }
);

export const updateMediaTag = createAsyncThunk(
  'tag/updateMediaTag',
  async ({ mediaId, tag }: { mediaId: string; tag: string | null }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/files/${mediaId}/tag`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ tag: tag || '' }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to update tag' }));
        throw new Error(errorData.detail || 'Failed to update tag');
      }

      const data = await response.json();
      return { mediaId, tag: data.file?.tag || tag };
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update tag');
    }
  }
);

export const updateDiagnosticTag = createAsyncThunk(
  'tag/updateDiagnosticTag',
  async ({ diagnosticId, tag }: { diagnosticId: string; tag: string | null }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/tag`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ tag: tag || '' }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to update tag' }));
        throw new Error(errorData.detail || 'Failed to update tag');
      }

      const data = await response.json();
      return { diagnosticId, tag: data.tag || tag };
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update tag');
    }
  }
);

// Initial state
const initialState: TagState = {
  mediaTags: {},
  diagnosticTags: {},
  isLoading: false,
  error: null,
};

// Slice
const tagSlice = createSlice({
  name: 'tag',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    clearTags: (state) => {
      state.mediaTags = {};
      state.diagnosticTags = {};
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch media tags
      .addCase(fetchMediaTags.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchMediaTags.fulfilled, (state, action) => {
        state.isLoading = false;
        // Merge new tags with existing ones
        state.mediaTags = { ...state.mediaTags, ...action.payload };
      })
      .addCase(fetchMediaTags.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Update media tag
      .addCase(updateMediaTag.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(updateMediaTag.fulfilled, (state, action) => {
        state.isLoading = false;
        if (action.payload.tag) {
          state.mediaTags[action.payload.mediaId] = action.payload.tag;
        } else {
          // Remove tag if it's null
          delete state.mediaTags[action.payload.mediaId];
        }
      })
      .addCase(updateMediaTag.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Update diagnostic tag
      .addCase(updateDiagnosticTag.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(updateDiagnosticTag.fulfilled, (state, action) => {
        state.isLoading = false;
        if (action.payload.tag) {
          state.diagnosticTags[action.payload.diagnosticId] = action.payload.tag;
        } else {
          // Remove tag if it's null
          delete state.diagnosticTags[action.payload.diagnosticId];
        }
      })
      .addCase(updateDiagnosticTag.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError, clearTags } = tagSlice.actions;
export default tagSlice.reducer;

