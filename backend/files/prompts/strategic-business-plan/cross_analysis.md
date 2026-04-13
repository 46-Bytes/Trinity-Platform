Perform a comprehensive cross-pattern analysis across all provided materials for {client_name} operating in the {industry} sector.

CONTEXT:
- Planning horizon: {planning_horizon}
- Target audience: {target_audience}
- Additional context: {additional_context}

UPLOADED MATERIALS:
{file_references}

DIAGNOSTIC CONTEXT:
{diagnostic_context}

ADVISOR INSTRUCTIONS: {custom_instructions}

TASK:
Review all provided inputs in full and perform a cross-pattern analysis, identifying:
1. Recurring themes and priorities across all documents
2. Repeated constraints or bottlenecks
3. Correlations between issues (e.g. people → operations → margin)
4. Tensions or contradictions (e.g. ambition vs capacity)
5. Frequency of issues appearing across multiple documents
6. Relationships between internal factors and external pressures
7. Data gaps — information that appears missing or unclear

Return a JSON object with the following structure:
{{
  "recurring_themes": [
    {{
      "theme": "Theme name",
      "description": "Clear description of the theme",
      "sources": ["Strategy Workbook", "Diagnostic Report"],
      "signal_strength": "very_strong|strong|moderate"
    }}
  ],
  "tensions": [
    {{
      "tension": "Brief title",
      "description": "Description of the contradiction or tension"
    }}
  ],
  "correlations": [
    {{
      "correlation": "Brief title",
      "description": "How these issues are linked"
    }}
  ],
  "data_gaps": ["Description of missing information"],
  "preliminary_observations": ["Strategic observation based on the synthesis"]
}}

All string values must be plain text only — do not use HTML tags, markdown, or any special formatting inside JSON strings.

Treat these findings as strategic signals, not commentary. Focus on what will be most useful for building a coherent, integrated Strategic Business Plan.
