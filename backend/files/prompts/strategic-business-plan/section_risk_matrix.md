Draft the Risk Matrix and Mitigation section of the Strategic Business Plan for {client_name} ({industry}).

This section identifies the key risks to successful strategy execution and provides practical mitigation strategies. It must be grounded in the realities of this specific business, not generic risk categories.

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

1. Risk Assessment Matrix
   Identify 8-12 risks drawn from:
   - Threats identified in the SWOT analysis
   - External pressures from PESTLE
   - Capacity constraints from the resources assessment
   - Financial risks
   - Implementation risks from the roadmap

   Present as a table:
   | Risk | Category | Likelihood (H/M/L) | Impact (H/M/L) | Risk Rating | Mitigation Strategy | Owner |

   Risk Rating = Likelihood x Impact (High-High = Critical, High-Medium = High, etc.)

2. Top 3-5 Critical Risks
   For each critical risk, provide:
   - Detailed description of the risk scenario
   - Early warning indicators
   - Mitigation actions (preventive and reactive)
   - Contingency plan if the risk materialises

3. Risk Monitoring
   How should risks be monitored? Suggest:
   - Review frequency
   - Who is responsible for risk oversight
   - Escalation triggers

CRITICAL RULES:
- Risks must be specific to this business and this strategy — not generic industry risks.
- Link each risk back to a specific section of the plan (e.g. "Risk to Growth Play 2" or "Risk from PESTLE: regulatory change").
- Mitigation strategies must be practical and actionable, not theoretical.
- Use the table format for the risk matrix.

Return a JSON object:
{{
  "content": "<HTML content with risk matrix table and critical risk detail>",
  "strategic_implications": null
}}
