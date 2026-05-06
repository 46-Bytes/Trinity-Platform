Draft the Strategic Intent Overview section of the Strategic Business Plan for {client_name} ({industry}).

This section establishes the foundational strategic direction — the "why" behind the plan. It must feel decisive and owned, not aspirational and generic.

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
LENGTH TARGET: 250 words maximum for the entire section. Be surgical.

1. Vision Statement
   - One sentence only — maximum 20 words.
   - Must be specific to this business — not a generic corporate vision.

2. Mission Statement
   - One to two sentences — maximum 30 words total.
   - What the business does, for whom, and how it creates value.

3. Core Values
   - 4–6 values. Present as a bullet list — NOT a table.
   - Format: "• [Value] — [one-sentence explanation, max 12 words]"
   - No additional prose.

4. Business Goals (Planning Horizon)
   - 3–5 goals. One tight bullet per goal — specific and measurable where possible.
   - No sub-bullets, no explanatory paragraphs.

5. Sustainable Competitive Advantage
   - 3–5 points. One line each — maximum 15 words per point.
   - Present as a bullet list — NOT a table.
   - Must be specific and defensible, not generic.

CRITICAL RULE:
The Vision, Mission, Values, and SCA stated here are the definitive versions for the entire plan — no paraphrasing elsewhere.

If source materials do not contain explicit statements, synthesise from the workbook and mark as "[DRAFT — confirm with client]".

Return a JSON object:
{{
  "content": "<HTML content covering Vision, Mission, Values (bullet list), Business Goals (bullet list), and SCA (bullet list)>",
  "strategic_implications": null
}}
