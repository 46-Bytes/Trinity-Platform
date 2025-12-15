# File Scoring Example - Complete Data Flow

## Real-World Example: Financial Diagnostic with Uploaded Documents

### Scenario

A business owner completes a diagnostic and uploads their financial documents.

---

## Step 1: User Uploads Files

**Files uploaded:**
- `Balance_Sheet_2023.pdf`
- `PL_Statement_2022.pdf`
- `PL_Statement_2023.pdf`

**API Request:**
```bash
POST /api/files/upload
Content-Type: multipart/form-data

diagnostic_id: 550e8400-e29b-41d4-a716-446655440000
files: [balance_sheet_2023.pdf, pl_statement_2022.pdf, pl_statement_2023.pdf]
```

**Backend Process:**
1. Files saved locally: `/user_files/{user_id}/balance_sheet_2023.pdf`
2. Files uploaded to OpenAI:
   ```python
   file1 = client.files.create(
       file=open("balance_sheet_2023.pdf", "rb"),
       purpose="user_data"
   )
   # Returns: file-abc123xyz
   ```
3. File IDs stored in database:
   ```sql
   INSERT INTO media (user_id, file_name, openai_file_id, ...)
   VALUES (1, 'Balance_Sheet_2023.pdf', 'file-abc123xyz', ...)
   ```
4. Files linked to diagnostic:
   ```sql
   INSERT INTO diagnostic_media (diagnostic_id, media_id)
   VALUES ('550e8400-...', 1)
   ```

---

## Step 2: User Completes Survey

**Survey Responses:**
```json
{
  "financial_performance_since_acquisition": "Better",
  "do_you_have_any_debts_in_the_business": "No",
  "key_reports_review_frequency": "Weekly",
  "profit_or_loss_last_year": "Profit",
  "accountant_meeting_freq": "monthly",
  "estimated_annual_revenue": "$500k - $1M",
  "estimated_profit_margin": "10-20%"
}
```

---

## Step 3: User Submits Diagnostic

**API Request:**
```bash
POST /api/diagnostics/550e8400-e29b-41d4-a716-446655440000/submit
```

---

## Step 4: Backend Processing

### 4.1: Retrieve Files

```python
# diagnostic_service.py - Line 232
attached_files = list(diagnostic.media)
# Returns: [
#   Media(file_name="Balance_Sheet_2023.pdf", openai_file_id="file-abc123xyz"),
#   Media(file_name="PL_Statement_2022.pdf", openai_file_id="file-def456uvw"),
#   Media(file_name="PL_Statement_2023.pdf", openai_file_id="file-ghi789rst")
# ]
```

### 4.2: Extract File IDs

```python
# diagnostic_service.py - Line 234
file_ids = [
    file.openai_file_id 
    for file in attached_files 
    if file.openai_file_id
]
# Returns: ["file-abc123xyz", "file-def456uvw", "file-ghi789rst"]
```

### 4.3: Build File Context

```python
# diagnostic_service.py - Line 233
file_context = self._build_file_context(attached_files)
```

**Output:**
```
=== UPLOADED DOCUMENTS ===
The user has uploaded 3 document(s) for this diagnostic.
✅ 3 document(s) are attached to this request and available for you to read directly.

Documents uploaded:

1. Balance_Sheet_2023.pdf
   Type: pdf
   Question: balance_sheets_upload
   Status: ✅ Attached for analysis

2. PL_Statement_2022.pdf
   Type: pdf
   Question: profit_loss_upload
   Status: ✅ Attached for analysis

3. PL_Statement_2023.pdf
   Type: pdf
   Question: profit_loss_upload
   Status: ✅ Attached for analysis

IMPORTANT INSTRUCTIONS:
- The attached documents (financial statements, reports, etc.) are available for you to read.
- When scoring, analyze the actual data from these documents.
- For financial questions (M1), review P&L statements, balance sheets, and financial reports.
- Use document data to validate and enrich scores beyond just survey responses.
- Extract key metrics, trends, and insights from the documents.
=== END UPLOADED DOCUMENTS ===
```

---

## Step 5: Send to OpenAI

### 5.1: Build Messages

```python
# openai_service.py - process_scoring()
messages = [
    {
        "role": "system",
        "content": (
            "You are Trinity, an expert business advisor...\n\n"
            "Scoring Map: {...}\n\n"
            "Task Library: {...}\n\n"
            "=== UPLOADED DOCUMENTS ===\n"
            "The user has uploaded 3 document(s)...\n"
            "..."
        )
    },
    {
        "role": "user",
        "content": (
            "Diagnostic: {...}\n\n"
            "User Responses: {...}\n\n"
            "Generate a complete JSON response..."
        )
    }
]
```

