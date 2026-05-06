Draft the Operational Strategy and Key Recommendations section of the Strategic Business Plan for {client_name} ({industry}).

This section defines how the business must operate to deliver its strategy efficiently, consistently, and at scale. It should identify operational moats worth protecting and the most critical process improvements required over the planning horizon.

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
LENGTH TARGET: 280 words maximum excluding the initiatives table. Each prose subsection is 2–3 sentences only.
Draft the following subsections using ONLY content from the provided source materials:

1. Current Operational Position
   - How the business currently delivers its products/services
   - Key processes, systems, and operational strengths
   - Capacity constraints or bottlenecks identified in diagnostics

2. Operational Moats and Flywheels
   - Which operational capabilities give this business a durable advantage?
   - What would take a competitor years to replicate?
   - What operational habits or systems reinforce growth rather than constrain it?

3. Target Operating Model
   - What does the business need to look like operationally at the end of the planning horizon?
   - Key changes to structure, process, or systems required to support strategic growth

4. Key Operational Initiatives
   Present as a table:
   | Initiative | Purpose | Owner | Timeline | Link to Strategic Priority |

   Cover efficiency improvements, technology investments, process redesign, supply chain optimisation (only where supported by source materials).

5. Technology and Systems
   - Current technology stack and any material gaps
   - Digital transformation or automation priorities
   - Only if relevant and evidenced in source materials

IMPORTANT RULES:
- Link every initiative back to a specific strategic priority or growth play from approved sections
- Apply the owner dependency nuance rule — distinguish operational capacity from concentration of strategic authority
- Language must reflect capability being strengthened, not weakness being corrected

Return a JSON object:
{{
  "content": "<HTML content with all subsections including the initiatives table>",
  "strategic_implications": null
}}
