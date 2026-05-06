Draft the Marketing and Sales Strategy section of the Strategic Business Plan for {client_name} ({industry}).

This section defines how the business will attract, convert, and retain its target customers over the planning horizon. It must connect directly to the Customer Dynamics and Growth Opportunities sections already approved.

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
LENGTH TARGET: 280 words maximum excluding the acquisition table. Each prose subsection is 2–3 sentences only — reference Customer Dynamics and Growth Opportunities, do not repeat them.
Draft the following subsections using ONLY content from the provided source materials:

1. Target Audience and Segmentation
   - Which customer segments will this strategy prioritise?
   - What is the rationale for prioritisation (revenue potential, strategic fit, ease of acquisition)?
   - Reference the Customer Dynamics section — do not repeat; build forward.

2. Brand Positioning and Messaging
   - How does the business want to be perceived in its market?
   - What is the core value proposition for each priority segment?
   - What is the brand promise — and is it differentiated?

3. Channel Strategy
   - How does the business currently reach customers? (direct, referral, digital, trade, etc.)
   - Which channels will be prioritised or expanded over the planning horizon?
   - Which channels should be deprioritised or exited?

4. Customer Acquisition Strategy
   - Key initiatives to attract new customers in priority segments
   - Present as a table:
     | Initiative | Target Segment | Channel | Owner | Timeline |

5. Customer Retention and Lifetime Value
   - How will the business deepen relationships with existing customers?
   - Loyalty, repeat purchase, or cross-sell strategies (only where evidenced in source materials)

IMPORTANT RULES:
- Every marketing initiative must link to a named growth play or strategic priority from earlier approved sections
- Do not invent campaign ideas or channel strategies not supported by source materials
- Use bullet lists for brand and positioning content — reserve tables for initiative plans

Return a JSON object:
{{
  "content": "<HTML content covering all five subsections>",
  "strategic_implications": null
}}
