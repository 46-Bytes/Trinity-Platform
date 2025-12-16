import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export type ToolType = 
  | 'diagnostic'
  | 'business-plan'
  | 'position-description'
  | 'org-redesign'
  | 'operating-rhythm'
  | 'kpi-builder'
  | 'policy-generator'
  // Add more tool types as you build them
  ;

export interface ToolResult {
  id: string;
  engagementId: string;
  toolType: ToolType;
  aiResponse: any; // AI-generated content
  generatedArtifacts: string[]; // File IDs of generated documents
  generatedTasks: string[]; // Task IDs created from this tool
  createdAt: string;
}

interface ToolState {
  // Tool results/outputs
  results: ToolResult[];
  
  // Loading states
  isLoading: boolean;
  isSaving: boolean;
  isSubmitting: boolean;
  
  // Error handling
  error: string | null;
  
  // Available tools metadata
  availableTools: {
    type: ToolType;
    name: string;
    description: string;
    category: string;
  }[];
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Async thunks
export const saveToolProgress = createAsyncThunk(
  'tool/saveProgress',
  async ({ 
    engagementId, 
    toolType, 
    responses, 
    currentPage, 
    completedPages 
  }: { 
    engagementId: string;
    toolType: ToolType;
    responses: Record<string, any>; 
    currentPage: number;
    completedPages: number[];
  }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/tools/progress`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ engagementId, toolType, responses, currentPage, completedPages }),
      });

      if (!response.ok) {
        throw new Error('Failed to save progress');
      }

      const data = await response.json();
      return data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to save progress');
    }
  }
);

export const submitTool = createAsyncThunk(
  'tool/submit',
  async ({ 
    engagementId, 
    toolType, 
    responses 
  }: { 
    engagementId: string;
    toolType: ToolType;
    responses: Record<string, any>; 
  }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/tools/submit`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ engagementId, toolType, responses }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit tool');
      }

      const data = await response.json();
      return data as ToolResult;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to submit tool');
    }
  }
);

export const fetchToolResults = createAsyncThunk(
  'tool/fetchResults',
  async (engagementId: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/tools/results?engagementId=${engagementId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch tool results');
      }

      const data = await response.json();
      return data.results || data;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch tool results');
    }
  }
);

// Initial state
const initialState: ToolState = {
  results: [],
  isLoading: false,
  isSaving: false,
  isSubmitting: false,
  error: null,
  availableTools: [
    {
      type: 'diagnostic',
      name: 'Business Health Diagnostic',
      description: 'Comprehensive business assessment survey',
      category: 'Assessment',
    },
    {
      type: 'business-plan',
      name: 'Business Plan Generator',
      description: 'AI-assisted business plan creation',
      category: 'Planning',
    },
    {
      type: 'position-description',
      name: 'Position Description Generator',
      description: 'Generate detailed job descriptions and role specifications',
      category: 'HR',
    },
    {
      type: 'org-redesign',
      name: 'Organisation Redesign Tool',
      description: 'Design optimal organizational structure',
      category: 'Strategy',
    },
    {
      type: 'operating-rhythm',
      name: 'Operating Rhythm Planner',
      description: 'Plan meetings and operational cadence',
      category: 'Operations',
    },
    {
      type: 'kpi-builder',
      name: 'KPI Builder',
      description: 'Define key performance indicators and metrics',
      category: 'Performance',
    },
    {
      type: 'policy-generator',
      name: 'Policy Generator',
      description: 'Generate company policies (AI Use, Privacy, etc.)',
      category: 'Governance',
    },
  ],
};

// Slice
const toolSlice = createSlice({
  name: 'tool',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      // Save progress
      .addCase(saveToolProgress.pending, (state) => {
        state.isSaving = true;
        state.error = null;
      })
      .addCase(saveToolProgress.fulfilled, (state) => {
        state.isSaving = false;
      })
      .addCase(saveToolProgress.rejected, (state, action) => {
        state.isSaving = false;
        state.error = action.payload as string;
      })
      
      // Submit tool
      .addCase(submitTool.pending, (state) => {
        state.isSubmitting = true;
        state.error = null;
      })
      .addCase(submitTool.fulfilled, (state, action) => {
        state.isSubmitting = false;
        state.results.push(action.payload);
      })
      .addCase(submitTool.rejected, (state, action) => {
        state.isSubmitting = false;
        state.error = action.payload as string;
      })
      
      // Fetch results
      .addCase(fetchToolResults.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchToolResults.fulfilled, (state, action) => {
        state.isLoading = false;
        state.results = action.payload;
      })
      .addCase(fetchToolResults.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const {
  clearError,
} = toolSlice.actions;

export default toolSlice.reducer;

