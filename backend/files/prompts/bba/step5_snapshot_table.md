# Step 5: Snapshot Table

## Your Task

Create the "Key Findings & Recommendations Snapshot" - a concise three-column table.

## Table Structure

| Priority Area | Key Findings | Recommendations |
|--------------|--------------|-----------------|
| Category | Brief finding description | Brief recommendation |

## Instructions

1. Summarise each finding into a concise table row
2. Keep text brief - the entire table should fit on one Word page
3. Priority Area should be the category/theme (e.g., Financial, Operations, People)
4. Key Findings column: 1-2 sentences maximum
5. Recommendations column: 1-2 sentences maximum
6. Maintain the ranking order from expanded findings

## Output Format

Return a JSON object with this structure:

```json
{
  "snapshot_table": {
    "title": "Key Findings & Recommendations Snapshot",
    "rows": [
      {
        "rank": 1,
        "priority_area": "Financial Reporting",
        "key_finding": "Management accounts lack detail and timeliness, limiting decision-making capability.",
        "recommendation": "Implement monthly management reporting with KPI dashboards and variance analysis."
      }
    ]
  }
}
```

## Guidelines

- Include as many rows as the expanded findings support (typically 5–15; no hard maximum)
- Each cell should be concise but complete
- Use action-oriented language in recommendations
- Ensure consistency with the expanded findings
- British English spelling throughout
