import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';

// Types
export interface Note {
  id: string;
  engagementId: string;
  engagementName?: string;
  diagnosticId?: string;
  taskId?: string;
  authorId: string;
  authorName?: string;
  title?: string;
  content: string;
  noteType: 'general' | 'meeting' | 'observation' | 'decision' | 'progress_update';
  isPinned: boolean;
  visibility: 'all' | 'advisor_only' | 'client_only';
  tags?: string[];
  attachments?: any[];
  readBy?: string[];
  createdAt: string;
  updatedAt: string;
}

export interface NoteCreatePayload {
  engagementId: string;
  taskId?: string;
  diagnosticId?: string;
  title?: string;
  content: string;
  noteType?: 'general' | 'meeting' | 'observation' | 'decision' | 'progress_update';
  isPinned?: boolean;
  visibility?: 'all' | 'advisor_only' | 'client_only';
  tags?: string[];
  attachments?: any[];
}

export interface NoteUpdatePayload {
  title?: string;
  content?: string;
  noteType?: 'general' | 'meeting' | 'observation' | 'decision' | 'progress_update';
  isPinned?: boolean;
  visibility?: 'all' | 'advisor_only' | 'client_only';
  tags?: string[];
  attachments?: any[];
}

interface NoteState {
  notes: Note[];
  selectedNote: Note | null;
  isLoading: boolean;
  error: string | null;
  filters: {
    engagementId?: string;
    taskId?: string;
    noteType?: string;
  };
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Helper function to map backend note to frontend format
function mapBackendNoteToFrontend(item: any): Note {
  return {
    id: item.id,
    engagementId: item.engagement_id,
    engagementName: item.engagement_name,
    diagnosticId: item.diagnostic_id,
    taskId: item.task_id,
    authorId: item.author_id,
    authorName: item.author_name,
    title: item.title,
    content: item.content,
    noteType: item.note_type || 'general',
    isPinned: item.is_pinned || false,
    visibility: item.visibility || 'all',
    tags: item.tags || [],
    attachments: item.attachments || [],
    readBy: Array.isArray(item.read_by) ? item.read_by.map((id: any) => String(id)) : [],
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  };
}

// Helper function to map frontend note to backend format
function mapFrontendNoteToBackend(note: NoteCreatePayload): any {
  return {
    engagement_id: note.engagementId,
    task_id: note.taskId || null,
    diagnostic_id: note.diagnosticId || null,
    title: note.title || null,
    content: note.content,
    note_type: note.noteType || 'general',
    is_pinned: note.isPinned || false,
    visibility: note.visibility || 'all',
    tags: note.tags || [],
    attachments: note.attachments || [],
    author_id: '', // Will be set by backend from current user
  };
}

// Async thunks
export const fetchNotes = createAsyncThunk(
  'note/fetchNotes',
  async (params: {
    engagementId?: string;
    taskId?: string;
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
      if (params?.taskId) {
        queryParams.append('task_id', params.taskId);
      }
      if (params?.skip !== undefined) {
        queryParams.append('skip', params.skip.toString());
      }
      if (params?.limit !== undefined) {
        queryParams.append('limit', params.limit.toString());
      }

      const url = `${API_BASE_URL}/api/notes${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch notes' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch notes`);
      }

      const data = await response.json();
      
      // Transform backend data to match frontend Note interface
      const notes: Note[] = (Array.isArray(data) ? data : []).map(mapBackendNoteToFrontend);

      return notes;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to fetch notes');
    }
  }
);

export const createNote = createAsyncThunk(
  'note/createNote',
  async (note: NoteCreatePayload, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const backendPayload = mapFrontendNoteToBackend(note);

      const response = await fetch(`${API_BASE_URL}/api/notes`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backendPayload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to create note' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create note`);
      }

      const data = await response.json();
      return mapBackendNoteToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to create note');
    }
  }
);

export const updateNote = createAsyncThunk(
  'note/updateNote',
  async ({ id, updates }: { id: string; updates: NoteUpdatePayload }, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      // Map frontend updates to backend format
      const backendUpdates: any = {};
      if (updates.title !== undefined) backendUpdates.title = updates.title;
      if (updates.content !== undefined) backendUpdates.content = updates.content;
      if (updates.noteType !== undefined) backendUpdates.note_type = updates.noteType;
      if (updates.isPinned !== undefined) backendUpdates.is_pinned = updates.isPinned;
      if (updates.visibility !== undefined) backendUpdates.visibility = updates.visibility;
      if (updates.tags !== undefined) backendUpdates.tags = updates.tags;
      if (updates.attachments !== undefined) backendUpdates.attachments = updates.attachments;

      const response = await fetch(`${API_BASE_URL}/api/notes/${id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backendUpdates),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to update note' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to update note`);
      }

      const data = await response.json();
      return mapBackendNoteToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to update note');
    }
  }
);

export const deleteNote = createAsyncThunk(
  'note/deleteNote',
  async (id: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/notes/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete note' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to delete note`);
      }

      return id;
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to delete note');
    }
  }
);

export const markNoteRead = createAsyncThunk(
  'note/markNoteRead',
  async (id: string, { rejectWithValue }) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(`${API_BASE_URL}/api/notes/${id}/read`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to mark note as read' }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to mark note as read`);
      }

      const data = await response.json();
      return mapBackendNoteToFrontend(data);
    } catch (error) {
      return rejectWithValue(error instanceof Error ? error.message : 'Failed to mark note as read');
    }
  }
);

// Initial state
const initialState: NoteState = {
  notes: [],
  selectedNote: null,
  isLoading: false,
  error: null,
  filters: {},
};

// Slice
const noteSlice = createSlice({
  name: 'note',
  initialState,
  reducers: {
    setSelectedNote: (state, action: PayloadAction<Note | null>) => {
      state.selectedNote = action.payload;
    },
    setFilters: (state, action: PayloadAction<NoteState['filters']>) => {
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
      // Fetch all notes
      .addCase(fetchNotes.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchNotes.fulfilled, (state, action) => {
        state.isLoading = false;
        state.notes = action.payload;
      })
      .addCase(fetchNotes.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Create note
      .addCase(createNote.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(createNote.fulfilled, (state, action) => {
        state.isLoading = false;
        state.notes.push(action.payload);
      })
      .addCase(createNote.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Update note
      .addCase(updateNote.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(updateNote.fulfilled, (state, action) => {
        state.isLoading = false;
        const index = state.notes.findIndex((n) => n.id === action.payload.id);
        if (index !== -1) {
          state.notes[index] = action.payload;
        }
        if (state.selectedNote?.id === action.payload.id) {
          state.selectedNote = action.payload;
        }
      })
      .addCase(updateNote.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      // Delete note
      .addCase(deleteNote.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(deleteNote.fulfilled, (state, action) => {
        state.isLoading = false;
        state.notes = state.notes.filter((n) => n.id !== action.payload);
        if (state.selectedNote?.id === action.payload) {
          state.selectedNote = null;
        }
      })
      .addCase(deleteNote.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      })
      .addCase(markNoteRead.fulfilled, (state, action) => {
        const updatedNote = action.payload;
        const index = state.notes.findIndex((n) => n.id === updatedNote.id);
        if (index !== -1) {
          state.notes[index] = updatedNote;
        }
        if (state.selectedNote?.id === updatedNote.id) {
          state.selectedNote = updatedNote;
        }
      });
  },
});

export const { setSelectedNote, setFilters, clearFilters, clearError } = noteSlice.actions;
export default noteSlice.reducer;

