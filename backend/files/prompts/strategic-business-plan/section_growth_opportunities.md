Draft the Growth Opportunities and Strategic Direction section of the Strategic Business Plan for {client_name} ({industry}).

This section translates the diagnostic findings into explicit, actionable growth decisions. It must move BEYOND frameworks into named, scoped, sequenced growth plays.

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
LENGTH TARGET: 250 words maximum excluding table content. The Ansoff Matrix and Named Growth Plays are tables — they replace prose, not supplement it.
Draft the following:

1. Growth Direction Summary
   - Where is the business choosing to grow? (markets, products, capabilities)
   - What is the strategic logic behind this direction?
   - 3–4 sentences only. Reference the diagnostic findings that support this direction.

2. Ansoff Matrix
   - Map the identified growth options against the Ansoff Matrix quadrants.
   - Present as a table:
     | Quadrant | Growth Option | Rationale | Risk Level |
   - This is a framing tool — not the conclusion. Use it to show the strategic range considered.

3. Named Growth Plays
   Maximum 4 plays. For each, articulate:
   - Play name (a clear, descriptive label)
   - Scope (what it includes and excludes)
   - Sequencing logic (why this play comes before/after others)
   - Ownership (who is accountable)
   - Constraints and guardrails (what could limit this play, what must be true for it to work)

   Present as a table:
   | Growth Play | Scope | Sequence | Owner | Key Constraint |

4. Strategic Direction Choices
   - 2–3 sentences only: what the business is choosing TO DO and what it is explicitly NOT doing.

CRITICAL RULES:
- The Ansoff Matrix is an input, not an output. Always follow it with the Named Growth Plays that translate it into decisions.
- Clients value clarity and decision context over named tools. Translate frameworks into explicit choices.
- Growth plays must be specific to this business — not generic strategies that could apply to anyone.
- If the source materials describe growth ambitions without clear scope, note this as a gap.

This section MUST end with a "Strategic Implications" subsection — 3–5 bullets only, max 15 words each. Cover: which plays to sequence first and why, key conditions that must hold, and resource allocation implications. Do NOT use Lean/Protect/Fix/Deprioritise framing.

Return a JSON object:
{{
  "content": "<HTML content with Ansoff Matrix table, growth plays table, and strategic direction>",
  "strategic_implications": "<HTML with 3–5 bullet points covering growth play sequencing and conditions. No prose paragraphs.>"
}}
