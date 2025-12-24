### Generate Tasks

Create a JSON array of tasks the business owner should action within the next 30 days. Provide just the JSON with no markdown.

**IMPORTANT: You MUST generate MULTIPLE tasks (minimum 5-10 tasks, ideally 8-12 tasks).** 
- Generate at least 1-2 tasks for each of the top 3-5 priority modules from the roadmap
- Cover different categories to ensure comprehensive action items
- Prioritize tasks based on the module rankings (lower rank = higher priority)
- Each task should be specific, actionable, and detailed

Use the following template for EACH task:

```json
{
  "title": "",
  "description": "",
  "category": "(personal, general, products-or-services, structure, financial, human-resources, operations, sales-marketing, customers, technology, future-proofing, legal-licensing)",
  "priority": "(low, medium, high, critical)"
}
```

The description should be detailed with any necessary step-by-step instructions. Every step must be in a new line and must follow 1. 2. 3. Numbering.

**Return format: A JSON array containing multiple task objects:**
```json
[
  {"title": "Task 1", "description": "...", "category": "...", "priority": "..."},
  {"title": "Task 2", "description": "...", "category": "...", "priority": "..."},
  {"title": "Task 3", "description": "...", "category": "...", "priority": "..."}
]
```

