Draft the Human Resource Strategy and Key Recommendations section of the Strategic Business Plan for {client_name} ({industry}).

This section defines the people, leadership, and culture strategy required to execute the plan. It must be honest about current state, clear on what needs to change, and realistic about what the business can achieve within the planning horizon.

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
LENGTH TARGET: 280 words maximum excluding the metrics table. Each prose subsection is 2–3 sentences only — cap bullet lists at 5 items.
Draft the following subsections using ONLY content from the provided source materials:

1. Current People Position
   - Team structure, headcount, key roles
   - Current capability strengths and gaps
   - Culture and engagement observations from diagnostics

2. Owner and Leadership Dependency
   - Apply the owner dependency nuance rule:
     - Distinguish between day-to-day operational coverage without the owner vs. concentration of strategic value, client relationships, or decision authority
   - Language must reflect strength being professionalised, not weakness being patched

3. People Strategy for the Planning Horizon
   - Recruitment priorities (roles critical to executing the strategy)
   - Capability development and training focus areas
   - Succession and retention approach for key people

4. People Metrics Scoreboard
   Present as a table — only include metrics evidenced in source materials or identified as targets:
   | Metric | Current | Target (End of Horizon) | Owner |

   Examples (only if relevant): headcount, retention rate, time-to-hire, training investment, engagement score.

5. Culture and Leadership Development
   - What cultural attributes must be preserved or strengthened?
   - Leadership development priorities for the planning period

IMPORTANT RULES:
- Do NOT assume owner dependency equals operational fragility
- Every recruitment or development initiative must link to a strategic priority
- If headcount or HR data is not in source materials, note the gap clearly

Return a JSON object:
{{
  "content": "<HTML content covering all subsections including the people metrics table>",
  "strategic_implications": null
}}
