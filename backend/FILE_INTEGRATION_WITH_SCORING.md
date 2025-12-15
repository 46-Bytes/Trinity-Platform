# File Integration with AI Diagnostic Scoring

## Overview

This document explains how uploaded files (Balance Sheets, P&L statements, financial documents) are integrated into the AI diagnostic scoring pipeline using OpenAI's Responses API.

## How It Works

### 1. File Upload Process

When a user uploads files during a diagnostic:

```
User Upload → Local Storage → OpenAI Upload → Store File ID → Attach to Diagnostic
```

**Key Components:**
- **FileService** (`file_service.py`): Handles file storage and OpenAI uploads
- **Media Model** (`media.py`): Stores file metadata and OpenAI file IDs
- **Files API** (`files.py`): REST endpoints for file operations

**Upload Flow:**
1. User uploads file via `/api/files/upload` endpoint
2. File is stored locally in `user_files` directory
3. File is uploaded to OpenAI using `client.files.create()`
4. OpenAI returns a file ID (e.g., `file-abc123xyz`)
5. File ID is stored in `media.openai_file_id`
6. File is attached to diagnostic via `diagnostic_media` table

### 2. Scoring Pipeline Integration

When a diagnostic is submitted for scoring, the system:

**Step 1: Retrieve Attached Files**
```python
# In diagnostic_service.py
attached_files = list(diagnostic.media)
```

**Step 2: Extract OpenAI File IDs**
```python
file_ids = [
    file.openai_file_id 
    for file in attached_files 
    if file.openai_file_id  # Only include files uploaded to OpenAI
]
```

**Step 3: Build File Context (Text Description)**
```python
file_context = self._build_file_context(attached_files)
```

Example file context:
```
=== UPLOADED DOCUMENTS ===
The user has uploaded 3 document(s) for this diagnostic.
✅ 3 document(s) are attached to this request and available for you to read directly.

Documents uploaded:

1. Balance_Sheet_2023.pdf
   Type: pdf
   Question: balance_sheets_upload
   Status: ✅ Attached for analysis

2. PL_Statement_2023.pdf
   Type: pdf
   Question: profit_loss_upload
   Status: ✅ Attached for analysis

IMPORTANT INSTRUCTIONS:
- The attached documents are available for you to read.
- When scoring, analyze the actual data from these documents.
- For financial questions (M1), review P&L statements, balance sheets.
- Use document data to validate and enrich scores beyond just survey responses.
=== END UPLOADED DOCUMENTS ===
```

**Step 4: Pass Files to OpenAI**
```python
scoring_result = await openai_service.process_scoring(
    scoring_prompt=scoring_prompt,
    scoring_map=scoring_map,
    task_library=task_library,
    diagnostic_questions=diagnostic_questions,
    user_responses=user_responses,
    file_context=file_context,  # Text description
    file_ids=file_ids  # Actual file IDs
)
```

### 3. OpenAI Responses API Format

The system uses OpenAI's Responses API with file attachments:

**Without Files:**
```python
response = client.responses.create(
    model="gpt-4o",
    input=[
        {
            "role": "developer",
            "content": "System prompt with scoring instructions..."
        },
        {
            "role": "user",
            "content": "Diagnostic questions and user responses..."
        }
    ]
)
```

**With Files (New Implementation):**
```python
response = client.responses.create(
    model="gpt-4o",
    input=[
        {
            "role": "developer",
            "content": "System prompt with scoring instructions..."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "input_file",
                    "file_id": "file-abc123"  # Balance Sheet
                },
                {
                    "type": "input_file",
                    "file_id": "file-xyz789"  # P&L Statement
                },
                {
                    "type": "input_text",
                    "text": "Diagnostic questions and user responses..."
                }
            ]
        }
    ]
)
```

### 4. How GPT Reads Files

When file IDs are attached:

1. **GPT accesses file content directly** - It can read the full content of PDFs, spreadsheets, images
2. **Extracts data automatically** - GPT can extract financial data, tables, charts
3. **Analyzes in context** - Uses file data alongside survey responses
4. **Enriches scoring** - Validates user responses against actual document data

**Example:**

User Response:
```json
{
  "profit_or_loss_last_year": "Profit",
  "financial_performance_since_acquisition": "Better"
}
```

Attached File: `PL_Statement_2023.pdf`

GPT Analysis:
- Reads P&L document
- Confirms profit of $150,000
- Validates "Better" claim by comparing year-over-year
- Assigns accurate score based on actual data, not just user claim
- Provides detailed insights in advisor report

## Benefits of File Integration

### Before (Text Responses Only)

```
User: "My profit was $150,000 last year"
GPT: ✅ Score: 5 (based on user claim)
```

**Problem:** No validation, relies on user's memory/honesty

### After (With File Analysis)

```
User: "My profit was $150,000 last year"
Files: Balance_Sheet_2023.pdf, PL_Statement_2023.pdf
GPT: 
  - ✅ Reads P&L statement
  - ✅ Confirms net profit: $148,732
  - ✅ Reviews trends: +23% YoY growth
  - ✅ Validates cash flow positive
  - ✅ Score: 5 (validated from documents)
  - 📊 Additional insight: "Strong revenue growth driven by operational efficiency"
```

