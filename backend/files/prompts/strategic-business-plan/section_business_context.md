Draft the Business and Context Overview section of the Strategic Business Plan for {client_name} ({industry}).

This section provides the factual foundation — who the business is, where it sits, and what context the strategy operates within. It must ground the reader before the diagnostic sections begin.

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
Draft the following subsections using ONLY content from the provided source materials:

1. Business Overview
   - What the business does, its core products/services
   - Ownership structure and legal form
   - Year established, key milestones
   - Number of employees, locations

2. Current Market Position
   - Where the business sits in its market/industry
   - Market share (if known), competitive positioning
   - Key customer segments served

3. Recent Performance Summary
   - High-level financial or operational performance indicators
   - Recent trends (growth, stagnation, decline)
   - Only include numbers explicitly stated in source materials

4. Key Stakeholders
   - Owners, directors, management team
   - Key external relationships (suppliers, partners, advisors)
   - Only include what is stated in the materials

Keep this section factual and concise. This is context-setting, not analysis — the analysis comes in the next section.

Do NOT invent any financial figures, employee counts, or historical facts. If information is not in the source materials, omit the subsection or mark as "[Data not provided — confirm with client]".

Return a JSON object:
{{
  "content": "<HTML content covering the business context>",
  "strategic_implications": null
}}
