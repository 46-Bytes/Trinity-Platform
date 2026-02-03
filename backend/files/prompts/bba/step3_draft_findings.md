# Step 3: Draft Findings

## Your Task

Analyse all uploaded files and advisor notes for recurring themes, risks, and issues.
Generate a proposed Top 10 Findings list with one-line summaries.

## Instructions

1. Review ALL uploaded documents thoroughly
2. Identify key issues, risks, and areas requiring attention
3. Group related issues into coherent findings
4. Rank findings by materiality (financial, operational, strategic impact)
5. Consider urgency and dependency order
6. High impact, cross-functional issues should appear first

## Output Format

Return a JSON object with this structure:

```json
{
  "findings": [
    {
      "rank": 1,
      "title": "Finding Title (concise, descriptive)",
      "summary": "One-line summary explaining the finding and its significance",
      "priority_area": "Category (e.g., Financial, Operations, People, Compliance)",
      "impact": "high|medium|low",
      "urgency": "immediate|short-term|medium-term"
    }
  ],
  "analysis_notes": "Brief notes on the analysis approach and any assumptions made",
  "files_analysed": ["List of files that were analysed"]
}
```

## Guidelines

- Provide exactly 10 findings (or fewer if the documents don't support 10)
- Each finding should be distinct and actionable
- Summaries should be clear and jargon-free
- Consider the client's strategic priorities when ranking
- If sale-readiness topics should be excluded, do not include them
- Use British English spelling throughout
