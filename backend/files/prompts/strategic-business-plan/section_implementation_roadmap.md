Draft the Implementation Roadmap section of the Strategic Business Plan for {client_name} ({industry}).

This section translates priorities and initiatives into a phased, time-bound plan with clear ownership and dependencies. It must feel actionable and realistic, not aspirational.

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

1. Phased Implementation Plan
   Break the planning horizon into phases (e.g. Phase 1: Months 1-6, Phase 2: Months 7-12, Phase 3: Year 2-3).
   For each phase:
   - Phase name and timeframe
   - Key objectives for this phase
   - Major initiatives and milestones
   - Dependencies (what must be complete before this phase begins)
   - Resource requirements

2. Implementation Timeline
   Present as a structured table:
   | Phase | Timeframe | Initiative | Milestone | Owner | Dependencies |

3. Quick Wins
   Identify 3-5 initiatives that can be started immediately and deliver visible results within 90 days.
   These build momentum and demonstrate progress.

4. Critical Path
   What are the 3-4 initiatives that, if delayed, would delay everything else?
   What are the key decision points?

CRITICAL RULES:
- Sequencing must be logical — do not schedule dependent initiatives in parallel.
- Ownership must be assigned to specific roles (not "the team" or "management").
- If the source materials do not specify timing, propose realistic timing based on the scope and mark as "[Proposed timing — confirm with client]".
- Default to table format for the timeline.

Return a JSON object:
{{
  "content": "<HTML content with phased roadmap and timeline table>",
  "strategic_implications": null
}}
