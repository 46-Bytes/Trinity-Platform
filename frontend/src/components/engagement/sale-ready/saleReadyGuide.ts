/**
 * Sale Ready option lists shared by the DD checklist views.
 * Guide content (stage guides, run-with, workflow, rules) comes from the
 * engagement's guide snapshot on the server; it is not duplicated here.
 */

export const DD_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'yes', label: 'Yes' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'no', label: 'No' },
  { value: 'not_applicable', label: 'N/A' },
];

export const GAP_OPTIONS: { value: string; label: string }[] = [
  { value: 'fix', label: 'Fix in Sale Ready' },
  { value: 'disclose', label: 'Disclose as is' },
  { value: 'refer', label: 'Refer to Value Builder' },
];
