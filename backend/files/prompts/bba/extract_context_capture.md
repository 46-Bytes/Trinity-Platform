# Extract Context Capture Fields from Diagnostic Report

## Your Task

You are given the text of a diagnostic report (business health assessment). Extract any information that maps to the following context-capture form fields. Return a JSON object with **only** the keys for which you found a clear value. Omit any key you cannot fill from the document.

## Output Rules

- Return **valid JSON only** (no markdown, no explanation).
- Use **camelCase** for all keys.
- For `companySize`, use exactly one of: `startup`, `small`, `medium`, `large`, `enterprise`. If the report implies size but uses different words, map to the nearest option.
- For `excludeSaleReadiness`, use boolean `true` or `false` only if the report clearly states sale-readiness should be excluded; otherwise omit.
- If a field is not found or ambiguous, **omit that key** from the JSON.
- Do not invent or assume values; only extract what is stated or clearly implied in the text.

## JSON Keys (use these exact names when present)

- `clientName` (string): Client or business name
- `industry` (string): Industry sector
- `companySize` (string): One of startup, small, medium, large, enterprise
- `locations` (string): Geographic or office locations
- `exclusions` (string, optional): Areas or topics to exclude from analysis
- `constraints` (string, optional): Constraints or limitations
- `preferredRanking` (string, optional): How findings should be ranked
- `strategicPriorities` (string): Strategic priorities for the next 12 months
- `excludeSaleReadiness` (boolean, optional): Whether to exclude sale-readiness from analysis
