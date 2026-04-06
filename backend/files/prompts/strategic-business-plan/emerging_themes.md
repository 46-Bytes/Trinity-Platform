Based on the approved diagnostic sections for {client_name} ({industry}), surface emerging strategic themes.

CROSS-ANALYSIS RESULTS:
{cross_analysis}

APPROVED SECTIONS SO FAR:
{approved_sections}

TASK:
After the core diagnostic sections (PESTLE, SWOT, Resources & Capabilities, Customer Dynamics), consolidate emerging strategic themes:

1. Surface which implications are repeating across frameworks
2. Identify which signals appear strongest and weakest
3. State which themes should govern the remaining sections
4. Prevent duplication in later sections by clearly defining the governing themes now

Return a JSON object:
{{
  "themes": [
    {{
      "theme": "Theme name",
      "description": "What this theme means for the strategy",
      "supporting_sections": ["section_key_1", "section_key_2"],
      "signal_strength": "very_strong|strong|moderate"
    }}
  ],
  "summary": "Plain language summary explaining what these integrated themes mean for the business and which are non-negotiable versus optional"
}}
