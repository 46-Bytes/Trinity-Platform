# Step: Generate the Half-Yearly Role Scorecard

Produce the scorecard content for the single role named in the request. It must line up
with that role's approved Position Description — same responsibilities, same language,
same transition items.

You return content only. The rating columns, comment columns, dropdowns and summary block
are added by the exporter, so do not attempt to produce them.

## Sections

### Role Purpose

One paragraph. Reuse the PD's position purpose, condensed if it runs long.

### Responsibilities & Outcomes

One entry per focus area, each with three fields:

- `focus_area` — the theme, matching the PD's key responsibility themes.
- `core_accountability` — what the role is accountable for in that area, one sentence.
- `performance_indicators` — the observable outcomes that show it is being done well.

Aim for five to seven entries. Collapse the PD's bullets up a level: a theme with four
bullets becomes one focus area with a single core accountability, not four rows.

### Behaviour & Leadership Expectations

One entry per behaviour:

- `behavioural_focus` — the behaviour, two or three words, e.g. "Integrity & Accountability".
- `expected_demonstration` — how it shows up in practice, one sentence.

Aim for four to six entries, drawn from the PD's behavioural expectations.

### Transition Milestones

Only where the PD has a transition focus. One entry per milestone:

- `milestone` — the shift being made, stated as a completed outcome.
- `target_date` — the stated timing where the matrix gives one, otherwise a sensible point
  in the supplied financial year range, e.g. "FY25 H2", "FY26 H1", "FY27".

Where the PD has no transition focus, return an empty list and the section is omitted.

## Output format

```json
{
  "scorecard_content": {
    "role_purpose": "The General Manager provides day-to-day leadership and operational management across the business, ensuring projects, systems and teams run efficiently and profitably.",
    "responsibilities": [
      {
        "focus_area": "Operational Leadership",
        "core_accountability": "Oversee daily business operations, scheduling and delivery performance across all divisions.",
        "performance_indicators": "Consistent delivery performance, reduced rework, clear team alignment and accountability."
      },
      {
        "focus_area": "Financial & Commercial Management",
        "core_accountability": "Oversee operational budgets, supplier performance and commercial decision-making.",
        "performance_indicators": "Improved job profitability, accurate reporting and controlled costs."
      }
    ],
    "behaviours": [
      {
        "behavioural_focus": "Integrity & Accountability",
        "expected_demonstration": "Leads transparently and takes ownership for results."
      },
      {
        "behavioural_focus": "Team Empowerment",
        "expected_demonstration": "Builds trust, delegates effectively and empowers team leaders."
      }
    ],
    "milestones": [
      {
        "milestone": "Build an empowered supervisor layer responsible for daily delivery.",
        "target_date": "FY25 H2"
      },
      {
        "milestone": "Delegate administrative duties and strengthen office leadership.",
        "target_date": "FY26 H1"
      }
    ]
  }
}
```

## Guidelines

- Every field is a string. Where something is genuinely unknown, use `null` rather than
  "N/A", "TBC" or an empty string.
- Keep `core_accountability` and `performance_indicators` to one sentence each — they sit
  in spreadsheet cells.
- `milestones` is `[]` when the role has no transition items.
- British English spelling throughout.
