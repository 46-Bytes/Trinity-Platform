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
  tool?: 'diagnostic' | 'kpi_builder';
  status: 'draft' | 'active' | 'on-hold' | 'completed' | 'cancelled';
  startDate: string;
  endDate?: string;
  budget?: number;
  assignedUsers: string[];
  createdAt: string;
  updatedAt: string;
  // Additional fields from backend
  tasksCount?: number;
  pendingTasksCount?: number;
  diagnosticsCount?: number;
  notesCount?: number;
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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
  async (params: { status?: string; search?: string } | undefined, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Build query string
      const queryParams = new URLSearchParams();
      if (params?.status) {
        queryParams.append('status_filter', params.status);
      }
      if (params?.search) {
        queryParams.append('search', params.search);
      }

      const url = `${API_BASE_URL}/api/engagements${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch engagements' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch engagements`);
      }

      const data = await response.json();
      
      // Transform backend data to match frontend Engagement interface
      const engagements: Engagement[] = (Array.isArray(data) ? data : []).map((item: any) => ({
        id: item.id,
        clientId: item.client_id,
        clientName: item.client_name || 'Unknown Client',
        businessName: item.business_name || '',
        title: item.title || item.engagement_name || '',
        description: item.description || '',
        industryName: item.industry_name || item.industry || '',
        tool: item.tool || undefined,
        status: mapBackendStatusToFrontend(item.status),
        startDate: item.start_date || item.created_at || new Date().toISOString(),
        endDate: item.end_date || item.completed_at || undefined,
        budget: undefined, // Not in backend model yet
        assignedUsers: item.assigned_users || item.secondary_advisor_ids?.map((id: string) => String(id)) || [],
        createdAt: item.created_at || new Date().toISOString(),
        updatedAt: item.updated_at || new Date().toISOString(),
        // Additional fields from backend
        tasksCount: item.tasks_count || 0,
        pendingTasksCount: item.pending_tasks_count || 0,
        diagnosticsCount: item.diagnostics_count || 0,
        notesCount: item.notes_count || 0,
      }));

      return engagements;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch engagements');
    }
  }
);

// Helper function to map backend status to frontend status
function mapBackendStatusToFrontend(status: string): 'draft' | 'active' | 'on-hold' | 'completed' | 'cancelled' {
  const statusMap: Record<string, 'draft' | 'active' | 'on-hold' | 'completed' | 'cancelled'> = {
    'draft': 'draft',
    'active': 'active',
    'paused': 'on-hold',
    'completed': 'completed',
    'archived': 'cancelled',
  };
  return statusMap[status.toLowerCase()] || 'active';
}

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
  async (engagement: {
    clientId: string;
    clientName: string;
    businessName: string;
    title: string;
    description: string;
    industryName: string;
    tool: 'diagnostic' | 'kpi_builder';
    status: 'draft' | 'active' | 'on-hold' | 'completed' | 'cancelled';
    primaryAdvisorId?: string; // Optional: will be fetched from current user if not provided
  }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Get current user to determine primary_advisor_id
      let primaryAdvisorId = engagement.primaryAdvisorId;
      if (!primaryAdvisorId) {
        try {
          const userResponse = await fetch(`${API_BASE_URL}/api/auth/user`, {
            headers: {
              'Authorization': `Bearer ${token}`,
            },
          });
          if (userResponse.ok) {
            const userData = await userResponse.json();
            if (userData.user?.id && (userData.user?.role === 'advisor' || userData.user?.role === 'admin')) {
              primaryAdvisorId = userData.user.id;
            }
          }
        } catch (error) {
          console.warn('Failed to fetch current user, using provided advisor ID');
        }
      }

      if (!primaryAdvisorId) {
        throw new Error('Primary advisor ID is required. Please ensure you are logged in as an advisor.');
      }

      // Map frontend format to backend format
      const backendPayload = {
        engagement_name: engagement.title,
        business_name: engagement.businessName,
        industry: engagement.industryName,
        description: engagement.description,
        tool: engagement.tool,
        client_id: engagement.clientId,
        primary_advisor_id: primaryAdvisorId,
        status: mapFrontendStatusToBackend(engagement.status),
      };

      const response = await fetch(`${API_BASE_URL}/api/engagements`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backendPayload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to create engagement' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create engagement`);
      }

      const data = await response.json();
      
      // Transform backend response to frontend format
      return {
        id: data.id,
        clientId: data.client_id,
        clientName: data.client_name || engagement.clientName,
        businessName: data.business_name || engagement.businessName,
        title: data.title || data.engagement_name || engagement.title,
        description: data.description || engagement.description,
        industryName: data.industry_name || data.industry || engagement.industryName,
        status: mapBackendStatusToFrontend(data.status),
        startDate: data.start_date || data.created_at || new Date().toISOString(),
        endDate: data.end_date || data.completed_at || undefined,
        assignedUsers: data.assigned_users || data.secondary_advisor_ids?.map((id: string) => String(id)) || [],
        createdAt: data.created_at || new Date().toISOString(),
        updatedAt: data.updated_at || new Date().toISOString(),
      } as Engagement;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create engagement');
    }
  }
);

// Helper function to map frontend status to backend status
function mapFrontendStatusToBackend(status: 'draft' | 'active' | 'on-hold' | 'completed' | 'cancelled'): string {
  const statusMap: Record<string, string> = {
    'draft': 'draft',
    'active': 'active',
    'on-hold': 'paused',
    'completed': 'completed',
    'cancelled': 'archived',
  };
  return statusMap[status] || 'active';
}

export const updateEngagement = createAsyncThunk(
  'engagement/updateEngagement',
  async ({ id, updates }: { id: string; updates: Partial<Engagement> }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/engagements/${id}`, {
        method: 'PATCH',
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