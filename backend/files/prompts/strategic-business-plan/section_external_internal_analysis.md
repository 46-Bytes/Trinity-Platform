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
This section must include both the analysis AND its strategic interpretation. Structure as follows:

1. PESTLE Analysis
   - Present the key external factors using a table format
   - Cover Political, Economic, Social, Technological, Legal, Environmental factors
   - Focus on factors most relevant to this specific business and industry

2. SWOT Analysis
   - Present as a structured matrix/table
   - Ensure strengths and weaknesses are genuinely internal
   - Ensure opportunities and threats are genuinely external

3. Resources and Capabilities Assessment
   - Key resources (people, systems, IP, relationships)
   - Core capabilities and where they need strengthening

4. Customer Dynamics
   - Customer segments and their relative importance
   - Customer needs, retention drivers, and risks

IMPORTANT RULES:
- Default to tables where comparison or prioritisation exists
- Do NOT assume owner dependency equals operational fragility — distinguish between day-to-day operations and concentration of strategic value
- Each framework must be BOTH presented AND interpreted strategically

End with a clearly labelled "Strategic Implications" subsection that states what the business should:
- Lean into
- Protect
- Fix
- Deprioritise or avoid

Return a JSON object:
{{
  "content": "<HTML content including all four sub-analyses>",
  "strategic_implications": "<HTML content for the Strategic Implications subsection>"
}}
