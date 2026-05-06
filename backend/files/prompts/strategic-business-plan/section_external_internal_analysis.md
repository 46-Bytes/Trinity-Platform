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
LENGTH TARGET: 350 words maximum excluding table content. Tables replace prose — do not add narrative rows of text to describe what the table already shows.

This section must include both the analysis AND its strategic interpretation. Structure as follows:

1. Industry Environment
   - Summarise the competitive dynamics of the industry using a Porter's Five Forces lens.
   - Present as a structured table:
     | Force | Intensity (High/Med/Low) | Key Observations |
   - Focus only on forces that are materially relevant to the strategic choices facing this business.

2. PESTLE Analysis
   - Present the key external factors in a table format.
   - Cover Political, Economic, Social, Technological, Legal, Environmental factors.
   - Focus on factors most relevant to this specific business and industry.
   - Each factor: one row, one clear observation, one implication.

3. SWOT Analysis
   - Present as a structured matrix/table.
   - Ensure strengths and weaknesses are genuinely internal.
   - Ensure opportunities and threats are genuinely external.
   - Be specific — no generic SWOT entries that could apply to any business.
   - Each SWOT cell uses compact bullets: 6 bullets at approximately 8 words each. The reader scans — do not write full sentences.

IMPORTANT RULES:
- Default to tables where comparison or prioritisation exists.
- Do NOT assume owner dependency equals operational fragility — distinguish between day-to-day operations and concentration of strategic value.
- Each framework must be BOTH presented AND interpreted strategically.
- Do NOT include Resources & Capabilities or Customer Dynamics here — those are covered in their own standalone sections.

End with a clearly labelled "Strategic Implications" subsection that states what the business should:
- Lean into
- Protect
- Fix
- Deprioritise or avoid

Return a JSON object:
{{
  "content": "<HTML content including Industry Environment, PESTLE, and SWOT analyses>",
  "strategic_implications": "<HTML content for the Strategic Implications subsection>"
}}
