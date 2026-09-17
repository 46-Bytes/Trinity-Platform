# Step: Build the Matrix

## Your Task

Turn the extracted responsibilities into matrix rows matching the "Job Roles" tab layout.

## Instructions

1. Produce one row per responsibility.
2. Group rows by person, in the order the advisor listed the confirmed roles.
3. Set `name` on the first row of each person's block only. Every other row for that
   person has `name` as `null`.
4. Copy `description` into `role_description` unchanged unless it needs tightening.
5. Copy `time`, `priorities`, `action`, `resp` and `when` straight through. Where the
   extraction has `null`, the matrix cell is `null`.
6. Convert the booleans to flags: `retain: true` becomes `"Y"`, otherwise `null`. Same for
   `gain` and `lose`. A row may carry more than one flag if the source supports it.
7. Do not add rows for responsibilities that were not extracted, and do not drop any that
   were.

## Output Format

Return a JSON object with this structure:

```json
{
  "matrix_rows": [
    {
      "name": "Scott",
      "role_description": "Client delivery",
      "time": null,
      "priorities": null,
      "retain": "Y",
      "gain": null,
      "lose": null,
      "action": null,
      "resp": null,
      "when": null
    },
    {
      "name": null,
      "role_description": "Invoicing",
      "time": "1hr per week",
      "priorities": null,
      "retain": null,
      "gain": null,
      "lose": "Y",
      "action": "Transfer to Mary",
      "resp": null,
      "when": null
    }
  ]
}
```

## Guidelines

- Every field is either a string or `null`. Never write "N/A", "TBC", "-" or an empty
  string — use `null`.
- `retain`, `gain` and `lose` are either `"Y"` or `null`. No other value is valid.
- Keep `role_description` short enough to read in a spreadsheet cell.
- British English spelling throughout.
