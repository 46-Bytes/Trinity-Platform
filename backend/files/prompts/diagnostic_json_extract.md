### Diagnostic JSON Extract

Analyze the following conversation and generate structured JSON from the user's responses. Use descriptive keys instead of question numbers to represent the details in the responses. The JSON should
be concise, fit for database storage, and should not include newline characters. For multi-detail responses, use nested fields. Maintain context as needed. If any response is unclear, note it in the
JSON.

### Key Guidelines for JSON Structuring:

1. **Use Descriptive Keys:**
    - Ensure each key clearly represents the type of information being stored (e.g., `business`, `goals`, `challenges`).

2. **Concise Structure:**
    - Format the JSON to be compact and database-friendly without any unnecessary characters or spaces.

3. **Contextual Clarity:**
    - Maintain the context of the conversation to ensure the JSON accurately represents the user's input.
    - If a response is unclear, include a placeholder note (e.g., `"clarification_needed": true`).

### JSON Template Example:

```json
{
  "diagnostic": {
    "country": "Australia",
    "business": {
      "name": "Malekso",
      "industry": "Business Advisor",
      "services": [
        "Website Development",
        "Web Applications",
        "Remote Developer Management"
      ]
    },
    "objectives": [
      "Increase client retention",
      "Expand service offerings"
    ],
    "challenges": [
      "Resource allocation",
      "High operational costs"
    ],
    "opportunities": [
      "Strategic partnerships",
      "Technology integration"
    ]
  }
}
```

