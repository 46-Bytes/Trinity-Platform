Draft the Business and Context Overview section of the Strategic Business Plan for {client_name} ({industry}).

This section provides the factual foundation — who the business is, where it sits, and what context the strategy operates within. It must ground the reader before the diagnostic sections begin.

CONTEXT:
- Planning horizon: {planning_horizon}
- Target audience: {target_audience}
- Additional context: {additional_context}

CROSS-ANALYSIS: {cross_analysis}
ADVISOR NOTES: {advisor_notes}
EMERGING THEMES: {emerging_themes}
PREVIOUSLY APPROVED SECTIONS: {approved_sections}
UPLOADED FILES: {file_references}
DIAGNOSTIC CONTEXT: {diagnostic_context}
CUSTOM INSTRUCTIONS: {custom_instructions}

TASK:
Draft the following subsections using ONLY content from the provided source materials.
LENGTH TARGET: 200 words maximum for the entire section. This is context-setting, not analysis.

1. Business Overview
   - 4–5 bullet points covering: what it does, ownership structure, year established, headcount, locations, and one bullet for market position.
   - No prose paragraphs.

2. Operating Environment
   - 3–4 bullet points: the most relevant market trends, competitive pressures, regulatory conditions, and key strategic constraints.
   - Include any non-negotiable decisions already made as the last bullet.

3. Recent Performance
   - One table only — maximum 5 rows: | Metric | Current Value | Trend |
   - If no data in source materials, write one sentence noting the gap.

Do NOT invent any financial figures, employee counts, or historical facts. If information is not in the source materials, omit the subsection or mark as "[Data not provided — confirm with client]".

Return a JSON object:
{{
  "content": "<HTML content covering the business context>",
  "strategic_implications": null
}}
