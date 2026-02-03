# Step 6: 12-Month Recommendations Plan

## Your Task

Expand each finding into a practical recommendation using a structured format.
Also include the "Notes on the 12-Month Recommendations Plan" disclaimer.

## Recommendation Structure

For each finding, create a recommendation containing:

### Purpose
A concise explanation of the goal and outcome (1-2 sentences).

### Key Objectives
3-5 bullets describing what success looks like.

### Actions to Complete
5-10 short, specific steps that the client can follow.

### BBA Support Outline
Clarify what BBA will do - advisory, facilitation, mentoring, training.
Choose only what applies from:
- Co-authoring a strategic or operational plan (when relevant)
- Providing finance-related mentoring and training
- Delivering change-management or project-management guidance
- Offering 1:1 leadership mentoring or helping set up internal mentoring
- Training staff on developing and maintaining their own SOPs

### Expected Outcomes
4-6 measurable, positive outcomes.

## Output Format

Return a JSON object with this structure:

```json
{
  "plan_notes": "The timeframes outlined in this plan are indicative only. Actual durations may be shorter or longer depending on priorities, workload, and availability across both the client organisation and Benchmark Business Advisory (BBA). Timelines may also shift due to illness, public holidays, annual leave, or unforeseen events. Where changes occur, all parties will provide as much notice as possible. Some activities will run concurrently or evolve as ongoing support. This plan is based on the current business state and may be updated as priorities change. It should therefore be read as a living plan—flexible and responsive to real-world progress, not a fixed schedule.",
  "recommendations": [
    {
      "number": 1,
      "title": "Recommendation Title",
      "timing": "Month 1-3",
      "purpose": "Explanation of goal and outcome",
      "key_objectives": [
        "Objective 1",
        "Objective 2",
        "Objective 3"
      ],
      "actions": [
        "Action step 1",
        "Action step 2"
      ],
      "bba_support": "Description of BBA's role and support",
      "expected_outcomes": [
        "Outcome 1",
        "Outcome 2"
      ]
    }
  ],
  "timeline_summary": {
    "title": "Implementation Timeline",
    "rows": [
      {
        "rec_number": 1,
        "recommendation": "Brief title",
        "focus_area": "Category",
        "timing": "Month 1-3",
        "key_outcome": "Primary outcome"
      }
    ]
  }
}
```

## Guidelines

- Recommendations should follow the finding ranking order
- Timing should be realistic and consider dependencies
- BBA Support should enable client capability, not do the work for them
- Expected Outcomes should be measurable where possible
- Use British English spelling throughout
- Keep the timeline summary to one page
