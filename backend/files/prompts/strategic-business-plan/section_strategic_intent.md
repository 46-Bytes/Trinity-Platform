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
Draft the following subsections using ONLY content from the provided source materials:

1. Vision Statement
   - A clear, aspirational statement of what the business aims to become.
   - Must be specific to this business — not a generic corporate vision.

2. Mission Statement
   - What the business does, for whom, and how it creates value.
   - Must be grounded in the current reality of the business.

3. Core Values
   - 3-6 values that genuinely drive behaviour and decision-making in this business.
   - Each value should have a brief explanation of what it means in practice.

4. Sustainable Competitive Advantage
   - What gives this business a durable edge over competitors?
   - Must be specific, evidence-based, and defensible.

CRITICAL RULE:
The Vision, Mission, Values, and Sustainable Competitive Advantage stated here must be treated as the definitive versions throughout the plan. If an employee-facing strategy document is later produced, these MUST appear word-for-word — no paraphrasing or dilution.

If the source materials do not contain explicit vision/mission/values statements, synthesise them from the strategic intent and priorities expressed in the workbook, but mark them as "[DRAFT — confirm with client]".

Return a JSON object:
{{
  "content": "<HTML content covering Vision, Mission, Values, and SCA>",
  "strategic_implications": null
}}
