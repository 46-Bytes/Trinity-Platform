# Step 7: Review & Edit

## Your Task

Apply requested edits to the report while maintaining consistency and quality.

## Types of Edits You May Receive

1. **Re-ranking findings**: Change the order of findings based on advisor input
2. **Timing adjustments**: Modify the timing/month for recommendations
3. **Language changes**: Reword sections for clarity or tone
4. **Adding content**: Include additional findings or recommendations
5. **Removing content**: Remove specific findings or recommendations
6. **Merging/splitting**: Combine or separate findings as requested

## Instructions

1. Apply all requested changes precisely
2. Maintain consistent formatting throughout
3. Preserve section order and structure
4. Keep professional, advisory tone
5. Use British English spelling
6. Ensure all cross-references remain accurate after edits
7. Update numbering if items are added/removed/reordered

## Output Format

Return a JSON object with the updated sections:

```json
{
  "updated_sections": {
    "draft_findings": [...],
    "expanded_findings": [...],
    "snapshot_table": {...},
    "twelve_month_plan": {...}
  },
  "changes_made": [
    "Description of change 1",
    "Description of change 2"
  ],
  "warnings": [
    "Any warnings about potential issues with the edits"
  ]
}
```

Only include sections that were actually modified.

## Guidelines

- Preserve the advisor's intent in all edits
- If an edit request is unclear, note it in warnings
- Maintain consistency across all sections
- Update related sections when a change affects them
- Keep the professional tone consistent
