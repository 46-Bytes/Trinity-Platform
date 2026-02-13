# Phase 3 – PowerPoint Presentation Generator

## Your Task

Generate concise, spoken-delivery slide content for a diagnostic presentation.
The slides will be used in a professional advisory presentation delivered to the
client's leadership team. Content must be visually clean, confident, and suitable
for projection — not essay style.

---

## Slide Structure

Generate the following slides in order:

### Slide 0 – Title
- Type: `title`
- Title: "Diagnostic Findings & Recommendations"
- Subtitle: "[Client Name] | [Month Year]"

### Slide 1 – Executive Summary
- Type: `executive_summary`
- Title: "Executive Summary"
- 3–5 bullet points summarising the key themes and overall direction.
  Distil the executive summary text into concise presentation bullets.

### Slide 2 – How Recommendations Are Structured
- Type: `structure`
- Title: "How Recommendations Are Structured"
- Bullets explaining the structure of each recommendation:
  Purpose, Key Objectives, Actions to Complete, BBA Support Outline,
  Expected Outcomes. Keep to 5 bullets maximum.

### Slides 3 to N – One Slide Per Recommendation
- Type: `recommendation`
- Title: "[Number]. [Recommendation Title]"
- For each recommendation, create three sections with 2–4 bullet points each:
  - **finding**: What was identified in the diagnostic (the problem/gap)
  - **recommendation_bullets**: What should be done (the solution)
  - **outcome**: What success looks like (the result)
- Draw content from the expanded findings, snapshot table, and 12-month plan.
- Keep each section to 2–4 bullets maximum — the content must fit on one slide.

### Second-to-Last Slide – Implementation Timeline
- Type: `timeline`
- Title: "Implementation Timeline"
- Provide a `rows` array with one entry per recommendation:
  `{"rec": 1, "title": "Short title", "timing": "Month 1–3", "outcome": "Key outcome"}`

### Last Slide – Next Steps
- Type: `next_steps`
- Title: "Next Steps"
- 3–5 bullets summarising agreed priorities, immediate actions, and how the
  engagement will proceed. Include a prompt to discuss questions.

---

## Content Rules

- **Spoken-delivery tone**: concise, confident, professional.
- **British English** spelling throughout.
- **No bold inside bullet text** — bold is for slide headings only.
- **2–5 bullet points per section** maximum. Each bullet should be one
  short sentence or phrase that fits on a single line.
- **Do not repeat** the same point across multiple slides.
- **Do not invent** facts or numbers not present in the source data.
- Every bullet must be directly traceable to the diagnostic report content.

---

## Output Format

Return a JSON object with a single `slides` key containing an array of slide
objects. Each slide must include `index`, `type`, `title`, and `approved: false`.

```json
{
  "slides": [
    {
      "index": 0,
      "type": "title",
      "title": "Diagnostic Findings & Recommendations",
      "subtitle": "Client Name | Month Year",
      "approved": false
    },
    {
      "index": 1,
      "type": "executive_summary",
      "title": "Executive Summary",
      "bullets": ["Point 1", "Point 2", "Point 3"],
      "approved": false
    },
    {
      "index": 2,
      "type": "structure",
      "title": "How Recommendations Are Structured",
      "bullets": ["Purpose — ...", "Key Objectives — ...", "Actions — ...", "BBA Support — ...", "Expected Outcomes — ..."],
      "approved": false
    },
    {
      "index": 3,
      "type": "recommendation",
      "title": "1. Recommendation Title",
      "finding": ["Finding bullet 1", "Finding bullet 2"],
      "recommendation_bullets": ["Recommendation bullet 1", "Recommendation bullet 2"],
      "outcome": ["Outcome bullet 1", "Outcome bullet 2"],
      "approved": false
    },
    {
      "index": 13,
      "type": "timeline",
      "title": "Implementation Timeline",
      "rows": [
        {"rec": 1, "title": "Short title", "timing": "Month 1–3", "outcome": "Key outcome"}
      ],
      "approved": false
    },
    {
      "index": 14,
      "type": "next_steps",
      "title": "Next Steps",
      "bullets": ["Priority 1", "Priority 2", "Discuss questions"],
      "approved": false
    }
  ]
}
```

Return ONLY the JSON object. Do not include any markdown, explanation, or
commentary outside the JSON.
