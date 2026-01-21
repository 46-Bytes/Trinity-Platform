import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { RootState } from '../index';

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
  clients?: string[]; // Array of client user IDs
  is_active?: boolean;
  created_at: string;
  updated_at?: string;
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
  first_name?: string;
  last_name?: string;
  role: 'client';
  is_active: boolean;
  created_at: string;
}

export interface FirmStats {
  firm_id: string;
  firm_name: string;
  advisors_count: number;  // Total advisors (active + suspended)
  active_advisors_count?: number;  // Only active advisors
  seats_used: number;  // Active advisors only (for billing)
  seats_available: number;
  engagements_count: number;
  active_engagements: number;
  diagnostics_count: number;
  tasks_count: number;
}

interface FirmState {
  firms: Firm[];
  firm: Firm | null;
  advisors: Advisor[];
  clients: Client[];
  stats: FirmStats | null;
  seats_used: number | null;  // From advisors API response
  seats_available: number | null;  // From advisors API response
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

// Async thunk to fetch all firms (for super admin)
export const fetchFirms = createAsyncThunk(
  'firm/fetchFirms',
  async (_, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms`, {
        headers: getAuthHeaders(),
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

// Async thunk to fetch single firm (for firm admin)
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

// Async thunk to fetch firm by ID (for superadmin)
export const fetchFirmById = createAsyncThunk(
  'firm/fetchFirmById',
  async (firmId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch firm' }));
        throw new Error(errorData.detail || 'Failed to fetch firm');
      }

      const data = await response.json();
      return data as Firm;
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
      return {
        advisors: (data.advisors || data) as Advisor[],
        seats_used: data.seats_used as number,
        seats_available: data.seats_available as number,
      };
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

export const getAdvisorEngagements = createAsyncThunk(
  'firm/getAdvisorEngagements',
  async ({ firmId, advisorId }: { firmId: string; advisorId: string }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/advisors/${advisorId}/engagements`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch advisor engagements' }));
        throw new Error(errorData.detail || 'Failed to fetch advisor engagements');
      }

      const data = await response.json();
      return data as { primary: any[]; secondary: any[] };
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch advisor engagements');
    }
  }
);

export const suspendAdvisor = createAsyncThunk(
  'firm/suspendAdvisor',
  async ({ 
    firmId, 
    advisorId, 
    reassignments 
  }: { 
    firmId: string; 
    advisorId: string; 
    reassignments?: Record<string, string> 
  }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/advisors/${advisorId}/suspend`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reassignments: reassignments || {} }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to suspend advisor' }));
        throw new Error(errorData.detail || 'Failed to suspend advisor');
      }

      const data = await response.json();
      return data as Advisor;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to suspend advisor');
    }
  }
);

export const reactivateAdvisor = createAsyncThunk(
  'firm/reactivateAdvisor',
  async ({ 
    firmId, 
    advisorId 
  }: { 
    firmId: string; 
    advisorId: string; 
  }, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/advisors/${advisorId}/reactivate`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to reactivate advisor' }));
        throw new Error(errorData.detail || 'Failed to reactivate advisor');
      }

      const data = await response.json();
      return data as Advisor;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to reactivate advisor');
    }
  }
);

