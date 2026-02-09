# BBA (Benchmark Business Advisory) Tool - Complete Code Flow

This document explains the step-by-step flow of the BBA Diagnostic Report Builder, including files, functions, and example data at each stage.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (React)                                     │
│  FileUploadPOC.tsx → ContextCaptureQuestionnaire.tsx → DraftFindingsStep.tsx    │
│  → ExpandedFindingsStep.tsx → SnapshotTableStep.tsx → TwelveMonthPlanStep.tsx     │
│  → ReviewEditStep.tsx                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTP (fetch)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (FastAPI)                                    │
│  upload_poc.py (API endpoints) → bba_service.py → bba_conversation_engine.py      │
│  → openai_service.py → bba_report_export.py                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  PostgreSQL (bba table)  │  OpenAI API (Files + Chat)  │  Prompt Templates      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Application Startup

**File:** `backend/app/main.py`

1. **FastAPI app** is created
2. **Routers** are included: `upload_poc_router` at `/api/poc`
3. **On startup:** `OpenAIService.initialize_client()` creates the OpenAI client

**File:** `backend/app/services/openai_service.py`
- `initialize_client()` - Creates `AsyncOpenAI` with API key from settings

---

## Step 0: User Authentication

Before any BBA API call, the user must be authenticated.

**File:** `backend/app/utils/auth.py`
- `get_current_user()` - Dependency that validates JWT token and returns `User` object

**Example:** Every API endpoint uses `current_user: User = Depends(get_current_user)`

---

## Step 1: Create BBA Project

### 1.1 Frontend: User clicks "Start New Report"

**File:** `frontend/src/components/poc/FileUploadPOC.tsx`

```typescript
// When user adds files or starts, ensureProject() is called
const ensureProject = async (): Promise<string> => {
  if (projectId) return projectId;
  
  const response = await fetch(`${API_BASE_URL}/api/poc/create-project`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  });
  
  const result = await response.json();
  setProjectId(result.project_id);  // e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  return result.project_id;
};
```

### 1.2 Backend: Create Project API

**File:** `backend/app/api/upload_poc.py`

| Function | Line | Purpose |
|----------|------|---------|
| `create_bba_project()` | ~43 | POST `/api/poc/create-project` |

**Flow:**
1. `get_bba_service(db)` → Returns `BBAService` instance
2. `bba_service.create_bba(user_id, engagement_id)` → Creates BBA row in DB
3. Returns `{ success: true, project_id: "uuid", status: "uploaded" }`

**File:** `backend/app/services/bba_service.py`

| Function | Purpose |
|----------|---------|
| `create_bba()` | Creates `BBA` model with `status='uploaded'`, commits to DB |

**File:** `backend/app/models/bba.py`

| Column | Example Value |
|--------|---------------|
| id | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| created_by_user_id | `user-uuid` |
| status | `uploaded` |
| file_ids | `null` |
| file_mappings | `null` |
| client_name | `null` |
| ... | ... |

**Example Response:**
```json
{
  "success": true,
  "project_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "uploaded"
}
```

---

## Step 1: Upload Files

### 1.1 Frontend: User drops/selects files

**File:** `frontend/src/components/poc/FileUploadPOC.tsx`

```typescript
// User selects files → addFiles() validates → handleUpload() sends
const handleUpload = async () => {
  const formData = new FormData();
  pendingFiles.forEach((fileObj) => formData.append('files', fileObj.file));
  
  const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
};
```

### 1.2 Backend: Upload API

**File:** `backend/app/api/upload_poc.py`

| Function | Line | Purpose |
|----------|------|---------|
| `upload_files_poc()` | ~68 | POST `/api/poc/{project_id}/upload` |

**Flow:**
1. Verify BBA exists and belongs to user
2. For each file:
   - Save to temp file
   - Call `openai_service.upload_file(file_path, purpose="assistants")`
   - Get `file_id` from OpenAI (e.g., `file-abc123xyz`)
3. Call `bba_service.update_files(project_id, file_ids, file_mappings)`

**File:** `backend/app/services/openai_service.py`

