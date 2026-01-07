import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { UserRole } from '@/types/auth';

export interface ClientUser {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  email_verified: boolean;
}

interface ClientState {
  clients: ClientUser[];
  isLoading: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const fetchClientUsers = createAsyncThunk(
  'client/fetchClientUsers',
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/users?role=client`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch clients');
      }

      const data = await response.json();
      const filteredUsers = data.filter(
        (user: ClientUser) => user.role !== 'firm_admin' && user.role !== 'firm_advisor',
      );

      return filteredUsers as ClientUser[];
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch clients');
    }
  },
);

const initialState: ClientState = {
  clients: [],
  isLoading: false,
  error: null,
};

const clientSlice = createSlice({
  name: 'client',
  initialState,
  reducers: {
    clearClientError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchClientUsers.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchClientUsers.fulfilled, (state, action: PayloadAction<ClientUser[]>) => {
        state.isLoading = false;
        state.clients = action.payload;
      })
      .addCase(fetchClientUsers.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearClientError } = clientSlice.actions;
export default clientSlice.reducer;


