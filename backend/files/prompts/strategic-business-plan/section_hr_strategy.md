Draft the HR Strategy section of the Strategic Business Plan for {client_name} ({industry}).

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
LENGTH TARGET: 150 words maximum excluding the metrics table.
Draft the following subsections using ONLY content from the provided source materials:

1. Current People Position
   - 3–4 sentences covering: team structure, headcount, key capability strengths and gaps, and owner/leadership dependency.
   - On owner dependency, distinguish between day-to-day operational coverage and concentration of strategic value, client relationships, or decision authority. Language must reflect strength being professionalised, not weakness being patched.

2. People Strategy
   - 3–4 bullets covering: recruitment priorities (roles critical to executing the strategy), capability development focus, succession/retention approach, and one bullet on culture (what must be preserved or strengthened).

3. People Metrics Scoreboard
   Present as a table — maximum 5 rows only. Tag each metric as Leading (predictive) or Lagging (outcome-based):
   | Metric | Type (Leading / Lagging) | Current | Target (End of Horizon) | Owner |

   Examples (only if relevant): headcount, retention rate, time-to-hire, training investment, engagement score.

IMPORTANT RULES:
- Do NOT assume owner dependency equals operational fragility
- Every recruitment or development initiative must link to a strategic priority
- If headcount or HR data is not in source materials, note the gap clearly

Return a JSON object:
{{
  "content": "<HTML content covering all subsections including the people metrics table>",
  "strategic_implications": null
}}