| Function | Purpose |
|----------|---------|
| `upload_file()` | Uploads file to OpenAI Files API, returns `{ id: "file-xxx", bytes, purpose }` |

**File:** `backend/app/services/bba_service.py`

| Function | Purpose |
|----------|---------|
| `update_files()` | Updates BBA with `file_ids`, `file_mappings`, `status='uploaded'` |

**Example BBA after upload:**
```json
{
  "file_ids": ["file-abc123", "file-xyz789"],
  "file_mappings": {
    "Balance_Sheet_2024.pdf": "file-abc123",
    "P&L_Statement.pdf": "file-xyz789"
  },
  "status": "uploaded"
}
```

---

## Step 2: Context Capture (Questionnaire)

### 2.1 Frontend: User fills questionnaire

**File:** `frontend/src/components/poc/ContextCaptureQuestionnaire.tsx`

```typescript
// User fills form: clientName, industry, companySize, locations, etc.
// On submit:
const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/submit-questionnaire`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  body: JSON.stringify({
    client_name: "Acme Ltd",
    industry: "Manufacturing",
    company_size: "medium",
    locations: "UK, Midlands",
    strategic_priorities: "Cost reduction, digital transformation",
    exclude_sale_readiness: false,
    // ...
  }),
});
```

### 2.2 Backend: Submit Questionnaire API

**File:** `backend/app/api/upload_poc.py`

| Function | Line | Purpose |
|----------|------|---------|
| `submit_questionnaire()` | ~207 | POST `/api/poc/{project_id}/submit-questionnaire` |

**File:** `backend/app/services/bba_service.py`

| Function | Purpose |
|----------|---------|
| `update_questionnaire()` | Updates BBA with client_name, industry, etc., sets `status='questionnaire_completed'` |

**Example BBA after questionnaire:**
```json
{
  "client_name": "Acme Ltd",
  "industry": "Manufacturing",
  "company_size": "medium",
  "locations": "UK, Midlands",
  "strategic_priorities": "Cost reduction, digital transformation",
  "exclude_sale_readiness": false,
  "status": "questionnaire_completed"
}
```

---

## Step 3: Draft Findings (AI Analysis)

### 3.1 Frontend: User clicks "Generate Draft Findings"

**File:** `frontend/src/components/poc/DraftFindingsStep.tsx`

```typescript
const handleGenerate = async () => {
  const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step3/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ custom_instructions: null }),
  });
  
  const result = await response.json();
  setFindings(result.findings?.findings || result.findings);
};
```

### 3.2 Backend: Generate Draft Findings API

**File:** `backend/app/api/upload_poc.py`

| Function | Line | Purpose |
|----------|------|---------|
| `generate_draft_findings()` | ~325 | POST `/api/poc/{project_id}/step3/generate` |

**Flow:**
1. Load BBA from DB (must have `file_ids` and `client_name`)
2. `engine = get_bba_conversation_engine()`
3. `result = await engine.generate_draft_findings(bba, custom_instructions)`
4. `bba_service.update_draft_findings(project_id, result.findings, tokens_used, model)`
5. Return findings to frontend

### 3.3 Conversation Engine: Generate Draft Findings

**File:** `backend/app/services/bba_conversation_engine.py`

| Function | Purpose |
|----------|---------|
| `generate_draft_findings()` | Orchestrates Step 3 AI call |
| `_build_context_from_bba()` | Extracts client context, file_ids, file_mappings |
| `load_bba_prompt()` | Loads prompt from `backend/files/prompts/bba/` |

**Flow:**
1. `context = _build_context_from_bba(bba)` → e.g. `{ client_name: "Acme Ltd", file_ids: ["file-abc123"], ... }`
2. Load `bba_system_prompt.md` + `step3_draft_findings.md`
3. Build messages:
   - **System:** Full BBA system prompt + Step 3 instructions
   - **User:** Client context + file mappings + "Analyse files and generate Top 10 findings"
4. Call `openai_service.generate_json_completion(messages, file_ids=bba.file_ids)`
5. Return `{ findings: parsed_content, tokens_used, model }`

**File:** `backend/app/services/openai_service.py`

| Function | Purpose |
|----------|---------|
| `generate_json_completion()` | Calls `generate_completion()` with `json_mode=True` |
| `generate_completion()` | Converts messages, attaches files to last user message, calls `client.responses.create()` |
| `_convert_messages_to_input()` | Adds `{ type: "input_file", file_id }` to content for file_ids |

**OpenAI API Call (conceptual):**
```python
# Messages sent to OpenAI:
[
  { "role": "system", "content": "<bba_system_prompt + step3_draft_findings>" },
  { "role": "user", "content": "<client context + file mappings>", "file_ids": ["file-abc123", "file-xyz789"] }
]
# OpenAI analyses the PDF files and returns JSON
```

**Example AI Response (parsed_content):**
```json
{
  "findings": [
    {
      "rank": 1,
      "title": "Management accounts lack timeliness",
      "summary": "Monthly management accounts are delayed by 3-4 weeks, limiting decision-making.",
      "priority_area": "Financial Reporting",
      "impact": "high",
      "urgency": "immediate"
    },
    { "rank": 2, "title": "...", ... }
  ],
  "analysis_notes": "Analysed Balance Sheet and P&L. Focus on cash flow and reporting.",
  "files_analysed": ["Balance_Sheet_2024.pdf", "P&L_Statement.pdf"]
}
```

**File:** `backend/app/services/bba_service.py`

| Function | Purpose |
|----------|---------|
| `update_draft_findings()` | Saves `draft_findings` to BBA, sets `status='draft_findings'` |

### 3.4 Confirm Draft Findings (optional edits)

**Frontend:** User can reorder, edit, then click "Confirm & Continue"

**API:** `POST /api/poc/{project_id}/step3/confirm`  
**Body:** `{ findings: [edited findings array] }`  
**Service:** `bba_service.confirm_draft_findings(project_id, edited_findings)`

---

## Step 4: Expand Findings

### 4.1 Frontend: User clicks "Expand Findings"

**File:** `frontend/src/components/poc/ExpandedFindingsStep.tsx`

```typescript
const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step4/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
});
```

### 4.2 Backend Flow

**API:** `generate_expand_findings()` in `upload_poc.py`  
**Engine:** `engine.expand_findings(bba)` in `bba_conversation_engine.py`

**Flow:**
1. Load `step4_expand_findings.md` prompt
2. Get `draft_findings` from BBA (or provided list)
3. Build user message: client context + draft findings JSON
4. Call `generate_json_completion(messages, file_ids=optional)` — files optional for context
5. Parse response → `expanded_findings`
6. `bba_service.update_expanded_findings(project_id, expanded_findings)`

**Example AI Response:**
```json
{
  "expanded_findings": [
    {
      "rank": 1,
      "title": "Management accounts lack timeliness",
      "priority_area": "Financial Reporting",
      "paragraphs": [
        "The current management accounting process at Acme Ltd results in monthly accounts being available 3-4 weeks after month-end. This delay significantly impacts the ability of leadership to make timely operational and strategic decisions.",
        "The business impact includes missed opportunities for cost intervention, delayed budget variance analysis, and reduced agility in responding to market changes.",
        "Addressing this will be critical for the planned digital transformation and cost reduction priorities."
      ],
      "key_points": ["3-4 week delay", "Impacts decision-making", "Blocks digital transformation"]
    }
  ]
}
```

---

## Step 5: Snapshot Table

### 5.1 Frontend: User clicks "Generate Snapshot Table"

**File:** `frontend/src/components/poc/SnapshotTableStep.tsx`

```typescript
const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step5/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
});
```

### 5.2 Backend Flow

**API:** `generate_snapshot_table()` in `upload_poc.py`  
**Engine:** `engine.generate_snapshot_table(bba)` in `bba_conversation_engine.py`

**Flow:**
1. Load `step5_snapshot_table.md`
2. Get `expanded_findings` from BBA
3. Build user message with expanded findings
4. Call `generate_json_completion(messages)` — no files
5. `bba_service.update_snapshot_table(project_id, snapshot_table)`

**Example AI Response:**
```json
{
  "snapshot_table": {
    "title": "Key Findings & Recommendations Snapshot",
    "rows": [
      {
        "rank": 1,
        "priority_area": "Financial Reporting",
        "key_finding": "Management accounts delayed by 3-4 weeks.",
        "recommendation": "Implement monthly close process with KPI dashboards."
      }
    ]
  }
}
```

---

## Step 6: 12-Month Plan

### 6.1 Frontend: User clicks "Generate 12-Month Plan"

**File:** `frontend/src/components/poc/TwelveMonthPlanStep.tsx`

```typescript
const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step6/generate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
});
```

### 6.2 Backend Flow

**API:** `generate_12month_plan()` in `upload_poc.py`  
**Engine:** `engine.generate_12month_plan(bba)` in `bba_conversation_engine.py`

**Flow:**
1. Load `step6_12month_plan.md`
2. Get `expanded_findings`, `snapshot_table` from BBA
3. Build user message
4. Call `generate_json_completion(messages, file_ids=optional)`
5. Extract `plan_notes` and `recommendations` from response
6. `bba_service.update_twelve_month_plan(project_id, plan_data, plan_notes)`

**Example AI Response:**
```json
{
  "plan_notes": "The timeframes outlined in this plan are indicative only...",
  "recommendations": [
    {
      "number": 1,
      "title": "Implement Monthly Management Reporting",
      "timing": "Month 1-3",
      "purpose": "Establish timely financial visibility for decision-making.",
      "key_objectives": ["Close within 5 working days", "KPI dashboard", "..."],
      "actions": ["Define close checklist", "Assign responsibilities", "..."],
      "bba_support": "BBA will provide finance mentoring and co-author the reporting framework.",
      "expected_outcomes": ["Timely decisions", "Reduced variance", "..."]
    }
  ],
  "timeline_summary": { "rows": [...] }
}
```

---

## Step 7: Review & Edit

### 7.1 Frontend: ReviewEditStep loads project

**File:** `frontend/src/components/poc/ReviewEditStep.tsx`

```typescript
// On mount: load full project
const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}`);
const result = await response.json();
setProject(result.project);
```

