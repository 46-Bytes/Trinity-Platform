import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

// Types
export interface Firm {
  id: string;
  firm_name: string;
  firm_admin_id: string;
  firm_admin_name?: string;
  firm_admin_email?: string;
  seat_count: number;
  seats_used: number;
  clients_count?: number;
  advisors_count?: number;
  billing_email?: string;
  created_at: string;
  updated_at?: string;
}

interface FirmState {
  firms: Firm[];
  isLoading: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Async thunk to fetch all firms
export const fetchFirms = createAsyncThunk(
  'firm/fetchFirms',
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/firms`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch firms' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch firms`);
      }

      const data = await response.json();
      // Handle both array and object responses
      return Array.isArray(data) ? data : (data.firms || []);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch firms');
    }
  }
);

// Initial state
const initialState: FirmState = {
  firms: [],
  isLoading: false,
  error: null,
};

// Slice
const firmSlice = createSlice({
  name: 'firm',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch firms
      .addCase(fetchFirms.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchFirms.fulfilled, (state, action) => {
        state.isLoading = false;
        state.firms = action.payload;
      })
      .addCase(fetchFirms.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError } = firmSlice.actions;
export default firmSlice.reducer;

