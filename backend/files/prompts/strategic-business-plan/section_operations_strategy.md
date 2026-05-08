Draft the Operational Strategy section of the Strategic Business Plan for {client_name} ({industry}).

This section defines how the business must operate to deliver its strategy efficiently, consistently, and at scale. It should identify operational moats worth protecting and the most critical process improvements required over the planning horizon.

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
LENGTH TARGET: 150 words maximum excluding the initiatives table. 3–4 sentences for the prose section only.
Draft the following subsections using ONLY content from the provided source materials:

1. Operational Position
   - 3–4 sentences covering: how the business currently delivers, key operational strengths, critical bottlenecks, and what needs to change by end of the planning horizon.
   - Fold future-state direction into the last 1–2 sentences — do not create a separate "Target Operating Model" subsection.
   - If technology is a material issue, include 1 sentence on it here.

2. Key Operational Initiatives
   Present as a table — maximum 5 rows:
   | Initiative | Purpose | Owner | Timeline | Link to Strategy |

   Cover efficiency improvements, technology investments, process redesign (only where supported by source materials).

IMPORTANT RULES:
- Link every initiative back to a specific strategic priority or growth play from approved sections
- Apply the owner dependency nuance rule — distinguish operational capacity from concentration of strategic authority
- Language must reflect capability being strengthened, not weakness being corrected

Return a JSON object:
{{
  "content": "<HTML content with all subsections including the initiatives table>",
  "strategic_implications": null
}}