**API:** `GET /api/poc/{project_id}` → Returns full BBA with all steps' data

### 7.2 Generate Executive Summary (optional)

```typescript
const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/executive-summary/generate`, {
  method: 'POST',
});
```

**Engine:** `engine.generate_executive_summary(bba)` — Uses expanded findings + plan to write 2-4 paragraphs

### 7.3 Apply Edits (optional)

**API:** `PATCH /api/poc/{project_id}/review/edit`  
**Body:** `{ edit_type: "rerank", section: "findings", changes: {...}, instructions: "..." }`  
**Engine:** `engine.apply_edits(bba, edits)` — AI applies requested changes  
**Service:** `bba_service.apply_edits(project_id, updated_sections)`

---

## Export: Word Document

### Frontend: User clicks "Export to Word"

**File:** `frontend/src/components/poc/ReviewEditStep.tsx`

```typescript
const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/export/docx`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
});

const blob = await response.blob();
// Create download link
const a = document.createElement('a');
a.href = URL.createObjectURL(blob);
a.download = `BBA_Diagnostic_Report_${clientName}.docx`;
a.click();
```

### Backend: Export API

**File:** `backend/app/api/upload_poc.py`

| Function | Purpose |
|----------|---------|
| `export_to_word()` | POST `/api/poc/{project_id}/export/docx` |

