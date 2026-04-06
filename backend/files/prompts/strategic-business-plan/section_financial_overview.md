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
Draft the following subsections using ONLY financial data from the provided source materials:

1. Current Financial Position
   - Key financial metrics (revenue, profit, margins, cash position)
   - Trends over recent periods
   - Present as a table where data is available

2. Financial Targets
   - Revenue, profit, and margin targets for the planning horizon
   - Growth rate assumptions
   - Present as a table:
   | Metric | Current | Year 1 Target | Year 2 Target | Year 3 Target |

3. Investment Requirements
   - Capital expenditure needed to execute the strategy
   - Operating cost changes anticipated
   - Funding sources (retained earnings, debt, equity)

4. Key Financial Assumptions
   - What assumptions underpin the targets?
   - What external factors could affect financial performance?

CRITICAL RULES:
- NEVER invent financial figures. If a number is not in the source materials, do not include it.
- If financial data is sparse, state clearly what data is available and what is missing.
- Mark any gaps as "[Financial data not provided — confirm with client]".
- Use tables for all financial data presentation.
- Keep commentary factual — this is not the place for aspirational language.

Return a JSON object:
{{
  "content": "<HTML content with financial tables and commentary>",
  "strategic_implications": null
}}