### 5.2: Convert to Responses API Format

```python
# openai_service.py - _convert_messages_to_input()
input_messages = [
    {
        "role": "developer",  # Converted from 'system'
        "content": "You are Trinity, an expert business advisor..."
    },
    {
        "role": "user",
        "content": [
            # Files attached FIRST
            {
                "type": "input_file",
                "file_id": "file-abc123xyz"  # Balance Sheet 2023
            },
            {
                "type": "input_file",
                "file_id": "file-def456uvw"  # P&L 2022
            },
            {
                "type": "input_file",
                "file_id": "file-ghi789rst"  # P&L 2023
            },
            # Then text content
            {
                "type": "input_text",
                "text": "Diagnostic: {...}\n\nUser Responses: {...}"
            }
        ]
    }
]
```

### 5.3: Make API Call

```python
# openai_service.py - generate_completion()
response = self.client.responses.create(
    model="gpt-4o",
    input=input_messages,
    temperature=1.0,
    text={"format": {"type": "json_object"}},
    reasoning={"effort": "high"}
)
```

**What OpenAI Receives:**
```
Model: gpt-4o
Temperature: 1.0
Reasoning: high

Input Messages:
  [0] Developer Message: "You are Trinity... [scoring instructions]"
  [1] User Message:
      Files:
        - file-abc123xyz (Balance_Sheet_2023.pdf)
        - file-def456uvw (PL_Statement_2022.pdf)
        - file-ghi789rst (PL_Statement_2023.pdf)
      Text: "Diagnostic: {...} User Responses: {...}"
```

---

## Step 6: GPT Processing

### What GPT Does:

1. **Reads the files:**
   - Opens `Balance_Sheet_2023.pdf`
   - Extracts: Assets $850K, Liabilities $200K, Equity $650K
   - Opens `PL_Statement_2022.pdf`
   - Extracts: Revenue $650K, Net Profit $85K (13.1%)
   - Opens `PL_Statement_2023.pdf`
   - Extracts: Revenue $800K, Net Profit $120K (15%)

2. **Compares with user responses:**
   - User says: "Profit", "Better", "$500k-$1M", "10-20%"
   - Documents confirm: ✅ Profit (15%), ✅ Better (+23% revenue), ✅ ~$800K revenue, ✅ 15% margin

3. **Analyzes trends:**
   - Revenue growth: +23% YoY
   - Profit growth: +41% YoY
   - Margin improvement: 13.1% → 15%
   - Debt-free (confirmed by balance sheet)

4. **Scores questions:**

```json
{
  "scored_rows": [
    {
      "question": "How has your financial performance been since acquisition?",
      "response": "Better",
      "score": 5,
      "module": "M1",
      "ai_analysis": "Confirmed by financial statements. Revenue increased 23% YoY ($650K to $800K) and profit margin improved from 13.1% to 15%. Strong financial performance."
    },
    {
      "question": "What was your profit or loss last year?",
      "response": "Profit",
      "score": 5,
      "module": "M1",
      "ai_analysis": "P&L Statement 2023 shows net profit of $120,000 (15% margin). Significant improvement from prior year."
    },
    {
      "question": "Do you have any debts in the business?",
      "response": "No",
      "score": 5,
      "module": "M1",
      "ai_analysis": "Balance sheet confirms zero debt. Total liabilities $200K are current liabilities (accounts payable). No long-term debt. Excellent financial position."
    }
  ]
}
```

5. **Generates roadmap with document insights:**

```json
{
  "roadmap": [
    {
      "module": "M1",
      "name": "Financial Clarity & Reporting",
      "score": 5.0,
      "rag": "Green",
      "rank": 8,
      "whyPriority": "Strong financial performance with 23% revenue growth and 15% profit margin. Documents show consistent profitability, zero debt, and improving margins. Current financial management practices are excellent.",
      "quickWins": "Continue maintaining current financial reporting standards. Consider implementing quarterly board reporting to showcase strong performance to stakeholders.",
      "documentInsights": "Based on uploaded P&L and Balance Sheet: Revenue $800K (+23% YoY), Net Profit $120K (15% margin, up from 13.1%), Zero debt, Strong cash position."
    }
  ]
}
```

6. **Creates advisor report:**

