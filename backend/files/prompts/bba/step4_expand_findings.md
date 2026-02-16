# Step 4: Expand Findings

## Your Task

Take the draft findings and write clear, concise paragraphs under "Key Findings – Ranked by Importance".
For each finding, write **one or two short paragraphs** that are comprehensive but not long.

## Instructions

1. Maintain the ranking order from the draft findings
2. For each finding, write **1–2 paragraphs** (2–4 sentences each) covering:
   - The issue and its current state
   - The business impact and why it matters for goals and growth
3. Be **concise**: comprehensive and actionable, but avoid long-winded or repetitive text
4. Be specific with examples where the documents support them; avoid vague generalisations
5. Write for quick reading: every sentence should add value

## Output Format

Return a JSON object with this structure:

```json
{
  "expanded_findings": [
    {
      "rank": 1,
      "title": "Finding Title",
      "priority_area": "Category",
      "paragraphs": [
        "First short paragraph explaining the issue and current state.",
        "Second short paragraph on business impact and why it matters."
      ],
      "key_points": ["Bullet point 1", "Bullet point 2"]
    }
  ]
}
```

## Writing Guidelines

- Use professional, advisory language; keep paragraphs **short** (2–4 sentences)
- British English spelling (organisation, prioritise, colour, etc.)
- No bold text within paragraphs
- Each section should stand alone – no "as mentioned earlier" references
- Be factual and constructive, not alarmist
- Focus on solutions and clarity; **avoid unnecessary length or filler**
- Write for business owners and managers – practical and scannable
