### Generate Tasks

Create a JSON object with a 'tasks' key containing an array of tasks the business owner should action within the next 30 days. Provide just the JSON with no markdown.

---

## CRITICAL RULE: DATA-GROUNDED TASKS ONLY

**Every single task you generate MUST be directly traceable to a specific answer, issue, or gap identified in the Diagnostic Data (Q&A) or the Priority Roadmap.**

- **DO NOT** invent, assume, or fabricate tasks based on general business advice.
- **DO NOT** generate a task unless there is clear evidence in the supplied data that the issue exists for THIS specific business.
- If the diagnostic data shows the business is performing well in an area (Green RAG, high score), **DO NOT** create improvement tasks for that area.
- If a topic was not asked about or not answered in the diagnostic, **DO NOT** create tasks related to it.
- Quality over quantity: It is far better to generate 3-5 highly relevant tasks than 10 tasks where half are generic filler.

**For each task you generate, you must be able to point to the specific Q&A response(s) or roadmap module that justifies it.** Include a `"data_reference"` field that briefly states which diagnostic question(s) or module finding the task addresses.

---

## TASK GENERATION RULES

1. **Only create tasks for modules that scored Amber or Red** in the roadmap (score < 4.0). Green modules (score ≥ 4.0) should generally NOT have tasks unless the Q&A data reveals a very specific, actionable gap.
2. Focus on the **top 3-4 highest-priority modules** (lowest rank numbers) from the roadmap.
3. Generate **only as many tasks as the data supports** — typically 3-8 tasks. Do not pad with generic advice.
4. Each task must reference a specific finding from the diagnostic responses.
5. Prioritize tasks based on the module rankings (lower rank = higher priority).

## TASK FORMAT

Use the following template for EACH task:

```json
{
  "title": "",
  "description": "",
  "category": "(general|legal-licensing|financial|operations|human-resources|customers|competitive-forces|due-diligence|tax)",
  "priority": "(low, medium, high, critical)",
  "data_reference": "Brief reference to the specific Q&A response(s) or roadmap finding that justifies this task"
}
```

The description should be detailed with any necessary step-by-step instructions. Every step must be in a new line and must follow 1. 2. 3. Numbering.

**Return format: A JSON object with a 'tasks' key containing an array of task objects:**
```json
{
  "tasks": [
    {"title": "Task 1", "description": "...", "category": "...", "priority": "...", "data_reference": "..."},
    {"title": "Task 2", "description": "...", "category": "...", "priority": "...", "data_reference": "..."}
  ]
}
```

## WHAT TO EXCLUDE

- Generic best-practice tasks not specific to this business's data (e.g., "Review your business plan" when nothing in the data suggests a plan issue)
- Tasks for areas where the business scored Green/high and no specific gap was identified
- Tasks about topics that were not covered in the diagnostic responses
- Duplicate tasks that address the same underlying issue
- Overly broad tasks that could apply to any business regardless of diagnostic data

## CRITICAL: Text Formatting Requirements

**IMPORTANT: Use only standard ASCII characters and basic punctuation in all text content.**
- Use standard hyphens (-) not en-dashes (–) or em-dashes (—)
- Use standard quotation marks (") not curly quotes (" " ' ')
- Use standard apostrophes (') not curly apostrophes (' ')
- Use three periods (...) not ellipsis character (…)
- Use standard spaces only, no non-breaking spaces or zero-width characters
- Do NOT use any special Unicode symbols, emojis, or formatting characters
- Use only printable ASCII characters (letters, numbers, standard punctuation, spaces, newlines)