export const fetchFirmStats = createAsyncThunk(
  'firm/fetchFirmStats',
  async (firmId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/stats`, {
        headers: getAuthHeaders(),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch firm stats' }));
        throw new Error(errorData.detail || 'Failed to fetch firm stats');
      }

      const data = await response.json();
      return data as FirmStats;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch firm stats');
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

// Async thunk to fetch clients for a specific firm (for superadmin)
export const fetchFirmClientsById = createAsyncThunk(
  'firm/fetchFirmClientsById',
  async (firmId: string, { rejectWithValue, getState }) => {
    try {
      // Try to get firm from Redux state first to avoid duplicate API call
      const state = getState() as RootState;
      let clientIds: string[] = [];
      
      if (state.firm?.firm?.id === firmId && state.firm.firm.clients) {
        // Firm is already in state, use it
        console.log('Using firm from Redux state');
        clientIds = state.firm.firm.clients;
      } else {
        // Firm not in state, fetch it
        console.log('Fetching firm from API');
        const firmResponse = await fetch(`${API_BASE_URL}/api/firms/${firmId}`, {
          headers: getAuthHeaders(),
        });

        if (!firmResponse.ok) {
          throw new Error('Failed to fetch firm');
        }

        const firmData = await firmResponse.json();
        clientIds = firmData.clients || [];
      }

      if (clientIds.length === 0) {
        console.log('No clients found in firm');
        return [];
      }

      // Convert UUIDs to strings (they might be UUID objects or strings)
      const clientIdStrings = clientIds.map((id: any) => {
        if (typeof id === 'string') {
          return id;
        }
        // If it's a UUID object, convert to string
        return String(id);
      });

      console.log('Fetching clients with IDs:', clientIdStrings);

      // Fetch client details
      const clientsResponse = await fetch(`${API_BASE_URL}/api/users?role=client&ids=${clientIdStrings.join(',')}`, {
        headers: getAuthHeaders(),
      });

      if (!clientsResponse.ok) {
        const errorText = await clientsResponse.text();
        console.error('Failed to fetch clients:', clientsResponse.status, errorText);
        // If bulk fetch fails, try fetching individually or return empty
        return [];
      }

      const clientsData = await clientsResponse.json();
      console.log('Fetched clients data:', clientsData);
      
      // Handle both old format (array) and new format (paginated response)
      const usersArray = Array.isArray(clientsData) 
        ? clientsData 
        : (clientsData?.users || []);
      
      const clients: Client[] = usersArray.map((client: any) => ({
        id: client.id,
        email: client.email || '',
        name: client.name || 'Unknown',
        given_name: client.given_name,
        family_name: client.family_name,
        role: 'client' as const,
        is_active: client.is_active !== false,
        created_at: client.created_at || new Date().toISOString(),
      }));

      console.log('Mapped clients:', clients);
      return clients;
    } catch (error) {
      console.error('Error in fetchFirmClientsById:', error);
      // Fallback: try to get clients from engagements endpoint
      try {
        const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/engagements`, {
          headers: getAuthHeaders(),
        });

        if (response.ok) {
          const engagements = await response.json();
          // Extract unique client IDs from engagements
          const clientIds = new Set<string>();
          engagements.forEach((eng: any) => {
            if (eng.client_id) clientIds.add(eng.client_id);
          });

          // For now, return empty array - we'd need a user lookup endpoint
          console.warn('Fallback: Found client IDs from engagements but cannot fetch user details');
          return [];
        }
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError);
      }

      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch clients');
    }
  }
);

