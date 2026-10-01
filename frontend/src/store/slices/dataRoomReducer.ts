import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';

/**
 * The Sale Ready data room: files filed against DD sub-items, stored in Drive.
 *
 * Trinity is the working interface: files are listed, uploaded and downloaded
 * through it, and the ids below are Trinity's own. Drive links are carried
 * alongside, for the advisor and the owner, who may open a folder or a file
 * there when it suits them. The buyer's slice has no link field at all.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const BASE = `${API_BASE_URL}/api/sale-ready/engagements`;

export interface DataRoomFile {
  id: string;
  file_name: string;
  file_size: number | null;
  file_type: string | null;
  category_code: string | null;
  sub_item_code: string | null;
  uploaded_by_name: string | null;
  source: 'trinity' | 'drive' | null;
  created_at: string | null;
  /** The DD item it was uploaded to; null for Files-tab uploads and files added in Drive. */
  dd_item_id: string | null;
  dd_item_document: string | null;
  /** Advisor and owner only. Null until the file exists in Drive. */
  drive_web_link: string | null;
}

export interface DataRoomFolder {
  category_code: string;
  category: string | null;
  sub_item_code: string;
  sub_item: string | null;
  released_to_buyers: boolean;
  file_count: number;
  /** Advisor and owner only. Null until Trinity has created the folder in Drive. */
  drive_web_link: string | null;
}

export interface DataRoomStatus {
  connected: boolean;
  message: string | null;
}

export interface RegisterEntry {
  media_id: string;
  file_name: string;
  sub_item_code: string | null;
  sub_item: string | null;
  added_at: string | null;
  document_id: string | null;
  renewal_date: string | null;
  renewal_cost: number | null;
  notes: string | null;
  /** Advisor only. Null until the file exists in Drive. */
  drive_web_link: string | null;
}

interface DataRoomState {
  status: DataRoomStatus | null;
  folders: DataRoomFolder[];
  files: DataRoomFile[];
  /** The engagement's Data room folder in Drive. Advisor and owner only. */
  dataRoomWebLink: string | null;
  /** Keyed by stage code: a register is generated per stage. */
  register: Record<string, RegisterEntry[]>;
  isLoading: boolean;
  isUploading: boolean;
  error: string | null;
  /** The engagement the loaded state belongs to. */
  loadedFor: string | null;
}

const initialState: DataRoomState = {
  loadedFor: null,
  status: null,
  folders: [],
  files: [],
  dataRoomWebLink: null,
  register: {},
  isLoading: false,
  isUploading: false,
  error: null,
};

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, fallback: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...authHeaders(),
      ...(init.headers || {}),
    },
    credentials: 'include',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallback);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const thunk = <Arg, Result>(name: string, fallback: string, run: (arg: Arg) => Promise<Result>) =>
  createAsyncThunk<Result, Arg, { rejectValue: string }>(
    `dataRoom/${name}`,
    async (arg, { rejectWithValue }) => {
      try {
        return await run(arg);
      } catch (e) {
        return rejectWithValue(e instanceof Error ? e.message : fallback);
      }
    }
  );

interface DataRoomPayload {
  status: DataRoomStatus;
  folders: DataRoomFolder[];
  files: DataRoomFile[];
  data_room_web_link: string | null;
}

export const fetchDataRoom = thunk<string, DataRoomPayload>(
  'fetch',
  'Failed to load the data room',
  (engagementId) => request<DataRoomPayload>(`/${engagementId}/data-room`, 'Failed to load the data room')
);

export const uploadDDItemFile = thunk<
  { engagementId: string; itemId: string; file: File },
  DataRoomFile
>('uploadDDItem', 'Failed to upload the file', ({ engagementId, itemId, file }) => {
  const form = new FormData();
  form.append('file', file);
  return request<DataRoomFile>(`/${engagementId}/dd/${itemId}/files`, 'Failed to upload the file', {
    method: 'POST',
    body: form,
  });
});

export const renameDataRoomFile = thunk<
  { engagementId: string; mediaId: string; file_name: string },
  DataRoomFile
>('rename', 'Failed to rename the file', ({ engagementId, mediaId, file_name }) =>
  request<DataRoomFile>(`/${engagementId}/data-room/files/${mediaId}`, 'Failed to rename the file', {
    method: 'PATCH',
    body: JSON.stringify({ file_name }),
  })
);

export const deleteDataRoomFile = thunk<{ engagementId: string; mediaId: string }, string>(
  'delete',
  'Failed to remove the file',
  async ({ engagementId, mediaId }) => {
    await request<void>(`/${engagementId}/data-room/files/${mediaId}`, 'Failed to remove the file', {
      method: 'DELETE',
    });
    return mediaId;
  }
);

