# Phase 2 – Task List Generator (Excel-based Engagement Planner)

## Your Task

Generate a focused, practical advisor task list for each recommendation in the
12-month plan. The tasks will be exported to an Excel engagement planner used by
BBA advisors and the client.

**Quality over quantity.** Every task must be specific, actionable, and directly
tied to a recommendation from the diagnostic report. Do not pad with generic
filler tasks. If a recommendation needs only two tasks, generate two — not six.

---

## Task Row Format

Each task is a single row with these columns:

| Column | Description |
|---|---|
| `rec_number` | Recommendation number (1–10) |
| `recommendation` | Recommendation title (from the 12-month plan) |
| `owner` | `"Client"` or `"BBA"` |
| `task` | One clear, actionable task per row |
| `advisorHrs` | Estimated BBA advisor hours (0 for Client-owned tasks) |
| `advisor` | Assigned advisor name (null for Client-owned tasks) |
| `status` | Always `"Not yet started"` |
| `notes` | Always `""` (blank — reserved for human input) |
| `timing` | Real calendar month label (provided in context below) |

---

## Task Generation Rules

### For each recommendation, generate:

1. **One Client-owned summary task** — a concise statement of what the client
   must own and deliver for this recommendation. Set `advisorHrs` to 0 and
   `advisor` to null.

2. **One to three BBA-owned tasks** — specific advisory activities that BBA will
   perform to support the recommendation. These should be drawn from the
   recommendation's actions and BBA support outline, but distilled into the most
   impactful activities. Do not simply copy every action verbatim.

### BBA Hour Allocation

You will be given the total BBA hours available for each recommendation in the
context below (calculated as `monthly_capacity × months_span / 12`). Distribute
these hours across the BBA tasks for that recommendation proportionally based on
effort.

### Advisor Assignment

- Assign the **lead advisor** to the primary BBA tasks.
- Assign the **support advisor** (if provided) to secondary or supporting tasks.
- If only one advisor is available, assign all BBA tasks to them.

### Timing

Use the real calendar timing label provided for each recommendation (e.g.
"Feb–Apr 2026"). Do not use relative month references like "Month 1–3".

---

## Critical Rules

- **DO NOT** generate more than 4 tasks per recommendation (1 Client + up to 3 BBA).
- **DO NOT** create vague or generic tasks like "Support client with implementation".
  Every task must describe a specific deliverable or activity.
- **DO NOT** invent tasks unrelated to the recommendation's purpose, actions, or
  objectives.
- **DO NOT** duplicate tasks across recommendations.
- **DO** use British English spelling throughout.
- **DO** ensure BBA hours across all tasks for a recommendation sum to the
  allocated hours for that recommendation (provided in context).
- **DO** keep task descriptions concise — one to two sentences maximum.

---

## Output Format

Return a JSON object with a single `tasks` key containing an array of task rows:

```json
{
  "tasks": [
    {
      "rec_number": 1,
      "recommendation": "Recommendation Title",
      "owner": "Client",
      "task": "Specific client-owned task description",
      "advisorHrs": 0,
      "advisor": null,
      "status": "Not yet started",
      "notes": "",
      "timing": "Feb–Apr 2026"
    },
    {
      "rec_number": 1,
      "recommendation": "Recommendation Title",
      "owner": "BBA",
      "task": "Specific BBA advisory task description",
      "advisorHrs": 6.67,
      "advisor": "Lead Advisor Name",
      "status": "Not yet started",
      "notes": "",
      "timing": "Feb–Apr 2026"
    }
  ]
}
```

Return ONLY the JSON object. Do not include any markdown, explanation, or
commentary outside the JSON.
