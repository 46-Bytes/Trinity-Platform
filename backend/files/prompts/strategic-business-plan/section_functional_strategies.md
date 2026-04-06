Draft the Functional and Thematic Strategies section of the Strategic Business Plan for {client_name} ({industry}).

This section translates the strategic direction into functional strategies across the key areas of the business. Each functional strategy must link directly back to the strategic priorities and growth plays already approved.

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
Draft functional strategies for each relevant area. Only include areas where the source materials provide sufficient input. Typical areas include:

1. People and Leadership Strategy
   - Capability gaps, recruitment needs, succession, leadership development
   - IMPORTANT: Apply the owner dependency nuance rule — distinguish between day-to-day operational ability without the owner vs. concentration of strategic value/decision authority
   - Language must reflect strength being professionalised, not weakness being fixed

2. Operations and Process Strategy
   - Efficiency improvements, systems, technology, supply chain
   - Link to capacity constraints identified in diagnostics

3. Sales and Marketing Strategy
   - Customer acquisition, retention, market positioning, brand
   - Link to customer dynamics from the diagnostic sections

4. Technology and Digital Strategy
   - Systems, automation, digital transformation
   - Only if relevant to this business

5. Financial Strategy
   - Capital allocation, investment priorities, cost management
   - Reference the Financial Overview section for alignment

For each functional area:
- State the current position (from diagnostics)
- Define the target state (from strategic direction)
- List 3-5 key initiatives to bridge the gap
- Assign ownership where possible

Use a table for each functional area:
| Initiative | Purpose | Owner | Timeline | Link to Strategic Priority |

This section MUST end with a "Strategic Implications" subsection.

Return a JSON object:
{{
  "content": "<HTML content with functional strategies and tables>",
  "strategic_implications": "<HTML stating cross-cutting implications from the functional analysis>"
}}
