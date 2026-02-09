# File Upload POC - OpenAI Files API Integration

This is a standalone Proof of Concept (POC) for file upload functionality with OpenAI Files API integration. It is completely separate from the main file upload system.

## Features

1. **Multiple File Upload**: Accepts multiple files in a single request
2. **OpenAI Files API Integration**: Automatically uploads files to OpenAI and retrieves file_ids
3. **Session State Management**: Stores filename → file_id mappings in session state
4. **Drag-and-Drop Interface**: Modern React component with drag-and-drop functionality
5. **File Validation**: Frontend validation for file size and file types
6. **Upload Status Display**: Shows real-time upload status for each file

## Backend Endpoints

### POST `/api/upload`
- Accepts multiple file uploads
- Forwards each file to OpenAI Files API
- Returns file_id for each uploaded file
- Stores filename → file_id mapping in session state

**Request:**
- `files`: List of files (multipart/form-data)

**Response:**
```json
{
  "success": true,
  "message": "Processed 2 file(s)",
  "files": [
    {
      "filename": "document.pdf",
      "file_id": "file-abc123",
      "status": "success",
      "size": 1024000,
      "openai_info": {
        "bytes": 1024000,
        "purpose": "assistants",
        "created_at": 1234567890
      }
    }
  ],
  "file_mapping": {
    "document.pdf": "file-abc123"
  },
  "total_files": 2,
  "successful_uploads": 2
}
```

### GET `/api/upload/mappings`
- Retrieves current file_id mappings from session state

**Response:**
```json
{
  "success": true,
  "file_mappings": {
    "document.pdf": "file-abc123",
    "spreadsheet.xlsx": "file-xyz789"
  },
  "count": 2
}
```

### DELETE `/api/upload/mappings`
- Clears all file_id mappings from session state

**Response:**
```json
{
  "success": true,
  "message": "File mappings cleared"
}
```

## Frontend Component

### FileUploadPOC Component
Location: `frontend/src/components/poc/FileUploadPOC.tsx`

**Features:**
- Drag-and-drop file upload
- File validation (max size: 100MB, allowed types: PDF, DOCX, XLSX, images, etc.)
- Real-time upload status
- Display of OpenAI file_ids
- File removal functionality

### File Validation Rules
- **Max File Size**: 100 MB
- **Allowed Types**:
  - PDF documents
  - Microsoft Office documents (Word, Excel)
  - Text files (TXT, CSV, Markdown)
  - Images (JPEG, PNG, GIF)
  - JSON files

## Usage

### Access the POC Page
Navigate to: `http://localhost:8080/poc/file-upload` (or your frontend URL)

### Upload Files
1. Drag and drop files onto the upload area, or click "Select Files"
2. Files will be validated on the frontend
3. Click "Upload" to send files to the backend
4. Backend will forward files to OpenAI Files API
5. File IDs will be displayed and stored in session

### View File Mappings
The component displays all successful uploads with their OpenAI file_ids. These mappings are also stored in the session state and can be retrieved via the `/api/upload/mappings` endpoint.

## File Structure

```
backend/
  app/
    api/
      upload_poc.py          # POC backend endpoint

frontend/
  src/
    components/
      poc/
        FileUploadPOC.tsx    # POC React component
    pages/
      poc/
        FileUploadPOCPage.tsx # POC page
```

## Integration Notes

This POC is intentionally separate from the main system:
- Uses different endpoint (`/api/upload` vs `/api/files/upload`)
- No database integration (uses session state only)
- No authentication required (though it will use auth token if available)
- Simplified error handling

## Testing

1. Start the backend server
2. Start the frontend development server
3. Navigate to `/poc/file-upload`
4. Upload test files and verify:
   - Files are validated on frontend
   - Files are uploaded to OpenAI
   - File IDs are returned and displayed
   - File mappings are stored in session

## Dependencies

- Backend: Uses existing `OpenAIService` for OpenAI API integration
- Frontend: Uses shadcn/ui components (Card, Button, Progress)
- Session: Uses FastAPI SessionMiddleware (already configured)

## Notes

- Session state is stored server-side and requires cookies to work
- File mappings are session-specific and will be cleared when session expires
- Temporary files are created during upload and automatically cleaned up
- OpenAI file uploads use the "assistants" purpose by default
