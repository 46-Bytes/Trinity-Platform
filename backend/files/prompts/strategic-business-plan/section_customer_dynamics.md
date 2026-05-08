Draft the Customer Dynamics section of the Strategic Business Plan for {client_name} ({industry}).

This section examines who the business serves, how customers buy, and what drives loyalty and churn. It must move beyond demographics into the behavioural and relational dynamics that shape revenue.

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
LENGTH TARGET: 180 words maximum for the entire section including tables.
Draft the following subsections using ONLY content from the provided source materials:

1. Target Audience
   - Primary and secondary customer segments — maximum 3 rows:
     | Segment | Core Need | Value Driver |
   - Do not add profile columns or revenue importance unless directly evidenced.

2. Buying Behaviour
   - 2–3 sentences only: how customers discover, evaluate, and commit to this business.
   - State one key decision-making factor and any notable shift relevant to the planning horizon.

3. Retention and Concentration
   - 3–4 bullets only: what keeps customers returning, key retention risks, and (if applicable) concentration risk with mitigation.
   - Fold Customer Concentration Risk into this subsection — do not create a separate subsection.

IMPORTANT RULES:
- Only use data and observations explicitly stated in source materials
- If customer data is sparse, note the gap clearly
- Avoid generic marketing language — every observation must be grounded in this specific business

Return a JSON object:
{{
  "content": "<HTML content covering all four subsections>",
  "strategic_implications": null
}}
