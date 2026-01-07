import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

// Types
export interface Subscription {
  id: string;
  firm_id?: string | null;
  plan_name: string;
  seat_count: number;
  monthly_price: number;
  status: 'active' | 'cancelled' | 'expired' | 'pending' | 'suspended';
  created_at: string;
  updated_at: string;
  current_period_end?: string; // End date of current billing period
}

interface SubscriptionState {
  subscriptions: Subscription[];
  isLoading: boolean;
  isCreating: boolean;
  error: string | null;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Async thunk to fetch all subscriptions
export const fetchSubscriptions = createAsyncThunk(
  'subscription/fetchSubscriptions',
  async (_, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/subscriptions`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch subscriptions' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch subscriptions`);
      }

      const data = await response.json();
      // Handle both array and object responses
      return Array.isArray(data) ? data : (data.subscriptions || []);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch subscriptions');
    }
  }
);

// Async thunk to create a subscription
export const createSubscription = createAsyncThunk(
  'subscription/createSubscription',
  async (subscriptionData: {
    plan_name: string;
    seat_count: number;
    billing_period: 'monthly' | 'annual';
    price: number;
    currency?: string;
  }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/subscriptions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(subscriptionData),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to create subscription' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create subscription`);
      }

      const data = await response.json();
      return data as Subscription;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create subscription');
    }
  }
);

// Initial state
const initialState: SubscriptionState = {
  subscriptions: [],
  isLoading: false,
  isCreating: false,
  error: null,
};

// Slice
const subscriptionSlice = createSlice({
  name: 'subscription',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch subscriptions
      .addCase(fetchSubscriptions.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchSubscriptions.fulfilled, (state, action) => {
        state.isLoading = false;
        state.subscriptions = action.payload;
      })
      .addCase(fetchSubscriptions.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Create subscription
      .addCase(createSubscription.pending, (state) => {
        state.isCreating = true;
        state.error = null;
      })
      .addCase(createSubscription.fulfilled, (state, action) => {
        state.isCreating = false;
        state.subscriptions.push(action.payload);
      })
      .addCase(createSubscription.rejected, (state, action) => {
        state.isCreating = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearError } = subscriptionSlice.actions;
export default subscriptionSlice.reducer;

