# File Upload POC - Complete Explanation

## 📍 Location
The POC (Proof of Concept) work is located in:
- **Frontend Route**: `/poc/file-upload` (accessible at `http://localhost:8080/poc/file-upload`)
- **Backend Endpoint**: `/api/upload` (and related endpoints)

---

## 🎯 What This POC Does

This is a **standalone proof of concept** for uploading files to **OpenAI Files API**. It demonstrates:

1. **Multiple File Upload**: Upload multiple files at once
2. **OpenAI Integration**: Automatically forwards files to OpenAI Files API and gets back `file_id`s
3. **Session Management**: Stores filename → file_id mappings in server session
4. **Drag-and-Drop UI**: Modern React interface with drag-and-drop support
5. **File Validation**: Frontend validation for file size (max 100MB) and file types
6. **Real-time Status**: Shows upload progress and status for each file

---

## 📁 Related Files & Their Functions

### **Frontend Files**

#### 1. `frontend/src/pages/poc/FileUploadPOCPage.tsx`
**Purpose**: Page wrapper component that renders the POC
- **Function**: Simple page component that displays the POC title and renders the main `FileUploadPOC` component
- **Route**: Registered in `App.tsx` at `/poc/file-upload`

#### 2. `frontend/src/components/poc/FileUploadPOC.tsx`
**Purpose**: Main React component with all the UI and upload logic
- **Functions**:
  - **`validateFile()`**: Validates file size (max 100MB) and file type (PDF, DOCX, XLSX, images, etc.)
  - **`addFiles()`**: Adds files to the upload queue after validation
  - **`handleFileInputChange()`**: Handles file selection via file input
  - **`handleDragEnter/Leave/Over/Drop()`**: Handles drag-and-drop functionality
  - **`handleUpload()`**: 
    - Creates FormData with selected files
    - Sends POST request to `/api/upload`
    - Updates file status (pending → uploading → success/error)
    - Displays OpenAI file_id for successful uploads
  - **`removeFile()`**: Removes a file from the list
  - **`clearAll()`**: Clears all files from the list
- **UI Features**:
  - Drag-and-drop zone
  - File list with status indicators
  - Progress bars for uploading files
  - Display of OpenAI file_ids
  - File mappings display

#### 3. `frontend/src/App.tsx` (Line 38, 63)
**Purpose**: Registers the POC route
- **Function**: Adds route `/poc/file-upload` that renders `FileUploadPOCPage`

---

### **Backend Files**

#### 4. `backend/app/api/upload_poc.py`
**Purpose**: Backend API endpoints for the POC
- **Functions**:

  **`POST /api/upload`** (Lines 17-147):
  - Accepts multiple files via `multipart/form-data`
  - For each file:
    1. Reads file content
    2. Creates temporary file
    3. Uploads to OpenAI Files API using `OpenAIService.upload_file()`
    4. Gets back `file_id` from OpenAI
    5. Stores filename → file_id mapping in session
    6. Cleans up temporary file
  - Returns JSON with:
    - Success status
    - List of files with their OpenAI file_ids
    - File mappings dictionary
    - Upload statistics

  **`GET /api/upload/mappings`** (Lines 150-174):
  - Retrieves all filename → file_id mappings from session
  - Returns JSON with mappings and count

  **`DELETE /api/upload/mappings`** (Lines 177-195):
  - Clears all file mappings from session
  - Returns success message

#### 5. `backend/app/main.py` (Lines 17, 82)
**Purpose**: Registers the POC router
- **Function**: Includes `upload_poc_router` in the FastAPI app

---

### **Supporting Files**

#### 6. `backend/app/services/openai_service.py`
**Purpose**: OpenAI API integration service (used by POC)
- **Function**: `upload_file()` method uploads files to OpenAI Files API
- **Note**: This is the main OpenAI service used throughout the app

#### 7. `POC_FILE_UPLOAD_README.md`
**Purpose**: Documentation for the POC
- **Function**: Explains features, API endpoints, usage, and file structure

---

## 🔄 Complete Workflow