```html
<h1>Advisor Report</h1>

<h2>Executive Summary</h2>
<p>Based on the diagnostic responses and review of your financial statements (Balance Sheet 2023, P&L Statements 2022-2023), your business demonstrates strong financial health and growth.</p>

<h3>Key Findings from Financial Documents:</h3>
<ul>
  <li>Revenue: $800,000 (2023) vs $650,000 (2022) - 23% growth</li>
  <li>Net Profit: $120,000 (15% margin) vs $85,000 (13.1% margin) - 41% growth</li>
  <li>Debt-Free: Zero long-term debt confirmed by balance sheet</li>
  <li>Strong Equity: $650,000 in owner equity</li>
  <li>Healthy Working Capital: Current assets exceed current liabilities</li>
</ul>

<h2>Module Analysis</h2>

<h3>M1: Financial Clarity & Reporting (Score: 5.0 - Green)</h3>
<p><strong>Document Analysis:</strong> Your uploaded financial statements demonstrate professional accounting practices with clear P&L statements and a well-structured balance sheet. The financial data shows consistent profitability with improving margins year-over-year.</p>

<p><strong>Strengths:</strong></p>
<ul>
  <li>Strong revenue growth trajectory (23% YoY)</li>
  <li>Improving profitability (margin expansion from 13.1% to 15%)</li>
  <li>Zero debt provides financial flexibility</li>
  <li>Weekly review of key reports shows good financial discipline</li>
</ul>

<p><strong>Recommendations:</strong> Maintain current practices. Consider implementing KPI dashboards to track these strong metrics in real-time.</p>

...
</html>
```

---

## Step 7: Response Returned

**OpenAI Response:**
```json
{
  "output_text": "{\"scored_rows\": [...], \"roadmap\": [...], \"advisorReport\": \"...\"}",
  "usage": {
    "prompt_tokens": 125000,  // Large due to file content
    "completion_tokens": 8500,
    "total_tokens": 133500
  },
  "finish_reason": "completed"
}
```

---

## Step 8: Saved to Database

```python
# diagnostic_service.py - Lines 298-337
diagnostic.json_extract = json_extract
diagnostic.summary = summary
diagnostic.json_scoring = scoring_data
diagnostic.advice = advice
diagnostic.overall_score = overall_score
diagnostic.status = "completed"
diagnostic.processed_at = datetime.utcnow()

db.commit()
```

---

## Key Differences: With vs Without Files

### Without Files (Survey Only)

**GPT sees:**
```
User Response: "financial_performance_since_acquisition": "Better"
```

**GPT scores:**
```json
{
  "score": 5,
  "ai_analysis": "User reports better financial performance since acquisition."
}
```

**Issues:**
- ❌ No validation
- ❌ Relies on user's memory
- ❌ No quantification
- ❌ No trend analysis

---

### With Files (Survey + Documents)

**GPT sees:**
```
User Response: "financial_performance_since_acquisition": "Better"
Files: 
  - Balance_Sheet_2023.pdf
  - PL_Statement_2022.pdf
  - PL_Statement_2023.pdf

[GPT reads files and extracts:]
- 2022 Revenue: $650,000
- 2023 Revenue: $800,000
- Growth: +23%
- 2022 Profit: $85,000 (13.1%)
- 2023 Profit: $120,000 (15%)
```

**GPT scores:**
```json
{
  "score": 5,
  "ai_analysis": "Confirmed by financial statements. Revenue increased 23% YoY ($650K to $800K) and profit margin improved from 13.1% to 15%. Strong financial performance validated by actual P&L data showing consistent growth and margin expansion. Balance sheet shows debt-free operation with strong equity position."
}
```

**Advantages:**
- ✅ Validated with real data
- ✅ Quantified metrics
- ✅ Trend analysis
- ✅ Additional insights
- ✅ Evidence-based scoring

---

## Technical Summary

### Data Flow

```
1. Files Upload
   ↓
2. Store Locally (/user_files/)
   ↓
3. Upload to OpenAI (get file IDs)
   ↓
4. Link to Diagnostic (diagnostic_media)
   ↓
5. Diagnostic Submission
   ↓
6. Retrieve Files (diagnostic.media)
   ↓
7. Extract File IDs (openai_file_id)
   ↓
8. Build File Context (text description)
   ↓
9. Convert Messages (attach files to input)
   ↓
10. Send to OpenAI Responses API
    ↓
11. GPT Reads Files + Analyzes
    ↓
12. Return Enriched Scoring
    ↓
13. Save to Database
```

### API Format (Responses API)

```python
# Correct format with files
input=[
    {
        "role": "developer",
        "content": "System prompt..."
    },
    {
        "role": "user",
        "content": [
            {"type": "input_file", "file_id": "file-abc123"},
            {"type": "input_file", "file_id": "file-def456"},
            {"type": "input_text", "text": "User message..."}
        ]
    }
]
```

### Result

✅ Files are properly attached using `input_file` format  
✅ GPT can read and analyze document content  
✅ Scoring is enriched with actual business data  
✅ Advisor reports include document-based insights  
✅ Validation of user responses against real documents  

This implementation transforms the diagnostic from subjective survey to **data-driven business analysis**.

