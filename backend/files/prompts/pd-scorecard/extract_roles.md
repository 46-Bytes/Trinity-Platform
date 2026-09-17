# Step: Identify the roles in the matrix

Read the supplied Roles & Responsibilities matrix and return the matrix rows plus the
distinct roles it contains.

## What to return

1. `matrix_rows` — every row of the matrix, normalised to the ten columns.
2. `roles` — one entry per distinct person/role in the matrix, in the order they appear.

## Rules for matrix rows

- One responsibility per row, exactly as the matrix states it. Do not rewrite the wording
  at this stage — that happens when the PD is generated.
- `name` is set only on the first row of that person's block, blank on their other rows.
  This mirrors how the matrix itself is laid out.
- `retain`, `gain` and `lose` are `"Y"` or `null`. No other value is valid.
- Where the source is silent, use `null`. Never write "N/A", "TBC", "-" or an empty string.

## Rules for roles

- `role_title` is the job title, not the person's name. Where the matrix gives only a
  name, derive the title from the responsibilities and any reference PDs, and say so by
  keeping the person's name in `person_name`.
- `person_name` is the individual currently in the role, where the matrix names one.
- Blank rows and spacer rows in the matrix are not roles. Skip them.

## Output format

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
  ],
  "roles": [
    { "role_title": "Director", "person_name": "Scott" },
    { "role_title": "Operations Manager", "person_name": "Mary" }
  ]
}
```