```
1. User navigates to /poc/file-upload
   ↓
2. FileUploadPOCPage renders FileUploadPOC component
   ↓
3. User drags/drops or selects files
   ↓
4. Frontend validates files (size, type)
   ↓
5. User clicks "Upload" button
   ↓
6. Frontend sends POST /api/upload with FormData
   ↓
7. Backend (upload_poc.py):
   - Receives files
   - For each file:
     a. Creates temp file
     b. Calls OpenAIService.upload_file()
     c. Gets OpenAI file_id
     d. Stores mapping in session
     e. Cleans up temp file
   ↓
8. Backend returns JSON with file_ids
   ↓
9. Frontend updates UI:
   - Shows success/error status
   - Displays OpenAI file_id for each file
   - Shows file mappings
```

---

## 🎨 UI Features

1. **Drag-and-Drop Zone**: Visual feedback when dragging files
2. **File List**: Shows each file with:
   - File name and size
   - Upload status (pending/uploading/success/error)
   - Progress bar during upload
   - OpenAI file_id (on success)
   - Error message (on failure)
3. **File Mappings Display**: Shows all filename → file_id mappings
4. **Statistics**: Shows total, pending, success, and error counts

---

## 🔧 Technical Details

### File Validation Rules
- **Max Size**: 100 MB
- **Allowed Types**: 
  - PDF (`application/pdf`)
  - Word (`application/msword`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
  - Excel (`application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`)
  - Text (`text/plain`, `text/csv`, `text/markdown`)
  - Images (`image/jpeg`, `image/png`, `image/gif`)
  - JSON (`application/json`)

### Session Storage
- Uses FastAPI's `SessionMiddleware`
- Stores mappings in `request.session["file_mappings"]`
- Session-specific (cleared when session expires)
- Requires cookies to work

### OpenAI Integration
- Uses `purpose="assistants"` for all uploads
- Returns `file_id` that can be used with OpenAI Assistants API
- Files are stored in OpenAI's system (not locally)

---

## 🚀 How to Use/Play Around

1. **Start the servers**:
   ```bash
   # Backend
   cd backend
   python -m uvicorn app.main:app --reload
   
   # Frontend
   cd frontend
   npm run dev
   ```

2. **Navigate to**: `http://localhost:8080/poc/file-upload`

3. **Test the POC**:
   - Drag and drop files or click "Select Files"
   - Files are validated on the frontend
   - Click "Upload" to send to backend
   - Watch files upload to OpenAI
   - See OpenAI file_ids displayed
   - Check file mappings in the session

4. **Test API endpoints directly**:
   ```bash
   # Upload files
   curl -X POST http://localhost:8000/api/upload \
     -F "files=@document.pdf" \
     -F "files=@spreadsheet.xlsx" \
     -H "Cookie: session=your-session-cookie"
   
   # Get mappings
   curl http://localhost:8000/api/upload/mappings \
     -H "Cookie: session=your-session-cookie"
   
   # Clear mappings
   curl -X DELETE http://localhost:8000/api/upload/mappings \
     -H "Cookie: session=your-session-cookie"
   ```

---

## 🔍 Key Differences from Main System

This POC is **intentionally separate** from the main file upload system:

| Feature | POC | Main System |
|---------|-----|-------------|
| Endpoint | `/api/upload` | `/api/files/upload` |
| Storage | Session state | Database |
| Authentication | Optional | Required |
| Purpose | Testing OpenAI integration | Production file management |

---

## 📝 Notes for Development

- **Session-based**: Mappings are stored in session, not database
- **Temporary files**: Created during upload, automatically cleaned up
- **No persistence**: File mappings are lost when session expires
- **Standalone**: Can be modified/experimented with without affecting main system
- **OpenAI dependency**: Requires valid OpenAI API key in environment

---

## 🎯 Use Cases

This POC is useful for:
1. Testing OpenAI Files API integration
2. Experimenting with file upload UI/UX
3. Understanding how to integrate OpenAI file uploads
4. Prototyping features before adding to main system
5. Learning how session state works in FastAPI

