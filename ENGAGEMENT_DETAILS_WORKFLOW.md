# Engagement Details Page - Complete Workflow Documentation

## Overview
This document explains the complete end-to-end workflow from backend to frontend for the Engagement Details page, including what each file does and how data flows through the system.

---

## 🎯 Frontend Entry Point

### **File: `frontend/src/pages/dashboard/Engagement/EngagementDetailPage.tsx`**

**Purpose:** Main page component that displays engagement details with tabs for Overview, Tasks, Diagnostic, and Chatbot.

**What it does:**
1. **Gets engagement ID from URL** (`useParams`)
2. **Fetches diagnostics** for the engagement
3. **Manages 4 tabs:**
   - Overview: Shows generated files and uploaded files
   - Tasks: Shows tasks list
   - Diagnostic: Shows diagnostic survey
   - Chatbot: Shows AI chatbot

**Key Functions:**

#### `fetchDiagnostics()` (Lines 33-82)
- **API Call 1:** `GET /api/diagnostics/engagement/{engagementId}`
  - Gets list of all diagnostics for this engagement
  - Returns: Array of diagnostic summaries (id, status, created_at, etc.)
  
- **API Call 2:** For each diagnostic, `GET /api/diagnostics/{diagnostic_id}`
  - Gets full diagnostic details including `user_responses`
  - Needed to extract file metadata from responses
  
- **Polling:** If any diagnostic has status "processing", polls every 5 seconds

#### `generatedFiles` (Lines 113-136)
- **Extracts diagnostic report PDFs** from diagnostics
- Creates file objects for completed/processing diagnostics
- Used in "Generated Files" section

#### `uploadedFiles` (Lines 139-217)
- **Extracts uploaded file metadata** from `user_responses`
- Iterates through all response fields
- Finds file metadata objects (with `file_name` property)
- Creates file objects for display
- Used in "Uploaded Files" section

#### `handleDownload()` (Lines 219-284)
- **Downloads diagnostic report PDFs**
- **API Call:** `GET /api/diagnostics/{diagnosticId}/download`
- Creates blob and triggers browser download

---

## 🔌 Backend API Endpoints

### **File: `backend/app/api/diagnostics.py`**

#### **1. List Diagnostics for Engagement**
```python
GET /api/diagnostics/engagement/{engagement_id}
```
**Handler:** `list_engagement_diagnostics()` (Line 644)

**What it does:**
- Calls `service.get_engagement_diagnostics(engagement_id)`
- Returns list of diagnostics (summary format)
- Used by frontend to get all diagnostics for an engagement

**Response:** `List[DiagnosticListItem]`
```json
[
  {
    "id": "uuid",
    "status": "completed",
    "created_at": "2024-01-01T00:00:00",
    "overall_score": 4.5,
    ...
  }
]
```

#### **2. Get Single Diagnostic Details**
```python
GET /api/diagnostics/{diagnostic_id}
```
**Handler:** `get_diagnostic()` (Line 250)

**What it does:**
- Calls `service.get_diagnostic(diagnostic_id)`
- Returns full diagnostic including:
  - `questions` (full survey structure)
  - `user_responses` (all user answers + file metadata)
  - `scoring_data`, `ai_analysis`, `module_scores`
  - `report_html`, etc.

**Response:** `DiagnosticDetail` (full diagnostic object)

#### **3. Download Diagnostic Report**
```python
GET /api/diagnostics/{diagnostic_id}/download
```
**Handler:** `download_diagnostic_report()` (Line 705)

**What it does:**
- Gets diagnostic from database
- Generates PDF report using `ReportService.generate_pdf_report()`
- Returns PDF file as binary response
- Sets `Content-Disposition` header for filename

---

## 🏗️ Backend Services

### **File: `backend/app/services/diagnostic_service.py`**

#### **1. `get_engagement_diagnostics()` (Line 827)**
**Purpose:** Get all diagnostics for an engagement

**What it does:**
```python
def get_engagement_diagnostics(self, engagement_id: UUID) -> list:
    return self.db.query(Diagnostic).filter(
        Diagnostic.engagement_id == engagement_id
    ).order_by(Diagnostic.created_at.desc()).all()
```

- Queries database for all diagnostics with matching `engagement_id`
- Orders by creation date (newest first)
- Returns list of Diagnostic model objects

#### **2. `get_diagnostic()` (Line 821)**
**Purpose:** Get single diagnostic by ID

**What it does:**
```python
def get_diagnostic(self, diagnostic_id: UUID) -> Optional[Diagnostic]:
    return self.db.query(Diagnostic).filter(
        Diagnostic.id == diagnostic_id
    ).first()
```

