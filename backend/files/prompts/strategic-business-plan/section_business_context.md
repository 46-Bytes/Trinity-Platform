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
LENGTH TARGET: 350 words maximum for the entire section. This is context-setting, not analysis.

1. Business Overview
   - 4–6 bullet points covering: what it does, ownership structure, year established, headcount, locations.
   - No prose paragraphs.

2. Current Market Position
   - 2–3 sentences only: where the business sits, its competitive positioning, key customer segments.

3. Operating Environment
   - 3–4 bullet points: the most relevant market trends, competitive pressures, or regulatory conditions.
   - Do not write a paragraph per point.

4. Recent Performance Summary
   - One table where data is available: metric | current value | trend.
   - If no data in source materials, write one sentence noting the gap.

5. Key Stakeholders
   - Bullet list only — name, role, relevance. 3–8 lines maximum.

6. Strategic Context and Constraints
   - 2–3 sentences: the most important constraints and any non-negotiable decisions already made.

Do NOT invent any financial figures, employee counts, or historical facts. If information is not in the source materials, omit the subsection or mark as "[Data not provided — confirm with client]".

Do NOT invent any financial figures, employee counts, or historical facts. If information is not in the source materials, omit the subsection or mark as "[Data not provided — confirm with client]".

Return a JSON object:
{{
  "content": "<HTML content covering the business context>",
  "strategic_implications": null
}}
