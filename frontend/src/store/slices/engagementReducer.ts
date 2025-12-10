import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export interface Engagement {
  id: string;
  clientId: string;
  clientName: string;
  businessName: string;
  title: string;
  description: string;
  industryName: string;
  status: 'draft' | 'active' | 'on-hold' | 'completed' | 'cancelled';
  startDate: string;
  endDate?: string;
  budget?: number;
  assignedUsers: string[];
  createdAt: string;
  updatedAt: string;
}

export interface Advisor {
  id: string;
  name: string;
}

export interface Client {
  id: string;
  name: string;
}

export interface UserRoleData {
  user_role: 'advisor' | 'client' | 'admin';
  advisors?: Advisor[];
  clients?: Client[];
}

interface EngagementState {
  engagements: Engagement[];
  selectedEngagement: Engagement | null;
  isLoading: boolean;
  error: string | null;
  userRoleData: UserRoleData | null;
  filters: {
    status?: string;
    clientId?: string;
    search?: string;
  };
}

const API_BASE_URL = '';

// Async thunks
export const fetchUserRoleData = createAsyncThunk(
  'engagement/fetchUserRoleData',
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/engagements/user-role-data`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch user role data');
      }

      const data = await response.json();
      return data as UserRoleData;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch user role data');
    }
  }
);

export const fetchEngagements = createAsyncThunk(
  'engagement/fetchEngagements',
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/engagements`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch engagements');
      }

      const data = await response.json();
      return data.engagements || data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch engagements');
    }
  }
);

export const fetchEngagementById = createAsyncThunk(
  'engagement/fetchEngagementById',
  async (id: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/engagements/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch engagement');
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch engagement');
    }
  }
);

export const createEngagement = createAsyncThunk(
  'engagement/createEngagement',
  async (engagement: Omit<Engagement, 'id' | 'createdAt' | 'updatedAt'>, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/engagements`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(engagement),
      });

      if (!response.ok) {
        throw new Error('Failed to create engagement');
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create engagement');
    }
  }
);

export const updateEngagement = createAsyncThunk(
  'engagement/updateEngagement',
  async ({ id, updates }: { id: string; updates: Partial<Engagement> }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/engagements/${id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        throw new Error('Failed to update engagement');
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update engagement');
    }
  }
);

export const deleteEngagement = createAsyncThunk(
  'engagement/deleteEngagement',
  async (id: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/engagements/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete engagement');
      }

      return id;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to delete engagement');
    }
  }
);

// Initial state
const initialState: EngagementState = {
  engagements: [],
  selectedEngagement: null,
  isLoading: false,
  error: null,
  userRoleData: null,
  filters: {},
};

// Slice
const engagementSlice = createSlice({
  name: 'engagement',
  initialState,
  reducers: {
    setSelectedEngagement: (state, action: PayloadAction<Engagement | null>) => {
      state.selectedEngagement = action.payload;
    },
    setFilters: (state, action: PayloadAction<EngagementState['filters']>) => {
      state.filters = { ...state.filters, ...action.payload };
    },
    clearFilters: (state) => {
      state.filters = {};
    },
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch user role data
      .addCase(fetchUserRoleData.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchUserRoleData.fulfilled, (state, action) => {
        state.isLoading = false;
        state.userRoleData = action.payload;
      })
      .addCase(fetchUserRoleData.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Fetch all engagements
      .addCase(fetchEngagements.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchEngagements.fulfilled, (state, action) => {
        state.isLoading = false;
        state.engagements = action.payload;
      })
      .addCase(fetchEngagements.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Fetch engagement by ID
      .addCase(fetchEngagementById.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchEngagementById.fulfilled, (state, action) => {
        state.isLoading = false;
        state.selectedEngagement = action.payload;
      })
      .addCase(fetchEngagementById.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Create engagement
      .addCase(createEngagement.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(createEngagement.fulfilled, (state, action) => {
        state.isLoading = false;
        state.engagements.push(action.payload);
      })
      .addCase(createEngagement.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Update engagement
      .addCase(updateEngagement.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(updateEngagement.fulfilled, (state, action) => {
        state.isLoading = false;
        const index = state.engagements.findIndex((e) => e.id === action.payload.id);
        if (index !== -1) {
          state.engagements[index] = action.payload;
        }
        if (state.selectedEngagement?.id === action.payload.id) {
          state.selectedEngagement = action.payload;
        }
      })
      .addCase(updateEngagement.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Delete engagement
      .addCase(deleteEngagement.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(deleteEngagement.fulfilled, (state, action) => {
        state.isLoading = false;
        state.engagements = state.engagements.filter((e) => e.id !== action.payload);
        if (state.selectedEngagement?.id === action.payload) {
          state.selectedEngagement = null;
        }
      })
      .addCase(deleteEngagement.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { setSelectedEngagement, setFilters, clearFilters, clearError } = engagementSlice.actions;
export default engagementSlice.reducer;