- Queries database for diagnostic by ID
- Returns Diagnostic model object (includes all relationships)

#### **3. `_get_current_files_from_responses()` (Line 555)**
**Purpose:** Extract only files currently in `user_responses` (not stale files)

**What it does:**
1. Iterates through all fields in `user_responses`
2. Extracts `media_id` from file metadata objects
3. Queries Media table by those IDs
4. Verifies files are attached to diagnostic
5. Returns list of Media objects

**Why:** Ensures only files the user currently has are used for scoring, not old files.

---

## 📊 Database Models

### **File: `backend/app/models/diagnostic.py`**

**Model: `Diagnostic`**

**Key Fields:**
- `id`: UUID (primary key)
- `engagement_id`: UUID (foreign key to Engagement)
- `status`: String (draft, in_progress, processing, completed, failed)
- `questions`: JSONB (full survey structure from JSON file)
- `user_responses`: JSONB (user answers + file metadata)
- `scoring_data`: JSONB (question-level scores)
- `ai_analysis`: JSONB (roadmap, advisor report, summary)
- `module_scores`: JSONB (M1-M8 module scores)
- `overall_score`: Numeric (0-5)
- `report_html`: Text (HTML version of report)

**Relationships:**
- `media`: Many-to-many with Media (via `diagnostic_media` table)
- `tasks`: One-to-many with Task
- `engagement`: Many-to-one with Engagement

### **File: `backend/app/models/media.py`**

**Model: `Media`**

**Key Fields:**
- `id`: UUID (primary key)
- `user_id`: UUID (who uploaded it)
- `file_name`: String (original filename)
- `file_path`: Text (storage path)
- `file_extension`: String (pdf, txt, xlsx, etc.)
- `openai_file_id`: String (OpenAI file ID for API)
- `question_field_name`: String (which diagnostic question)

**Relationships:**
- `diagnostics`: Many-to-many with Diagnostic (via `diagnostic_media` table)

---

## 🔄 Complete Data Flow

### **Scenario: User Opens Engagement Details Page**

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Page Loads                                          │
└─────────────────────────────────────────────────────────────┘

Frontend: EngagementDetailPage.tsx
  ↓
useEffect() triggers fetchDiagnostics()
  ↓
API Call: GET /api/diagnostics/engagement/{engagementId}
  ↓
Backend: diagnostics.py → list_engagement_diagnostics()
  ↓
Service: diagnostic_service.py → get_engagement_diagnostics()
  ↓
Database: Query diagnostics table WHERE engagement_id = {id}
  ↓
Response: List of diagnostic summaries
  ↓
Frontend: Receives array of diagnostics


┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Fetch Full Details for Each Diagnostic             │
└─────────────────────────────────────────────────────────────┘

Frontend: For each diagnostic in list
  ↓
API Call: GET /api/diagnostics/{diagnostic_id}
  ↓
Backend: diagnostics.py → get_diagnostic()
  ↓
Service: diagnostic_service.py → get_diagnostic()
  ↓
Database: Query diagnostic with all relationships
  ↓
Response: Full diagnostic object with:
  - questions (survey structure)
  - user_responses (answers + file metadata)
  - scoring_data, ai_analysis, etc.
  ↓
Frontend: Stores in diagnostics state


┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Extract Files from Data                            │
└─────────────────────────────────────────────────────────────┘

Frontend: useMemo() hooks process diagnostics

A. Generated Files (Lines 113-136):
   - Loops through diagnostics
   - For each completed/processing diagnostic:
     - Creates file object for PDF report
     - Sets diagnosticId for download
   
B. Uploaded Files (Lines 139-217):
   - Loops through diagnostics
   - For each diagnostic:
     - Gets user_responses
     - Loops through all response fields
     - Finds file metadata objects
     - Extracts: file_name, file_size, relative_path, media_id
     - Creates file objects for display


┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Display Files                                       │
└─────────────────────────────────────────────────────────────┘

Frontend: Renders tabs
  ↓
Overview Tab:
  - GeneratedFilesList component (generatedFiles)
  - GeneratedFilesList component (uploadedFiles)
  ↓
User clicks file → handleDownload()
  ↓
API Call: GET /api/diagnostics/{diagnosticId}/download
  ↓
Backend: Generates PDF on-demand
  ↓
Response: PDF binary
  ↓
