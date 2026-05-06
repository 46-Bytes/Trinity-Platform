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
LENGTH TARGET: 280 words maximum for the entire section.
Draft the following subsections using ONLY content from the provided source materials:

1. Key Tangible Resources
   - Physical assets, equipment, facilities, technology infrastructure
   - Financial position and capital available for investment
   - Only include what is confirmed in source materials

2. Key Intangible Resources
   - Brand reputation, customer relationships, supplier relationships
   - Intellectual property, proprietary processes, data assets
   - Licences, accreditations, or regulatory approvals

3. Core Capabilities
   - What this business is distinctively good at
   - Operational capabilities that competitors would find hard to replicate
   - Leadership and management capability

4. Capability Gaps
   - Where current capability falls short of what the strategy requires
   - Ranked by strategic criticality (high / medium / low)
   - Present as a concise table:
     | Capability Gap | Strategic Impact | Priority | Mitigation / Build Path |

IMPORTANT RULES:
- Use bullet lists for resources and capabilities (not tables)
- Only use a table for the capability gaps assessment
- Be specific — avoid generic statements that could apply to any business
- If data is insufficient, insert "[REQUIRES CONFIRMATION — confirm with client]"

Return a JSON object:
{{
  "content": "<HTML content covering all four subsections>",
  "strategic_implications": null
}}
