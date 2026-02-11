import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export interface Task {
  id: string;
  engagementId: string;
  engagementName?: string;
  diagnosticId?: string;
  assignedToUserIds?: string[];
  assignedToName?: string;
  createdByUserId: string;
  createdByName?: string;
  title: string;
  description?: string;
  taskType: 'manual' | 'diagnostic_generated';
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  priorityRank?: number;
  moduleReference?: string;
  impactLevel?: 'low' | 'medium' | 'high';
  effortLevel?: 'low' | 'medium' | 'high';
  dueDate?: string;
  completedAt?: string;
  createdAt: string;
  updatedAt: string;
  unreadNotesCountForCurrentUser?: number;
}

export interface TaskCreatePayload {
  engagementId: string;
  assignedToUserIds?: string[];
  createdByUserId: string;
  diagnosticId?: string;
  title: string;
  description?: string;
  taskType?: 'manual' | 'diagnostic_generated';
  status?: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  priorityRank?: number;
  moduleReference?: string;
  dueDate?: string;
}

export interface TaskUpdatePayload {
  title?: string;
  description?: string;
  status?: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  assignedToUserIds?: string[];
  dueDate?: string;
}

interface TaskState {
  tasks: Task[];
  selectedTask: Task | null;
  isLoading: boolean;
  error: string | null;
  filters: {
    engagementId?: string;
    assignedToUserId?: string;
    status?: string;
    priority?: string;
  };
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Helper function to map backend task to frontend format
function mapBackendTaskToFrontend(item: any): Task {
  // Handle both old format (assigned_to_user_id) and new format (assigned_to_user_ids)
  let assignedToUserIds: string[] | undefined = undefined;
  if (item.assigned_to_user_ids && item.assigned_to_user_ids.length > 0) {
    assignedToUserIds = item.assigned_to_user_ids.map((id: any) => String(id));
  } else if (item.assigned_to_user_id) {
    // Backward compatibility: convert single assignment to array
    assignedToUserIds = [String(item.assigned_to_user_id)];
  }
  
  return {
    id: item.id,
    engagementId: item.engagement_id,
    engagementName: item.engagement_name,
    diagnosticId: item.diagnostic_id,
    assignedToUserIds: assignedToUserIds,
    assignedToName: item.assigned_to_name,
    createdByUserId: item.created_by_user_id,
    createdByName: item.created_by_name,
    title: item.title,
    description: item.description,
    taskType: item.task_type || 'manual',
    status: item.status || 'pending',
    priority: item.priority || 'medium',
    priorityRank: item.priority_rank,
    moduleReference: item.module_reference,
    impactLevel: item.impact_level,
    effortLevel: item.effort_level,
    dueDate: item.due_date,
    completedAt: item.completed_at,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    unreadNotesCountForCurrentUser: item.unread_notes_count_for_current_user ?? 0,
  };
}


function mapFrontendTaskToBackend(task: TaskCreatePayload): any {
  return {
    engagement_id: task.engagementId,
    assigned_to_user_ids: task.assignedToUserIds || null,
    created_by_user_id: task.createdByUserId,
    diagnostic_id: task.diagnosticId || null,
    title: task.title,
    description: task.description || null,
    task_type: task.taskType || 'manual',
    status: task.status || 'pending',
    priority: task.priority || 'medium',
    priority_rank: task.priorityRank || null,
    module_reference: task.moduleReference || null,
    due_date: task.dueDate || null,
  };
}

// Async thunks
export const fetchTasks = createAsyncThunk(
  'task/fetchTasks',
  async (params: {
    engagementId?: string;
    assignedToUserId?: string;
    status?: string;
    priority?: string;
    skip?: number;
    limit?: number;
  } | undefined, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Build query string
      const queryParams = new URLSearchParams();
      if (params?.engagementId) {
        queryParams.append('engagement_id', params.engagementId);
      }
      if (params?.assignedToUserId) {
        queryParams.append('assigned_to_user_id', params.assignedToUserId);
      }
      if (params?.status) {
        queryParams.append('status_filter', params.status);
      }
      if (params?.priority) {
        queryParams.append('priority_filter', params.priority);
      }
      if (params?.skip !== undefined) {
        queryParams.append('skip', params.skip.toString());
      }
      if (params?.limit !== undefined) {
        queryParams.append('limit', params.limit.toString());
      }

      const url = `${API_BASE_URL}/api/tasks${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch tasks' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch tasks`);
      }

      const data = await response.json();
      
      // Transform backend data to match frontend Task interface
      const tasks: Task[] = (Array.isArray(data) ? data : []).map(mapBackendTaskToFrontend);