Frontend: Creates blob URL, triggers download
```

---

## 📁 Component Breakdown

### **Frontend Components**

#### **1. `EngagementDetailPage.tsx`** (Main Page)
- **Role:** Container component, orchestrates data fetching
- **State:** diagnostics, isLoadingFiles, activeTab
- **Key Functions:**
  - `fetchDiagnostics()`: Fetches all diagnostics
  - `generatedFiles`: Extracts PDF reports
  - `uploadedFiles`: Extracts uploaded files
  - `handleDownload()`: Downloads files

#### **2. `ToolSurvey.tsx`** (Diagnostic Tab)
- **Role:** Displays diagnostic survey/questions
- **What it does:**
  - Loads survey JSON structure
  - Displays questions page by page
  - Saves responses to backend
  - Submits diagnostic for processing
  - Polls for completion status

#### **3. `TasksList.tsx`** (Tasks Tab)
- **Role:** Displays tasks for engagement
- **What it does:**
  - Fetches tasks via Redux
  - Filters by engagement ID
  - Displays task cards
  - Handles create/edit/delete

#### **4. `EngagementChatbot.tsx`** (Chatbot Tab)
- **Role:** AI chatbot interface
- **What it does:**
  - Sends messages to `/api/ai/chat`
  - Displays conversation history
  - Handles AI responses

#### **5. `GeneratedFilesList.tsx`** (File Display)
- **Role:** Renders list of files
- **What it does:**
  - Maps file objects to `GeneratedFile` components
  - Shows empty state if no files
  - Handles download clicks

---

## 🔍 Key Data Structures

### **Diagnostic Object (from API)**
```json
{
  "id": "uuid",
  "engagement_id": "uuid",
  "status": "completed",
  "questions": { /* full survey structure */ },
  "user_responses": {
    "question_1": "answer",
    "docs_profit_loss_statements": [
      {
        "file_name": "balance_sheet.pdf",
        "media_id": "uuid",
        "file_size": 245000,
        "relative_path": "diagnostic/{id}/file.pdf"
      }
    ]
  },
  "scoring_data": { /* scores */ },
  "ai_analysis": { /* roadmap, report */ },
  "module_scores": { /* M1-M8 scores */ },
  "overall_score": 4.5
}
```

### **File Metadata (in user_responses)**
```json
{
  "file_name": "balance_sheet.pdf",
  "file_type": "application/pdf",
  "file_size": 245000,
  "relative_path": "diagnostic/{id}/file.pdf",
  "media_id": "uuid",
  "openai_file_id": "file-abc123"
}
```

---

## 🔐 Authentication Flow

**Every API call includes:**
```javascript
headers: {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
}
```

**Token:** Retrieved from `localStorage.getItem('auth_token')`

**Backend:** Validates token via `get_current_user` dependency

---

## 📊 Polling Mechanism

**When diagnostics are processing:**
1. Frontend detects `status === 'processing'`
2. Sets up interval: `setInterval(() => fetchDiagnostics(), 5000)`
3. Polls every 5 seconds
4. When status changes to `completed` or `failed`, stops polling
5. Shows notification when completed

---

## 🎯 Summary: What Each File Does

| File | Purpose | Key Responsibility |
|------|---------|-------------------|
| **EngagementDetailPage.tsx** | Main page | Fetches diagnostics, extracts files, manages tabs |
| **diagnostics.py** | API endpoints | Handles HTTP requests, validates, calls services |
| **diagnostic_service.py** | Business logic | Queries database, processes data, orchestrates AI |
| **Diagnostic model** | Database schema | Stores diagnostic data, relationships |
| **Media model** | Database schema | Stores file metadata, OpenAI IDs |
| **ToolSurvey.tsx** | Survey UI | Displays questions, saves responses, submits |
| **TasksList.tsx** | Tasks UI | Displays tasks for engagement |
| **GeneratedFilesList.tsx** | File display | Renders file list with download |

---

## 🔄 Complete Request Flow Example

**User opens Engagement Details page:**

1. **Frontend:** `EngagementDetailPage` mounts
2. **Frontend:** `useEffect` calls `fetchDiagnostics()`
3. **Frontend:** Makes API call `GET /api/diagnostics/engagement/{id}`
4. **Backend:** `list_engagement_diagnostics()` handler
5. **Backend:** Calls `service.get_engagement_diagnostics()`
6. **Database:** Returns diagnostics list
7. **Backend:** Returns JSON array to frontend
8. **Frontend:** For each diagnostic, calls `GET /api/diagnostics/{id}`
9. **Backend:** Returns full diagnostic with `user_responses`
10. **Frontend:** `useMemo` extracts files from `user_responses`
11. **Frontend:** Renders files in `GeneratedFilesList` components
12. **User:** Clicks download → `handleDownload()` → `GET /api/diagnostics/{id}/download`
13. **Backend:** Generates PDF → Returns binary
14. **Frontend:** Creates blob → Triggers browser download

---

This is the complete workflow from backend to frontend for the Engagement Details page!

