Draft the Executive Summary section of the Strategic Business Plan for {client_name} ({industry}).

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
This section is drafted AFTER all other sections are approved. It synthesises the completed
plan — it does not introduce new content or re-explain findings covered in other sections.

Write exactly 5 paragraphs:
1. Current state — the business as it stands: size, market position, core strengths, the moment it is at.
2. What needs fixing — the strategic challenge or tension the plan addresses. State it plainly.
3. The phase logic — how the strategy is sequenced, and why this order. Reference the growth plays by name.
4. The acquisition truth — if acquisition features in the strategy, state it plainly here (what, why, when). If it does not, omit this paragraph and write 4 paragraphs instead.
5. Target outcome — what the business looks like at the end of the planning horizon if the strategy succeeds.

Do not summarise what each section contains. Do not re-explain diagnostic findings.
Write for the owner who commissioned this plan — they know their business.

Return a JSON object:
{{
  "content": "<HTML content for the Executive Summary>",
  "strategic_implications": null
}}
