import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export interface Firm {
  id: string;
  firm_name: string;
  firm_admin_id: string;
  seat_count: number;
  seats_used: number;
  billing_email?: string;
  created_at: string;
  updated_at: string;
}

export interface Advisor {
  id: string;
  email: string;
  name: string;
  given_name?: string;
  family_name?: string;
  role: 'firm_advisor' | 'advisor';
  is_active: boolean;
  firm_id: string;
  created_at: string;
}

export interface Client {
  id: string;
  email: string;
  name: string;
  given_name?: string;
  family_name?: string;
  role: 'client';
  is_active: boolean;
  created_at: string;
}

interface FirmState {
  firm: Firm | null;
  advisors: Advisor[];
  clients: Client[];
  isLoading: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Helper function to get auth token
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
};

// Async thunks
export const fetchFirm = createAsyncThunk(
  'firm/fetchFirm',
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch firm' }));
        throw new Error(errorData.detail || 'Failed to fetch firm');
      }

      const data = await response.json();
      // If it's an array, get the first firm (firm admin sees their own firm)
      const firm = Array.isArray(data) ? data[0] : data;
      return firm as Firm;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch firm');
    }
  }
);

export const fetchFirmAdvisors = createAsyncThunk(
  'firm/fetchFirmAdvisors',
  async (firmId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/advisors`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch advisors' }));
        throw new Error(errorData.detail || 'Failed to fetch advisors');
      }

      const data = await response.json();
      return (data.advisors || data) as Advisor[];
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch advisors');
    }
  }
);

export const addAdvisorToFirm = createAsyncThunk(
  'firm/addAdvisorToFirm',
  async ({ firmId, advisorData }: { firmId: string; advisorData: { email: string; name?: string } }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/advisors`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(advisorData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to add advisor' }));
        throw new Error(errorData.detail || 'Failed to add advisor');
      }

      const data = await response.json();
      return data as Advisor;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to add advisor');
    }
  }
);

export const removeAdvisorFromFirm = createAsyncThunk(
  'firm/removeAdvisorFromFirm',
  async ({ firmId, advisorId }: { firmId: string; advisorId: string }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/advisors/${advisorId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to remove advisor' }));
        throw new Error(errorData.detail || 'Failed to remove advisor');
      }

      return advisorId;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to remove advisor');
    }
  }
);

export const fetchFirmClients = createAsyncThunk(
  'firm/fetchFirmClients',
  async (_, { rejectWithValue }) => {
    try {
      // Fetch clients through engagements endpoint (firm admin sees all firm clients)
      const response = await fetch(`${API_BASE_URL}/api/engagements/user-role-data`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        throw new Error('Failed to fetch clients');
      }

      const data = await response.json();
      // Transform the clients data
      const clients: Client[] = (data.clients || []).map((client: any) => ({
        id: client.id,
        email: client.email || '',
        name: client.name || 'Unknown',
        given_name: client.given_name,
        family_name: client.family_name,
        role: 'client' as const,
        is_active: true,
        created_at: client.created_at || new Date().toISOString(),
      }));
      return clients;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch clients');
    }
  }
);

export const addClientToFirm = createAsyncThunk(
  'firm/addClientToFirm',
  async ({ firmId, email, name, given_name, family_name }: { firmId: string; email: string; name?: string; given_name?: string; family_name?: string }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/clients`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, name, given_name, family_name }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to add client' }));
        throw new Error(errorData.detail || 'Failed to add client');
      }

      const client = await response.json() as Client;
      return client;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to add client');
    }
  }
);

const initialState: FirmState = {
  firm: null,
  advisors: [],
  clients: [],
  isLoading: false,
  error: null,
};

const firmSlice = createSlice({
  name: 'firm',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    // Fetch firm
    builder
      .addCase(fetchFirm.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchFirm.fulfilled, (state, action) => {
        state.isLoading = false;
        state.firm = action.payload;
      })
      .addCase(fetchFirm.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Fetch advisors
    builder
      .addCase(fetchFirmAdvisors.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchFirmAdvisors.fulfilled, (state, action) => {
        state.isLoading = false;
        state.advisors = action.payload;
      })
      .addCase(fetchFirmAdvisors.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Add advisor
    builder
      .addCase(addAdvisorToFirm.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(addAdvisorToFirm.fulfilled, (state, action) => {
        state.isLoading = false;
        state.advisors.push(action.payload);
        // Optimistically update seats_used in firm dashboard without full refresh
        if (state.firm) {
          state.firm.seats_used = (state.firm.seats_used || 0) + 1;
        }
      })
      .addCase(addAdvisorToFirm.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Remove advisor
    builder
      .addCase(removeAdvisorFromFirm.fulfilled, (state, action) => {
        state.advisors = state.advisors.filter(advisor => advisor.id !== action.payload);
        // Decrement seats_used when an advisor is removed
        if (state.firm && state.firm.seats_used > 0) {
          state.firm.seats_used = state.firm.seats_used - 1;
        }
      });

    // Fetch clients
    builder
      .addCase(fetchFirmClients.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchFirmClients.fulfilled, (state, action) => {
        state.isLoading = false;
        state.clients = action.payload;
      })
      .addCase(fetchFirmClients.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Add client
    builder
      .addCase(addClientToFirm.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(addClientToFirm.fulfilled, (state, action) => {
        state.isLoading = false;
        // Add client to list if not already present
        const existingIndex = state.clients.findIndex(c => c.id === action.payload.id);
        if (existingIndex === -1) {
          state.clients.push(action.payload);
        }
      })
      .addCase(addClientToFirm.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError } = firmSlice.actions;
export default firmSlice.reducer;

