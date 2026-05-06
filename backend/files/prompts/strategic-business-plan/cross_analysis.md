Perform a cross-pattern analysis across all provided materials for {client_name} ({industry}, {planning_horizon} horizon).

CONTEXT:
- Target audience: {target_audience}
- Additional context: {additional_context}

UPLOADED MATERIALS:
{file_references}

DIAGNOSTIC CONTEXT:
{diagnostic_context}

ADVISOR INSTRUCTIONS: {custom_instructions}

TASK:
Identify the most important patterns across all documents. Be concise — each value is a short phrase, not a sentence.

Return ONLY a JSON object:
{{
  "recurring_themes": [
    {{
      "theme": "Short theme label (5–8 words max)",
      "signal_strength": "very_strong|strong|moderate"
    }}
  ],
  "tensions": [
    {{
      "tension": "Short contradiction label (5–8 words max)"
    }}
  ],
  "correlations": [
    {{
      "correlation": "Short linkage label (5–8 words max)"
    }}
  ],
  "data_gaps": ["Short gap label"],
  "preliminary_observations": ["One crisp strategic observation per item"]
}}

Rules:
- Max 5 items per section. Omit sections with nothing significant.
- No descriptions, no sources, no elaboration — labels only.
- Plain text only, no markdown or HTML inside strings.
