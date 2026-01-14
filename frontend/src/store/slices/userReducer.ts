import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { UserRole } from '@/types/auth';

// Types
export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  email_verified: boolean;
  last_login?: string;
  created_at: string;
  nickname?: string;
}

interface UserState {
  users: User[];
  isLoading: boolean;
  isCreating: boolean;
  isUpdating: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Async thunks
export const fetchUsers = createAsyncThunk(
  'user/fetchUsers',
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/users`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch users');
      }

      const data = await response.json();
      // Filter out firm_admin and firm_advisor roles
      const filteredUsers = data.filter((user: User) => 
        user.role !== 'firm_admin' && user.role !== 'firm_advisor'
      );
      
      return filteredUsers;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch users');
    }
  }
);

export const createUser = createAsyncThunk(
  'user/createUser',
  async (userData: { email: string; name: string; role: UserRole }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/users`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: userData.email,
          name: userData.name,
          role: userData.role,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to create user' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create user`);
      }

      const data = await response.json();
      return data as User;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create user');
    }
  }
);

export const updateUser = createAsyncThunk(
  'user/updateUser',
  async (userData: { id: string; name?: string; role?: UserRole; is_active?: boolean }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const body: Record<string, any> = {};
      if (userData.name !== undefined) body.name = userData.name;
      if (userData.role !== undefined) body.role = userData.role;
      if (userData.is_active !== undefined) body.is_active = userData.is_active;

      const response = await fetch(`${API_BASE_URL}/api/users/${userData.id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to update user' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to update user`);
      }

      const data = await response.json();
      return data as User;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update user');
    }
  }
);

// Initial state
const initialState: UserState = {
  users: [],
  isLoading: false,
  isCreating: false,
  isUpdating: false,
  error: null,
};

// Slice
const userSlice = createSlice({
  name: 'user',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch users
      .addCase(fetchUsers.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchUsers.fulfilled, (state, action) => {
        state.isLoading = false;
        state.users = action.payload;
      })
      .addCase(fetchUsers.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Create user
      .addCase(createUser.pending, (state) => {
        state.isCreating = true;
        state.error = null;
      })
      .addCase(createUser.fulfilled, (state, action) => {
        state.isCreating = false;
        state.users.push(action.payload);
      })
      .addCase(createUser.rejected, (state, action) => {
        state.isCreating = false;
        state.error = action.payload as string;
      })
      // Update user
      .addCase(updateUser.pending, (state) => {
        state.isUpdating = true;
        state.error = null;
      })
      .addCase(updateUser.fulfilled, (state, action) => {
        state.isUpdating = false;
        const index = state.users.findIndex(u => u.id === action.payload.id);
        if (index !== -1) {
          state.users[index] = action.payload;
        }
      })
      .addCase(updateUser.rejected, (state, action) => {
        state.isUpdating = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError } = userSlice.actions;
export default userSlice.reducer;