export const fetchRegister = thunk<
  { engagementId: string; stageCode: string },
  { stageCode: string; entries: RegisterEntry[] }
>('fetchRegister', 'Failed to load the document register', async ({ engagementId, stageCode }) => ({
  stageCode,
  entries: await request<RegisterEntry[]>(
    `/${engagementId}/stages/${stageCode}/register`,
    'Failed to load the document register'
  ),
}));

export const updateRegisterEntry = thunk<
  {
    engagementId: string;
    stageCode: string;
    mediaId: string;
    changes: Partial<Pick<RegisterEntry, 'document_id' | 'renewal_date' | 'renewal_cost' | 'notes'>>;
  },
  { stageCode: string; entry: RegisterEntry }
>('updateRegister', 'Failed to save the register', async ({ engagementId, stageCode, mediaId, changes }) => ({
  stageCode,
  entry: await request<RegisterEntry>(
    `/${engagementId}/stages/${stageCode}/register/${mediaId}`,
    'Failed to save the register',
    { method: 'PATCH', body: JSON.stringify(changes) }
  ),
}));

/**
 * Download through Trinity, with the bearer token attached.
 *
 * A plain anchor cannot carry the Authorization header, and the endpoint is
 * deliberately authenticated, so the file is fetched and handed to the browser
 * as a blob. No Drive URL is involved at any point.
 */
export async function downloadDataRoomFile(
  engagementId: string,
  mediaId: string,
  fileName: string
): Promise<void> {
  const response = await fetch(`${BASE}/${engagementId}/data-room/files/${mediaId}/download`, {
    headers: authHeaders(),
    credentials: 'include',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'Failed to download the file');
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

const slice = createSlice({
  name: 'dataRoom',
  initialState,
  reducers: {
    clearDataRoom: () => initialState,
  },
  extraReducers: (builder) => {
    builder.addCase(fetchDataRoom.fulfilled, (state, action) => {
      state.loadedFor = action.meta.arg;
      state.status = action.payload.status;
      state.folders = action.payload.folders;
      state.files = action.payload.files;
      state.dataRoomWebLink = action.payload.data_room_web_link;
    });
    builder.addCase(uploadDDItemFile.fulfilled, (state, action) => {
      if (state.loadedFor !== action.meta.arg.engagementId) return;
      state.files = [...state.files, action.payload];
      const key = `${action.payload.category_code}|${action.payload.sub_item_code}`;
      state.folders = state.folders.map((f) =>
        `${f.category_code}|${f.sub_item_code}` === key ? { ...f, file_count: f.file_count + 1 } : f
      );
    });
    builder.addCase(renameDataRoomFile.fulfilled, (state, action) => {
      state.files = state.files.map((f) => (f.id === action.payload.id ? action.payload : f));
    });
    builder.addCase(deleteDataRoomFile.fulfilled, (state, action) => {
      const gone = state.files.find((f) => f.id === action.payload);
      state.files = state.files.filter((f) => f.id !== action.payload);
      if (gone) {
        const key = `${gone.category_code}|${gone.sub_item_code}`;
        state.folders = state.folders.map((f) =>
          `${f.category_code}|${f.sub_item_code}` === key
            ? { ...f, file_count: Math.max(0, f.file_count - 1) }
            : f
        );
      }
    });
    builder.addCase(fetchRegister.fulfilled, (state, action) => {
      state.register[action.payload.stageCode] = action.payload.entries;
    });
    builder.addCase(updateRegisterEntry.fulfilled, (state, action) => {
      const rows = state.register[action.payload.stageCode] ?? [];
      state.register[action.payload.stageCode] = rows.map((r) =>
        r.media_id === action.payload.entry.media_id ? { ...r, ...action.payload.entry } : r
      );
    });

    builder.addMatcher(
      (a) => a.type.startsWith('dataRoom/') && a.type.endsWith('/pending'),
      (state, action: { type: string }) => {
        state.error = null;
        if (action.type.includes('/upload')) state.isUploading = true;
        else state.isLoading = true;
      }
    );
    builder.addMatcher(
      (a) => a.type.startsWith('dataRoom/') && a.type.endsWith('/fulfilled'),
      (state) => {
        state.isLoading = false;
        state.isUploading = false;
      }
    );
    builder.addMatcher(
      (a) => a.type.startsWith('dataRoom/') && a.type.endsWith('/rejected'),
      (state, action: { payload?: string }) => {
        state.isLoading = false;
        state.isUploading = false;
        state.error = action.payload ?? 'Something went wrong';
      }
    );
  },
});

export const { clearDataRoom } = slice.actions;
export default slice.reducer;
