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
LENGTH TARGET: 280 words maximum for the entire section. Tables count towards the target — keep rows tight.
Draft the following subsections using ONLY content from the provided source materials:

1. Target Audience Analysis
   - Primary and secondary customer segments
   - Who they are, what they value, and what problem they are solving by choosing this business
   - Present as a structured table:
     | Segment | Profile | Core Need | Value Driver | Revenue Importance |

2. Buying Behaviour and Purchase Journey
   - How customers discover, evaluate, and commit to this business
   - Key decision-making factors (price, trust, convenience, relationship, quality)
   - Any notable shifts in buying behaviour relevant to the planning horizon

3. Customer Retention and Loyalty Drivers
   - What keeps customers returning
   - Net Promoter context or satisfaction signals (if available in source materials)
   - Key risks to customer retention over the planning period

4. Customer Concentration Risk
   - Is revenue concentrated in a small number of customers?
   - What is the dependency risk if any major customer or segment is lost?
   - Mitigation approach (if articulated in source materials)

IMPORTANT RULES:
- Only use data and observations explicitly stated in source materials
- If customer data is sparse, note the gap clearly and recommend what data the business should collect
- Avoid generic marketing language — every observation must be grounded in this specific business

Return a JSON object:
{{
  "content": "<HTML content covering all four subsections>",
  "strategic_implications": null
}}
