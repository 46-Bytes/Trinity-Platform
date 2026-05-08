Draft the Key Resources and Capabilities section of the Strategic Business Plan for {client_name} ({industry}).

This section identifies the foundational assets and capabilities that enable the business to compete, serve customers, and execute its strategy. It must be honest and specific — not a generic inventory.

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
LENGTH TARGET: 180 words maximum for the entire section.
Draft the following subsections using ONLY content from the provided source materials:

1. Key Resources
   - Maximum 6 bullets total covering both tangible and intangible resources.
   - Tangible: physical assets, technology infrastructure, capital available for investment.
   - Intangible: brand reputation, customer relationships, IP, licences, accreditations.
   - Only include what is confirmed in source materials. Do not separate into two sub-lists.

2. Core Capabilities
   - 3–4 bullets: what this business is distinctively good at and what competitors would find hard to replicate.

3. Capability Gaps
   - Where current capability falls short of what the strategy requires.
   - Present as a table — maximum 4 rows:
     | Capability Gap | Impact | Priority | Action |

IMPORTANT RULES:
- Use bullet lists for resources and capabilities — not tables
- Only use a table for the capability gaps
- Be specific — avoid generic statements that could apply to any business
- If data is insufficient, insert "[REQUIRES CONFIRMATION — confirm with client]"

Return a JSON object:
{{
  "content": "<HTML content covering all four subsections>",
  "strategic_implications": null
}}