**Flow:**
1. Load BBA from DB
2. `exporter = BBAReportExporter()` from `bba_report_export.py`
3. `doc_bytes = exporter.generate_report(bba)`
4. `bba_service.update_final_report(project_id, final_report)` — Save compiled report
5. Return `StreamingResponse(doc_bytes, media_type="application/vnd...docx")`

**File:** `backend/app/services/bba_report_export.py`

| Function | Purpose |
|----------|---------|
| `generate_report()` | Creates Word document from BBA data |
| `_add_title_page()` | Title, client name, date |
| `_add_executive_summary()` | Executive summary section |
| `_add_snapshot_table()` | 3-column table |
| `_add_key_findings()` | Expanded findings with paragraphs |
| `_add_recommendations_plan()` | 12-month plan with Purpose, Objectives, Actions, BBA Support, Outcomes |
| `_add_footer()` | Confidential footer |

Uses **python-docx** (`from docx import Document`) to build the .docx file.

---

## File Reference Summary

| File | Key Functions |
|------|---------------|
| `backend/app/main.py` | App setup, router inclusion, startup |
| `backend/app/api/upload_poc.py` | All BBA API endpoints |
| `backend/app/services/bba_service.py` | CRUD + step-specific updates for BBA |
| `backend/app/services/bba_conversation_engine.py` | AI orchestration for Steps 3-7 |
| `backend/app/services/openai_service.py` | `upload_file`, `generate_completion`, `generate_json_completion` |
| `backend/app/services/bba_report_export.py` | Word document generation |
| `backend/app/models/bba.py` | BBA SQLAlchemy model |
| `backend/app/schemas/bba.py` | Pydantic schemas |
| `backend/files/prompts/bba/*.md` | Prompt templates |
| `frontend/.../FileUploadPOC.tsx` | Steps 1-2 UI |
| `frontend/.../DraftFindingsStep.tsx` | Step 3 UI |
| `frontend/.../ExpandedFindingsStep.tsx` | Step 4 UI |
| `frontend/.../SnapshotTableStep.tsx` | Step 5 UI |
| `frontend/.../TwelveMonthPlanStep.tsx` | Step 6 UI |
| `frontend/.../ReviewEditStep.tsx` | Step 7 UI + Export |

