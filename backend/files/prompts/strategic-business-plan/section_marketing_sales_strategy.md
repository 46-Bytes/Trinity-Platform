Draft the Marketing and Sales Strategy section of the Strategic Business Plan for {client_name} ({industry}).

This section defines how the business will attract, convert, and retain its target customers over the planning horizon. It must connect directly to the Customer Dynamics and Growth Opportunities sections already approved.

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
LENGTH TARGET: 150 words maximum excluding the acquisition table. Reference Customer Dynamics and Growth Opportunities — do not repeat them.
Draft the following subsections using ONLY content from the provided source materials:

1. Positioning and Channel Strategy
   - 4–5 bullets covering: brand position (what the business wants to be known for), core value proposition, channels to prioritise, and channels to deprioritise or exit.
   - Reference the priority segments from Customer Dynamics in one bullet — do not repeat that section's analysis.

2. Customer Acquisition
   - Key initiatives to attract new customers — maximum 4 rows:
     | Initiative | Target Segment | Channel | Owner | Timeline |

3. Retention
   - 2–3 bullets only: how the business will deepen relationships with existing customers and any cross-sell or loyalty priorities (only where evidenced in source materials).

IMPORTANT RULES:
- Every marketing initiative must link to a named growth play or strategic priority from earlier approved sections
- Do not invent campaign ideas or channel strategies not supported by source materials

Return a JSON object:
{{
  "content": "<HTML content covering all five subsections>",
  "strategic_implications": null
}}
