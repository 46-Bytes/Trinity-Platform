Draft the Integrated Strategic Implications and Alignment section of the Strategic Business Plan for {client_name} ({industry}).

CONTEXT:
- Planning horizon: {planning_horizon}
- Target audience: {target_audience}
- Additional context: {additional_context}

CROSS-ANALYSIS:
{cross_analysis}

ADVISOR NOTES: {advisor_notes}
EMERGING THEMES: {emerging_themes}

ALL APPROVED SECTIONS:
{approved_sections}

UPLOADED FILES:
{file_references}

DIAGNOSTIC CONTEXT:
{diagnostic_context}

CUSTOM INSTRUCTIONS: {custom_instructions}

TASK:
LENGTH TARGET: 150 words maximum excluding the correlation table. This section integrates — it does not repeat. Name themes, do not re-explain them.

1. Cross-Section Correlation Matrix
   - Present a table showing where strategic themes recur across sections — maximum 4 rows.
   | Theme | Sections Where It Appears | Signal Strength (Very Strong / Strong / Moderate) |

2. Integrated Implications
   - 3–4 bullets only: what the integrated picture means for the business.
   - Resolve repeated themes into clear commitments. Name what is non-negotiable.

3. What Must Remain True
   - 3–4 bullets only: conditions, assets, and behaviours the business must protect.

4. Way Forward
   - 2–3 sentences only. Name the one or two most important strategic decisions and what the business must do first.
   - This is not a second commitment statement — keep it directional, not aspirational.

Return a JSON object:
{{
  "content": "<HTML content including the correlation matrix, integrated implications, what must remain true, and Strategic Commitment and Way Forward>",
  "strategic_implications": null
}}
