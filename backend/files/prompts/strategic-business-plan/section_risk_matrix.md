Draft the Risk Matrix and Analysis section of the Strategic Business Plan for {client_name} ({industry}).

This section identifies the key risks to successful strategy execution. It must be grounded in the realities of this specific business, not generic risk categories.

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
LENGTH TARGET: 100 words maximum for the mitigation themes prose. The risk table is the substance — keep it tight.

1. Risk Assessment Matrix
   Identify 5–7 risks drawn from threats in the SWOT, PESTLE pressures, capacity constraints,
   financial risks, and execution risks from the growth plays. Prioritise the highest-impact risks — do not list everything.

   Present as a table:
   | Risk | Likelihood (H/M/L) | Impact (H/M/L) | Risk Rating | Mitigation | Owner |

   Risk Rating = Likelihood × Impact (H/H = Critical, H/M or M/H = High, M/M = Medium, etc.)

2. Mitigation Themes
   3–4 cross-cutting themes only, max 15 words each. Present as a bullet list — not per-risk essays.

CRITICAL RULES:
- Risks must be specific to this business and this strategy — not generic industry risks.
- No narrative assessments per risk. If a risk needs elaboration, it belongs in the relevant functional chapter.
- The risk matrix table plus the mitigation themes bullet list is the complete chapter.

Return a JSON object:
{{
  "content": "<HTML content with risk matrix table and critical risk detail>",
  "strategic_implications": null
}}
