# Step 4: Expand Findings

## Your Task

Take the draft findings and write full paragraphs under "Key Findings – Ranked by Importance".
For each finding, write 1-3 paragraphs explaining the issue and its implications.

## Instructions

1. Maintain the ranking order from the draft findings
2. For each finding, write 1-3 substantial paragraphs covering:
   - The issue and its current state
   - The business impact (financial, operational, strategic)
   - Why it matters for future goals and growth
3. Be specific with examples where the documents support them
4. Avoid vague generalisations - be concrete and actionable

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
        "First paragraph explaining the issue...",
        "Second paragraph on business impact...",
        "Third paragraph on future implications..."
      ],
      "key_points": ["Bullet point 1", "Bullet point 2"]
    }
  ]
}
```

## Writing Guidelines

- Use professional, advisory language
- British English spelling (organisation, prioritise, colour, etc.)
- No bold text within paragraphs
- Each section should stand alone - no "as mentioned earlier" references
- Be factual and constructive, not alarmist
- Focus on solutions and clarity
- Write for business owners and managers - practical, not academic
