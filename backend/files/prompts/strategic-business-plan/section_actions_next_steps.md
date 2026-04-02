Draft the Actions List and Next Steps section of the Strategic Business Plan for {client_name} ({industry}).

This is the final substantive section. It must provide a clear, actionable list of next steps AND end with a Strategic Commitment statement that closes the plan with confidence and momentum.

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
Draft the following:

1. Immediate Actions (Next 30 Days)
   5-8 specific actions that should begin immediately after plan approval.
   Present as a table:
   | Action | Owner | Deadline | Priority | Status |

2. Short-Term Actions (30-90 Days)
   Actions that build on the immediate steps and establish momentum.
   Present as a table with the same columns.

3. Ongoing Commitments
   Recurring activities that must be maintained throughout the planning horizon:
   - Strategy review cadence (quarterly, monthly)
   - KPI reporting schedule
   - Team communication rhythm

4. Strategic Commitment (MANDATORY)
   The plan MUST end with a short closing section (2-3 paragraphs) that:
   - Reaffirms confidence in the existing business and its people
   - Clarifies what is now decided (the strategic choices made in this plan)
   - States what will be protected (core strengths, values, relationships)
   - Signals momentum and intent — the plan ends with commitment, not analysis

   This closing statement must feel decisive and forward-looking. It is the last thing the reader sees.

CRITICAL RULES:
- Actions must be specific and assignable — not vague aspirations.
- Every action must link to a strategic priority or initiative from earlier sections.
- The Strategic Commitment section is NON-NEGOTIABLE — every plan must end with it.
- Do not introduce new analysis or findings in this section.

Return a JSON object:
{{
  "content": "<HTML content with action tables and Strategic Commitment closing>",
  "strategic_implications": null
}}
