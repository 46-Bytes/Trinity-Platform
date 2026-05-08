Draft the Actions List (Implementation Plan) section of the Strategic Business Plan for {client_name} ({industry}).

This section is the bridge between strategy and execution. It must provide a prioritised, assignable action plan and close the substantive plan with a Strategic Commitment statement.

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
LENGTH TARGET: 350 words maximum excluding action tables. Tables carry the content — prose is the connector, not the substance.
Draft the following:

1. Immediate Actions (Next 30 Days)
   5-8 specific actions that should begin immediately after plan approval.
   Present as a table:
   | Action | Owner | Deadline | Priority | Link to Strategy |

2. Short-Term Actions (30–90 Days)
   Actions that build on the immediate steps and establish momentum.
   Present as a table with the same columns.

3. Ongoing Commitments
   Recurring activities that must be maintained throughout the planning horizon:
   - Strategy review cadence (quarterly, monthly)
   - KPI reporting schedule
   - Team communication rhythm

4. A Note on Acquisitions (conditional)
   If acquisition features in the growth strategy, include a 2–3 sentence owner-directed note:
   what the business is looking for and why now is the right time to pursue it.
   Do not include rationale for the sequencing logic — that belongs in Growth Opportunities.
   If acquisitions are not relevant, omit this subsection entirely.

5. Strategic Commitment (MANDATORY)
   The plan MUST close with a short commitment section (2-3 paragraphs) that:
   - Reaffirms confidence in the existing business and its people
   - Clarifies what is now decided (the strategic choices made in this plan)
   - States what will be protected (core strengths, values, relationships)
   - Signals momentum and intent — the plan ends with commitment, not analysis

   This closing statement must feel decisive and forward-looking. It is the last thing the reader sees.

CRITICAL RULES:
- Every action must link to a strategic priority or initiative from earlier sections.
- Actions must be specific and assignable — not vague aspirations.
- The Strategic Commitment section is NON-NEGOTIABLE — every plan must include it.
- Do not introduce new analysis or findings in this section.

Return a JSON object:
{{
  "content": "<HTML content with all action tables, implementation roadmap, and Strategic Commitment closing>",
  "strategic_implications": null
}}
