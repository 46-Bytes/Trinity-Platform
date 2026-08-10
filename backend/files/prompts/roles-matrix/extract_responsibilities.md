# Step: Extract Responsibilities

## Your Task

Read the uploaded documents and the advisor's pasted notes, and extract the
responsibilities belonging to each person in the confirmed roles list.

## Instructions

1. Work through every uploaded document and the pasted notes.
2. Attribute each responsibility to the person it belongs to, matching against the staff
   list supplied by the advisor.
3. Split combined statements into one responsibility per entry — "invoicing and
   reconciliation" becomes two entries.
4. Capture the stated time commitment verbatim where one is given (e.g. "1hr per week").
   Leave it null when no time is stated.
5. Capture any stated action, responsible person, timing, or retain/gain/lose intent.
   Leave each null when the source is silent.
6. Record where each responsibility came from in `source`, e.g. the filename or
   "advisor notes".
7. Do not invent responsibilities. Do not merge people. Do not include anyone outside the
   confirmed roles list.

## Output Format

Return a JSON object with this structure:

```json
{
  "people": [
    {
      "name": "Scott",
      "role_title": "Director",
      "responsibilities": [
        {
          "description": "Client delivery",
          "time": null,
          "priority": null,
          "retain": true,
          "gain": false,
          "lose": false,
          "action": null,
          "resp": null,
          "when": null,
          "source": "Scott_PD.pdf"
        },
        {
          "description": "Invoicing",
          "time": "1hr per week",
          "priority": null,
          "retain": false,
          "gain": false,
          "lose": true,
          "action": "Transfer to Mary",
          "resp": null,
          "when": null,
          "source": "advisor notes"
        }
      ]
    }
  ],
  "unmatched_notes": [
    "Any responsibility that could not be attributed to a named person"
  ]
}
```

## Guidelines

- `retain`, `gain` and `lose` are booleans. Set one to `true` only where the source
  explicitly says the person keeps, takes on, or hands over that responsibility.
  When the source is silent, all three are `false`.
- `time`, `priority`, `action`, `resp` and `when` are strings or `null`. Never estimate.
- Preserve the advisor's own wording where it is already concise.
- British English spelling throughout.
