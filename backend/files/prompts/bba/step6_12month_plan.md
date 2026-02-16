# Step 6: 12-Month Recommendations Plan

## Your Task

Expand each finding into a **short, practical** recommendation. Keep every section concise—avoid long paragraphs or long lists. Also include the "Notes on the 12-Month Recommendations Plan" disclaimer.

## Recommendation Structure (keep each section brief)

For each finding, create a recommendation containing:

### Purpose
**One short sentence** (max two) stating the goal and outcome. No lengthy explanation.

### Key Objectives
**2–3 short bullets** only. One line each; what success looks like.

### Actions to Complete
**3–5 short, specific steps** that the client can follow. One line per action; no sub-bullets or long descriptions.

### BBA Support Outline
**1–2 sentences** only. Say what BBA will do (advisory, facilitation, mentoring, or training) from: co-authoring plans, finance mentoring, change/project guidance, leadership mentoring, or training on SOPs. Pick only what applies.

### Expected Outcomes
**2–3 measurable outcomes** only. One short line each.

## Output Format

Return a JSON object with this structure:

```json
{
  "plan_notes": "The timeframes outlined in this plan are indicative only. Actual durations may be shorter or longer depending on priorities, workload, and availability across both the client organisation and Benchmark Business Advisory (BBA). Timelines may also shift due to illness, public holidays, annual leave, or unforeseen events. Where changes occur, all parties will provide as much notice as possible. Some activities will run concurrently or evolve as ongoing support. This plan is based on the current business state and may be updated as priorities change. It should therefore be read as a living plan—flexible and responsive to real-world progress, not a fixed schedule.",
  "recommendations": [
    {
      "number": 1,
      "title": "Recommendation Title",
      "timing": "Month 1-3",
      "purpose": "One short sentence for goal and outcome.",
      "key_objectives": [
        "Short objective 1",
        "Short objective 2"
      ],
      "actions": [
        "Short action 1",
        "Short action 2",
        "Short action 3"
      ],
      "bba_support": "1–2 sentences on BBA's role (advisory, mentoring, or training).",
      "expected_outcomes": [
        "Measurable outcome 1",
        "Measurable outcome 2"
      ]
    }
  ],
  "timeline_summary": {
    "title": "Implementation Timeline",
    "rows": [
      {
        "rec_number": 1,
        "recommendation": "Brief title",
        "focus_area": "Category",
        "timing": "Month 1-3",
        "key_outcome": "Primary outcome"
      }
    ]
  }
}
```

## Timing Rules (CRITICAL)

Distribute all recommendations **sequentially** across the 12 months so they flow one after another with minimal overlap:

- Each recommendation gets a **focused 1–2 month window** (e.g. "Month 1–2", "Month 3–4", "Month 5–6").
- Recommendations must **not** all start at Month 1. Spread them evenly across the year.
- The timing pattern should look like a staircase: Rec 1 → Month 1–2, Rec 2 → Month 2–3, Rec 3 → Month 3–4, etc.
- For 10 recommendations across 12 months, each recommendation should roughly occupy a 2-month window, advancing by ~1 month each step.
- **DO NOT** use "then ongoing", "ongoing", or open-ended timing. Every recommendation must have a concrete start and end month.
- The `timing` field must use the exact format: `"Month X–Y"` (e.g. `"Month 1–2"`, `"Month 5–6"`, `"Month 12"`).
- The `timeline_summary.rows` timing must exactly match the corresponding recommendation timing.

Example for 10 recommendations:
| Rec | Timing |
|-----|--------|
| 1   | Month 1–2 |
| 2   | Month 2–3 |
| 3   | Month 3–4 |
| 4   | Month 4–5 |
| 5   | Month 5–6 |
| 6   | Month 6–7 |
| 7   | Month 7–8 |
| 8   | Month 8–9 |
| 9   | Month 9–10 |
| 10  | Month 12 |

## Guidelines

- **Be concise**: every field should be short. No long paragraphs or padded lists.
- Recommendations should follow the finding ranking order
- BBA Support should enable client capability, not do the work for them
- Expected Outcomes should be measurable where possible
- Use British English spelling throughout
- Keep the timeline summary to one page
- If in doubt, use fewer bullets and shorter text—quality over quantity