export const addClientToFirm = createAsyncThunk(
  'firm/addClientToFirm',
  async (
    { firmId, email, first_name, last_name }: { firmId: string; email: string; first_name?: string; last_name?: string },
    { rejectWithValue }
  ) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}/clients`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, first_name, last_name }),
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

export const revokeFirm = createAsyncThunk(
  'firm/revokeFirm',
  async (firmId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ is_active: false }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to revoke firm' }));
        throw new Error(errorData.detail || 'Failed to revoke firm');
      }

      const data = await response.json();
      return data as Firm;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to revoke firm');
    }
  }
);

export const reactivateFirm = createAsyncThunk(
  'firm/reactivateFirm',
  async (firmId: string, { rejectWithValue }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/firms/${firmId}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ is_active: true }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to reactivate firm' }));
        throw new Error(errorData.detail || 'Failed to reactivate firm');
      }

      const data = await response.json();
      return data as Firm;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to reactivate firm');
    }
  }
);

export const createFirm = createAsyncThunk(
  'firm/createFirm',
  async (firmData: { 
    firm_name: string; 
    admin_name: string;
    admin_email: string;
    subscription_id: string;
    billing_email?: string; 
  }, { rejectWithValue }) => {
    try {
      const headers = getAuthHeaders();

      // 1) Create a new user with firm_admin role
      const userResponse = await fetch(`${API_BASE_URL}/api/users`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          email: firmData.admin_email,
          name: firmData.admin_name,
          role: 'firm_admin',
        }),
      });

      if (!userResponse.ok) {
        const errorData = await userResponse.json().catch(() => ({ detail: 'Failed to create firm admin user' }));
        throw new Error(errorData.detail || 'Failed to create firm admin user');
      }

      const adminUser = await userResponse.json() as { id: string };

      // 2) Create the firm, assigning the new firm_admin
      const response = await fetch(`${API_BASE_URL}/api/firms`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          firm_name: firmData.firm_name,
          firm_admin_id: adminUser.id,
          subscription_id: firmData.subscription_id,
          billing_email: firmData.billing_email,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to create firm' }));
        throw new Error(errorData.detail || 'Failed to create firm');
      }

      const firm = await response.json() as Firm;
      return firm;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create firm');
    }
  }
);

const initialState: FirmState = {
  firms: [],
  firm: null,
  advisors: [],
  clients: [],
  stats: null,
  seats_used: null,
  seats_available: null,
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
    // Fetch firms (for super admin)
    builder
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

    // Fetch firm (for firm admin)
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

    // Fetch firm by ID (for superadmin)
    builder
      .addCase(fetchFirmById.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchFirmById.fulfilled, (state, action) => {
        state.isLoading = false;
        state.firm = action.payload;
      })
      .addCase(fetchFirmById.rejected, (state, action) => {
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
        state.advisors = action.payload.advisors;
        state.seats_used = action.payload.seats_used;
        state.seats_available = action.payload.seats_available;
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

    // Suspend advisor
    builder
      .addCase(suspendAdvisor.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(suspendAdvisor.fulfilled, (state, action) => {
        state.isLoading = false;
        // Update advisor in list
        const index = state.advisors.findIndex(a => a.id === action.payload.id);
        if (index !== -1) {
          state.advisors[index] = action.payload;
        }
        // NOTE: Do NOT decrement seats_used - suspended advisors still count as seats
      })
      .addCase(suspendAdvisor.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Reactivate advisor
    builder
      .addCase(reactivateAdvisor.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(reactivateAdvisor.fulfilled, (state, action) => {
        state.isLoading = false;
        // Update advisor in list
        const index = state.advisors.findIndex(a => a.id === action.payload.id);
        if (index !== -1) {
          state.advisors[index] = action.payload;
        }
      })
      .addCase(reactivateAdvisor.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
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

    // Fetch clients by firm ID
    builder
      .addCase(fetchFirmClientsById.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchFirmClientsById.fulfilled, (state, action) => {
        state.isLoading = false;
        state.clients = action.payload;
      })
      .addCase(fetchFirmClientsById.rejected, (state, action) => {
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

    // Create firm
    builder
      .addCase(createFirm.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(createFirm.fulfilled, (state, action) => {
        state.isLoading = false;
        // Add new firm to the list
        state.firms.push(action.payload);
      })
      .addCase(createFirm.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Revoke firm
    builder
      .addCase(revokeFirm.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(revokeFirm.fulfilled, (state, action) => {
        state.isLoading = false;
        // Update firm in the list
        const index = state.firms.findIndex(f => f.id === action.payload.id);
        if (index !== -1) {
          state.firms[index] = action.payload;
        }
        // Also update if it's the current firm
        if (state.firm && state.firm.id === action.payload.id) {
          state.firm = action.payload;
        }
      })
      .addCase(revokeFirm.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });

    // Reactivate firm
    builder
      .addCase(reactivateFirm.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(reactivateFirm.fulfilled, (state, action) => {
        state.isLoading = false;
        // Update firm in the list
        const index = state.firms.findIndex(f => f.id === action.payload.id);
        if (index !== -1) {
          state.firms[index] = action.payload;
        }
        // Also update if it's the current firm
        if (state.firm && state.firm.id === action.payload.id) {
          state.firm = action.payload;
        }
      })
      .addCase(reactivateFirm.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError } = firmSlice.actions;
export default firmSlice.reducer;