**Advantages:**
- ✅ Validates user responses
- ✅ Extracts additional insights
- ✅ Identifies discrepancies
- ✅ Provides data-driven recommendations
- ✅ More accurate scoring

## File Requirements

### Supported File Types

- **Documents:** PDF, DOC, DOCX, TXT
- **Spreadsheets:** CSV, XLSX, XLS
- **Images:** JPG, JPEG, PNG (for charts, screenshots)

### Recommended Files for Diagnostics

**Financial Clarity & Reporting (M1):**
- Balance Sheets (last 3-5 years)
- Profit & Loss Statements (last 3-5 years)
- Cash Flow Statements
- Management Reports

**Operations (M2-M8):**
- Process documentation
- Team structure charts
- Marketing materials
- Sales reports

## Handling Missing Files

The system gracefully handles cases where files are not uploaded:

```python
# If no files uploaded
file_ids = []  # Empty list
file_context = None  # No context

# OpenAI receives standard text-only request
# Scoring proceeds based on survey responses only
```

**No errors or failures** - the system simply skips file processing.

## Technical Implementation

### Key Functions

**1. File Upload (openai_service.py)**
```python
async def upload_file(self, file_path: str, purpose: str = "user_data") -> str:
    """Upload file to OpenAI and return file ID"""
    with open(file_path, "rb") as f:
        response = self.client.files.create(
            file=f,
            purpose=purpose
        )
    return response.id
```

**2. Message Conversion (openai_service.py)**
```python
def _convert_messages_to_input(
    self, 
    messages: List[Dict[str, str]],
    file_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Convert messages to Responses API format.
    Attaches files to the last user message.
    """
    # ... builds content array with files and text
```

**3. Scoring with Files (openai_service.py)**
```python
async def process_scoring(
    self,
    scoring_prompt: str,
    scoring_map: Dict[str, Any],
    task_library: Dict[str, Any],
    diagnostic_questions: Dict[str, Any],
    user_responses: Dict[str, Any],
    file_context: Optional[str] = None,
    file_ids: Optional[List[str]] = None,  # ← NEW
    reasoning_effort: str = "high"
) -> Dict[str, Any]:
    """Process scoring with file attachments"""
```

**4. File Context Builder (diagnostic_service.py)**
```python
def _build_file_context(self, files: list) -> Optional[str]:
    """
    Build descriptive text about attached files.
    Tells GPT what files are attached and how to use them.
    """
```

## Testing File Integration

### Test Scenario

1. **Create Diagnostic**
   ```bash
   POST /api/diagnostics/create
   {
     "engagement_id": "uuid-here"
   }
   ```

2. **Upload Files**
   ```bash
   POST /api/files/upload
   Content-Type: multipart/form-data
   
   Files:
   - balance_sheet_2023.pdf
   - pl_statement_2023.pdf
   ```

3. **Update Responses**
   ```bash
   PUT /api/diagnostics/{id}/responses
   {
     "responses": {
       "financial_performance_since_acquisition": "Better",
       "profit_or_loss_last_year": "Profit",
       ...
     }
   }
   ```

4. **Submit for Scoring**
   ```bash
   POST /api/diagnostics/{id}/submit
   ```

5. **Check Results**
   ```bash
   GET /api/diagnostics/{id}/results
   ```

### Expected Output

```json
{
  "diagnostic_id": "uuid",
  "status": "completed",
  "scored_rows": [
    {
      "question": "How has your financial performance been since acquisition?",
      "response": "Better",
      "score": 5,
      "module": "M1",
      "validation": "Confirmed by P&L analysis showing 23% YoY growth"
    }
  ],
  "roadmap": [...],
  "advisor_report": "Based on the uploaded financial statements...",
  "files_analyzed": 2
}
```

## Troubleshooting

### Files Not Being Used

**Symptom:** Scoring doesn't include file insights

**Check:**
1. File uploaded to OpenAI? Check `media.openai_file_id`
2. File attached to diagnostic? Check `diagnostic_media` table
3. Check logs for file count: `📤 X files uploaded to OpenAI`

### File Upload Errors

**Common Issues:**
- File size > 10MB → Increase limit or compress
- Invalid file type → Check allowed extensions
- OpenAI API error → Check API key and quota

### Files Not Attached

**Check:**
```python
# In diagnostic_service.py logs
print(f"📎 Found {len(attached_files)} attached files")
print(f"📤 {len(file_ids)} files uploaded to OpenAI")
```

If count is 0, files weren't attached to the diagnostic.

## Summary

The file integration system:

✅ **Uploads files to OpenAI** - Files stored securely and accessible to GPT  
✅ **Attaches to diagnostics** - Files linked to specific diagnostic sessions  
✅ **Passes to Responses API** - Uses correct format (`input_file` + `file_id`)  
✅ **Enriches AI analysis** - GPT reads actual document data  
✅ **Validates responses** - Cross-references user claims with documents  
✅ **Improves accuracy** - Data-driven scoring instead of subjective responses  
✅ **Graceful degradation** - Works with or without files  

This integration significantly improves diagnostic quality by grounding AI analysis in actual business data rather than just survey responses.

