# Step: Generate the Position Description

Produce a Position Description for the single role named in the request, using only that
role's rows from the matrix.

## Structure

Every PD has these sections, in this order:

1. **Position Purpose** — two to four sentences. What the role exists to do, how it fits
   the business, and where it is heading. Written as prose, not bullets.
2. **Key Responsibilities** — grouped into themes, each theme holding its own bullets.
3. **Decision-Making Authority** — what this role decides, what it delegates, and what it
   escalates.
4. **Key Relationships** — reporting line, direct reports, and external relationships.
5. **KPIs** — how performance is measured.
6. **Behavioural Expectations** — how the role is expected to operate.
7. **Transition Focus** — only where the role has `lose` rows or stated handover actions.

## Themes for key responsibilities

Choose the themes that fit the role's actual responsibilities. Do not use a theme you
have nothing to put under, and do not force every role into the same set:

- Strategic Leadership
- Operational Leadership
- People & Team Leadership
- Financial & Commercial Management
- Systems & Process Optimisation
- Client & Stakeholder Relationships
- Culture & Communication
- Governance & Compliance

## Building each section from the matrix

- **Key Responsibilities** come from `retain` and `gain` rows only. Rewrite each as an
  outcome-focused responsibility and group it under the theme it belongs to. A `gain` row
  is stated as a present responsibility, not as something the role will one day pick up.
- **Transition Focus** comes from `lose` rows and their `action`, `resp` and `when`
  values. State each as the shift being made, e.g. "Delegate invoicing and reconciliation
  to the Operations Manager." Where no `lose` rows exist, return an empty list and the
  section is omitted from the document.
- **Decision-Making Authority**, **Key Relationships**, **KPIs** and **Behavioural
  Expectations** are inferred from the seniority and content of the responsibilities, and
  from the reference PDs where supplied. Keep them grounded — a KPI must relate to
  something the role is actually responsible for.

## Output format

```json
{
  "pd_content": {
    "position_purpose": "The General Manager provides day-to-day leadership and operational management across the business, ensuring projects, systems and teams run efficiently and profitably.",
    "key_responsibilities": [
      {
        "theme": "Operational Leadership",
        "responsibilities": [
          "Oversee daily business operations, scheduling and delivery performance across all divisions.",
          "Ensure supervisors maintain clear accountability for job management and quality outcomes."
        ]
      },
      {
        "theme": "Financial & Commercial Management",
        "responsibilities": [
          "Oversee operational budgets, supplier performance and commercial decision-making."
        ]
      }
    ],
    "decision_making_authority": [
      "Authorised to approve operational spending within agreed limits.",
      "Escalates strategic or financial decisions beyond scope to the CEO/Director."
    ],
    "key_relationships": [
      "Reports to: CEO / Director",
      "Direct Reports: Supervisors, Office Administration",
      "External: Builders, suppliers, subcontractors"
    ],
    "kpis": [
      "On-time, on-budget project completion and client satisfaction.",
      "Reduction in rework, operational delays and administrative bottlenecks."
    ],
    "behavioural_expectations": [
      "Lead with integrity, consistency and accountability.",
      "Communicate clearly, respectfully and decisively under pressure."
    ],
    "transition_focus": [
      "Build an empowered supervisor layer responsible for day-to-day delivery.",
      "Finalise the delegation of administrative duties to appropriate roles."
    ]
  }
}
```

## Guidelines

- Each bullet is a complete sentence ending in a full stop.
- Two to six bullets per theme. Three to six themes for a senior role, fewer for a junior one.
- `transition_focus` is `[]` when the role has no transition items. Never invent one.
- British English spelling throughout.