      return tasks;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch tasks');
    }
  }
);

export const fetchTaskById = createAsyncThunk(
  'task/fetchTaskById',
  async (id: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/tasks/${id}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch task' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch task`);
      }

      const data = await response.json();
      return mapBackendTaskToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch task');
    }
  }
);

export const createTask = createAsyncThunk(
  'task/createTask',
  async (task: TaskCreatePayload, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const backendPayload = mapFrontendTaskToBackend(task);

      const response = await fetch(`${API_BASE_URL}/api/tasks`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backendPayload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to create task' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create task`);
      }

      const data = await response.json();
      return mapBackendTaskToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create task');
    }
  }
);

export const updateTask = createAsyncThunk(
  'task/updateTask',
  async ({ id, updates }: { id: string; updates: TaskUpdatePayload }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Map frontend updates to backend format
      const backendUpdates: any = {};
      if (updates.title !== undefined) backendUpdates.title = updates.title;
      if (updates.description !== undefined) backendUpdates.description = updates.description;
      if (updates.status !== undefined) backendUpdates.status = updates.status;
      if (updates.priority !== undefined) backendUpdates.priority = updates.priority;
      if (updates.assignedToUserIds !== undefined) backendUpdates.assigned_to_user_ids = updates.assignedToUserIds || null;
      if (updates.dueDate !== undefined) backendUpdates.due_date = updates.dueDate || null;

      const response = await fetch(`${API_BASE_URL}/api/tasks/${id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backendUpdates),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to update task' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to update task`);
      }

      const data = await response.json();
      return mapBackendTaskToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update task');
    }
  }
);

export const deleteTask = createAsyncThunk(
  'task/deleteTask',
  async (id: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/tasks/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete task' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to delete task`);
      }

      return id;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to delete task');
    }
  }
);

// Initial state
const initialState: TaskState = {
  tasks: [],
  selectedTask: null,
  isLoading: false,
  error: null,
  filters: {},
};

// Slice
const taskSlice = createSlice({
  name: 'task',
  initialState,
  reducers: {
    setSelectedTask: (state, action: PayloadAction<Task | null>) => {
      state.selectedTask = action.payload;
    },
    setFilters: (state, action: PayloadAction<TaskState['filters']>) => {
      state.filters = { ...state.filters, ...action.payload };
    },
    clearFilters: (state) => {
      state.filters = {};
    },
    clearError: (state) => {
      state.error = null;
    },
    clearUnreadNotesForTask: (state, action: PayloadAction<string>) => {
      const taskId = action.payload;
      const task = state.tasks.find((t) => t.id === taskId);
      if (task) {
        task.unreadNotesCountForCurrentUser = 0;
      }
      if (state.selectedTask?.id === taskId) {
        state.selectedTask = {
          ...state.selectedTask,
          unreadNotesCountForCurrentUser: 0,
        };
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch all tasks
      .addCase(fetchTasks.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchTasks.fulfilled, (state, action) => {
        state.isLoading = false;
        state.tasks = action.payload;
      })
      .addCase(fetchTasks.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Fetch task by ID
      .addCase(fetchTaskById.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchTaskById.fulfilled, (state, action) => {
        state.isLoading = false;
        state.selectedTask = action.payload;
        // Also update in tasks array if it exists
        const index = state.tasks.findIndex((t) => t.id === action.payload.id);
        if (index !== -1) {
          state.tasks[index] = action.payload;
        } else {
          state.tasks.push(action.payload);
        }
      })
      .addCase(fetchTaskById.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Create task
      .addCase(createTask.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(createTask.fulfilled, (state, action) => {
        state.isLoading = false;
        state.tasks.push(action.payload);
      })
      .addCase(createTask.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Update task
      .addCase(updateTask.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(updateTask.fulfilled, (state, action) => {
        state.isLoading = false;
        const index = state.tasks.findIndex((t) => t.id === action.payload.id);
        if (index !== -1) {
          state.tasks[index] = action.payload;
        }
        if (state.selectedTask?.id === action.payload.id) {
          state.selectedTask = action.payload;
        }
      })
      .addCase(updateTask.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Delete task
      .addCase(deleteTask.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(deleteTask.fulfilled, (state, action) => {
        state.isLoading = false;
        state.tasks = state.tasks.filter((t) => t.id !== action.payload);
        if (state.selectedTask?.id === action.payload) {
          state.selectedTask = null;
        }
      })
      .addCase(deleteTask.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { setSelectedTask, setFilters, clearFilters, clearError, clearUnreadNotesForTask } = taskSlice.actions;
export default taskSlice.reducer;

