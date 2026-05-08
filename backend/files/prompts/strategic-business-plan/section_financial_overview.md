Draft the Financial Overview section of the Strategic Business Plan for {client_name} ({industry}).

This section presents the financial context, targets, and investment requirements that underpin the strategy. It must be grounded entirely in data from the source materials.

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
LENGTH TARGET: 150 words maximum excluding tables. Financial data goes in tables — not prose.
Draft the following subsections using ONLY financial data from the provided source materials:

1. Current Financial Position
   - Key financial metrics (revenue, profit, margins, cash position)
   - Present as a table where data is available — maximum 5 rows

2. Financial Targets
   - Revenue, profit, and margin targets for the planning horizon
   - Present as a table — maximum 5 metrics:
   | Metric | Current | Year 1 Target | Year 2 Target | Year 3 Target |
   - For a 1-year planning horizon, omit Year 2 and Year 3 columns.

3. Investment Requirements
   - 3–4 bullets only: capex, operating cost changes, funding sources

4. Key Financial Assumptions
   - 3–4 bullets only: assumptions underpinning the targets and key external risk factors

CRITICAL RULES:
- NEVER invent financial figures. If a number is not in the source materials, do not include it.
- Mark any gaps as "[Financial data not provided — confirm with client]".
- Use tables for all financial data presentation.
- Keep commentary factual — this is not the place for aspirational language.

Return a JSON object:
{{
  "content": "<HTML content with financial tables and commentary>",
  "strategic_implications": null
}}
