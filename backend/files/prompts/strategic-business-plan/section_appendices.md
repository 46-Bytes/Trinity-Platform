Draft the Appendices section of the Strategic Business Plan for {client_name} ({industry}).

This is an optional section for supporting material that adds depth without cluttering the main plan.

CONTEXT:
- Planning horizon: {planning_horizon}
- Target audience: {target_audience}
- Additional context: {additional_context}

PREVIOUSLY APPROVED SECTIONS: {approved_sections}
UPLOADED FILES: {file_references}
DIAGNOSTIC CONTEXT: {diagnostic_context}
CUSTOM INSTRUCTIONS: {custom_instructions}

CROSS-ANALYSIS: {cross_analysis}
ADVISOR NOTES: {advisor_notes}
EMERGING THEMES: {emerging_themes}

TASK:
Include appendices ONLY if the source materials contain supporting data that is too detailed for the main plan body but adds value for reference. Possible appendices:

- Detailed financial projections or models
- Full PESTLE or SWOT worksheets
- Organisational charts
- Market research data
- Glossary of terms

If the source materials do not warrant any appendices, return a brief note stating that no appendices are required for this plan.

Keep each appendix clearly labelled (Appendix A, B, C, etc.) with a descriptive title.

Return a JSON object:
{{
  "content": "<HTML content with labelled appendices, or a note that none are required>",
  "strategic_implications": null
}}
