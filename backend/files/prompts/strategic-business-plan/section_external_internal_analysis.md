Draft the External and Internal Analysis section of the Strategic Business Plan for {client_name} ({industry}).

CONTEXT:
- Planning horizon: {planning_horizon}
- Target audience: {target_audience}
- Additional context: {additional_context}

CROSS-ANALYSIS:
{cross_analysis}

ADVISOR NOTES: {advisor_notes}
EMERGING THEMES: {emerging_themes}

PREVIOUSLY APPROVED SECTIONS:
{approved_sections}

UPLOADED FILES:
{file_references}

DIAGNOSTIC CONTEXT:
{diagnostic_context}

CUSTOM INSTRUCTIONS: {custom_instructions}

TASK:
LENGTH TARGET: 200 words maximum excluding table content. Tables replace prose — do not add narrative rows of text to describe what the table already shows.

This section must include both the analysis AND its strategic interpretation. Structure as follows:

1. Industry Environment
   - Summarise the competitive dynamics of the industry using a Porter's Five Forces lens.
   - Present as a structured table — exactly 5 rows, one per force:
     | Force | Intensity (High/Med/Low) | Key Observation |
   - Focus only on the observation most relevant to the strategic choices facing this business.

2. PESTLE Analysis
   - Present the key external factors in a table — exactly 6 rows, one per factor:
     | Factor | Observation | Implication |
   - One clear observation and one implication per factor. No prose.

3. SWOT Analysis
   - Present as a structured matrix/table.
   - Ensure strengths and weaknesses are genuinely internal; opportunities and threats genuinely external.
   - Be specific — no generic SWOT entries that could apply to any business.
   - Each SWOT cell: exactly 4 compact bullets at approximately 8 words each. The reader scans — do not write full sentences.

IMPORTANT RULES:
- Do NOT include Resources & Capabilities or Customer Dynamics here — those are covered in their own standalone sections.
- Do NOT assume owner dependency equals operational fragility.

End with a clearly labelled "Strategic Implications" subsection — exactly 4 bullets, one per category, max 15 words each:
- Lean into: [one bullet]
- Protect: [one bullet]
- Fix: [one bullet]
- Deprioritise: [one bullet]

Return a JSON object:
{{
  "content": "<HTML content including Industry Environment, PESTLE, and SWOT analyses>",
  "strategic_implications": "<HTML content for the Strategic Implications subsection>"
}}