---

## Data Flow Diagram (Step 3 Example)

```
User clicks "Generate Draft Findings"
         │
         ▼
DraftFindingsStep.tsx: handleGenerate()
         │
         │  POST /api/poc/{id}/step3/generate
         ▼
upload_poc.py: generate_draft_findings()
         │
         ├─► bba_service.get_bba(project_id)     → Load BBA from DB
         │
         ├─► get_bba_conversation_engine()
         │
         ▼
bba_conversation_engine.py: generate_draft_findings(bba)
         │
         ├─► _build_context_from_bba(bba)       → { client_name, file_ids, ... }
         ├─► load_bba_prompt("bba_system_prompt")
         ├─► load_bba_prompt("step3_draft_findings")
         ├─► Build messages [system, user]
         │
         ▼
openai_service.py: generate_json_completion(messages, file_ids)
         │
         ├─► _convert_messages_to_input()       → Attach file_ids to user message
         ├─► client.responses.create(...)        → OpenAI API call
         ├─► Parse JSON from response
         │
         ▼
Return { findings, tokens_used, model }
         │
         ▼
bba_service.update_draft_findings(project_id, findings)
         │
         ▼
Return { success, findings, project } to frontend
         │
         ▼
DraftFindingsStep.tsx: setFindings(result.findings)
         │
         ▼
User sees ranked findings, can edit/confirm
```

---

## Example: Complete BBA Record After All Steps

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "file_ids": ["file-abc123", "file-xyz789"],
  "file_mappings": { "Balance_Sheet_2024.pdf": "file-abc123", "P&L_Statement.pdf": "file-xyz789" },
  "client_name": "Acme Ltd",
  "industry": "Manufacturing",
  "company_size": "medium",
  "strategic_priorities": "Cost reduction, digital transformation",
  "draft_findings": { "findings": [ {...}, {...} ] },
  "expanded_findings": { "expanded_findings": [ {...} ] },
  "snapshot_table": { "title": "...", "rows": [ {...} ] },
  "twelve_month_plan": { "plan_notes": "...", "recommendations": [ {...} ] },
  "executive_summary": "Acme Ltd is a Midlands-based manufacturer...",
  "final_report": { "exported_at": "2026-01-29T..." },
  "report_version": 1,
  "ai_tokens_used": 45000
}
```
