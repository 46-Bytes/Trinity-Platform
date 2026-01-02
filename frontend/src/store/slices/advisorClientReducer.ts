import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export interface AdvisorClientAssociation {
  id: string;
  advisor_id: string;
  client_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  advisor_name?: string;
  advisor_email?: string;
  client_name?: string;
  client_email?: string;
}

interface AdvisorClientState {
  associations: AdvisorClientAssociation[];
  isLoading: boolean;
  isCreating: boolean;
  isDeleting: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Async thunks
export const fetchAssociations = createAsyncThunk(
  'advisorClient/fetchAssociations',
  async (advisorId: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/advisor-client?advisor_id=${advisorId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch associations' }));
        throw new Error(errorData.detail || 'Failed to fetch associations');
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch associations');
    }
  }
);

export const createAssociation = createAsyncThunk(
  'advisorClient/createAssociation',
  async ({ advisorId, clientId }: { advisorId: string; clientId: string }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/advisor-client`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          advisor_id: advisorId,
          client_id: clientId,
          status: 'active',
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to create association' }));
        throw new Error(errorData.detail || 'Failed to create association');
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create association');
    }
  }
);

export const deleteAssociation = createAsyncThunk(
  'advisorClient/deleteAssociation',
  async (associationId: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/advisor-client/${associationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete association' }));
        throw new Error(errorData.detail || 'Failed to delete association');
      }

      return associationId;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to delete association');
    }
  }
);

// Initial state
const initialState: AdvisorClientState = {
  associations: [],
  isLoading: false,
  isCreating: false,
  isDeleting: false,
  error: null,
};

// Slice
const advisorClientSlice = createSlice({
  name: 'advisorClient',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch associations
      .addCase(fetchAssociations.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchAssociations.fulfilled, (state, action) => {
        state.isLoading = false;
        state.associations = action.payload;
      })
      .addCase(fetchAssociations.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Create association
      .addCase(createAssociation.pending, (state) => {
        state.isCreating = true;
        state.error = null;
      })
      .addCase(createAssociation.fulfilled, (state, action) => {
        state.isCreating = false;
        state.associations.push(action.payload);
      })
      .addCase(createAssociation.rejected, (state, action) => {
        state.isCreating = false;
        state.error = action.payload as string;
      })
      // Delete association
      .addCase(deleteAssociation.pending, (state) => {
        state.isDeleting = true;
        state.error = null;
      })
      .addCase(deleteAssociation.fulfilled, (state, action) => {
        state.isDeleting = false;
        state.associations = state.associations.filter((assoc) => assoc.id !== action.payload);
      })
      .addCase(deleteAssociation.rejected, (state, action) => {
        state.isDeleting = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError } = advisorClientSlice.actions;
export default advisorClientSlice.reducer;

