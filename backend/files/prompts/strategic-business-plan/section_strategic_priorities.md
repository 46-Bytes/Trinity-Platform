Draft the Strategic Priorities and Key Initiatives section of the Strategic Business Plan for {client_name} ({industry}).

This section distils everything into a ranked set of priorities. It must explain not just WHAT the priorities are, but WHY they are ranked this way — linking back to the diagnostic signals and cross-analysis.

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

1. Strategic Priorities (Ranked)
   Present 5-8 strategic priorities in order of importance.
   For each priority:
   - Priority name
   - Why it ranks where it does (link to cross-analysis signals, diagnostic findings)
   - What success looks like
   - Key risk if this priority is neglected

   Present as a table:
   | Rank | Priority | Rationale | Success Measure | Risk if Neglected |

2. Key Initiatives
   For each priority, list 2-4 key initiatives that will drive it forward.
   Present as a table:
   | Priority | Initiative | Owner | Timing | Dependencies |

3. Prioritisation Logic
   A brief paragraph explaining the overall ranking methodology:
   - What criteria were used (impact, urgency, feasibility, strategic alignment)?
   - Which cross-analysis signals were most influential?
   - What trade-offs were made?

CRITICAL RULES:
- Priorities must be specific to this business, not generic strategic goals.
- The ranking must be justified by evidence from the source materials and earlier sections.
- If two priorities could be swapped, explain the judgment call.
- Do not duplicate content from earlier sections — reference and build forward.

Return a JSON object:
{{
  "content": "<HTML content with ranked priorities table and initiatives>",
  "strategic_implications": null
}}
