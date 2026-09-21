/**
 * Sale Ready program guide content, from the client's Sale Ready mockup.
 * Frontend constants for now; to become admin-editable content later.
 * Keyed by backend stage_code (files/sale_ready/stages.json).
 */

export interface StageGuide {
  purpose: string;
  steps: string[];
  watch: string[];
  templates: string[];
}

export const STAGE_GUIDES: Record<string, StageGuide> = {
  DIAG: {
    purpose: 'Get the diagnostic completed and the report generated so prioritisation has something to work from.',
    steps: [
      'Client completes the Trinity diagnostic. Offer a working session if they stall.',
      'File every uploaded document in the client folder.',
      'Submit the diagnostic and confirm the report generated.',
      'Read the report and note anything to verify at appraisal or in the workshop.',
    ],
    watch: ['An unsure answer is a finding, not a gap. List them for direct verification.'],
    templates: [],
  },
  APPRAISAL: {
    purpose:
      'Establish the price range and the sale structure options. This anchors prioritisation and the planning workshop.',
    steps: [
      'Review everything collected and list what is missing for the appraisal.',
      'Chase missing items with the client, accountant or lawyer.',
      'Identify and document add-backs in the Addback Tracker.',
      'Complete the analysis to set the price range.',
      'Work DD category 1, Type & Structure of Sale, before the report goes out.',
      'Send to the appraisal report team for report generation, then review the report with sale structure front of mind.',
    ],
    watch: [
      'If the appraisal needs to be outsourced, clear it with the practice principal first.',
      'Sale structure must be addressed in the report, not left for later.',
    ],
    templates: ['Addback Tracker', 'Normalised EBITDA template', 'Normalised balance sheet template'],
  },
  PRIORITISE: {
    purpose: 'Turn the diagnostic, the appraisal and your own judgement into an agreed module order and a roadmap.',
    steps: [
      'Trinity proposes the order from the diagnostic engine. Compare it against the appraisal and what you know.',
      'Adjust the order on the roadmap. Two or more modules can run at once.',
      'Open each module and add client-specific tasks before the workshop.',
      'Mark this phase complete when the roadmap is ready to present.',
    ],
    watch: ['Due Diligence Preparation always runs last. It is pinned on the roadmap.'],
    templates: [],
  },
  WORKSHOP: {
    purpose:
      'Walk the client through the findings and agree the plan, the sale structure direction, and who else needs to be involved.',
    steps: [
      'Book the session and share an agenda.',
      'Cover the minimum: Trinity report, appraisal, type and structure of sale, best value proposition, prioritisation and roadmap, when to tell staff.',
      'Get approval to contact the accountant and lawyer. Introduce them if needed.',
      'Update the prioritisation and roadmap with what changed in the room.',
      'Start the first module.',
    ],
    watch: ['The client owns the decision on when to tell staff. Record it, do not make it.'],
    templates: [],
  },
  M1: {
    purpose:
      'Produce clean, reconciled, normalised financials a buyer can rely on. Everything else in the program is easier once this is done.',
    steps: [
      'Get Xero access, or exported reports if you must.',
      'Review three years of P&L and balance sheet for inconsistencies. Work with the accountant to clean key accounts.',
      'Refresh the add-backs and build the normalised EBITDA view.',
      'Confirm BAS and tax lodgements are current, and separate personal from business expenses.',
      'Approve add-backs with the client and finalise three years plus YTD.',
      'File everything and work the financial DD items.',
    ],
    watch: [
      'Add-backs were done at appraisal. Redo them if that was months ago.',
      'QA is required on every must-do task before the module is marked complete.',
    ],
    templates: [
      'Addback Tracker',
      'Normalised EBITDA template',
      'Normalised balance sheet template',
      'Accountant Briefing Template',
      'Bookkeeper Briefing Template',
    ],
  },
  M2: {
    purpose:
      'Confirm the business is legally clean and transferable: structure, registrations, contracts, leases, insurance and assets.',
    steps: [
      'Collect structure documents and verify against ASIC.',
      'Confirm registrations are valid and current.',
      'Review every supplier, customer and contractor contract. Flag missing, expired or non-transferable ones.',
      'Review the lease: term, rent review, assignment, expiry. Document upcoming negotiations.',
      'Confirm insurance and produce the legal risk summary.',
      'Work the DD items. This module carries the largest share of the checklist.',
    ],
    watch: ['You are recording and referring, not giving legal advice. Anything material goes to the lawyer.'],
    templates: ['ASIC and Licence Checklist', 'Legal Document Checklist', 'Lease Summary Sheet', 'Risk Register Template'],
  },
  M3: {
    purpose:
      'Document how the business runs and how much of it sits with the owner. Owner dependency is mapped and disclosed, and reduced where the advisor and client agree it is worth doing before sale.',
    steps: [
      'Build or refresh the org chart.',
      'Run the owner role-mapping session and list every responsibility.',
      'Create the delegation roadmap. This is the input to the People module.',
      'Collect and verify SOPs. Document the missing critical ones.',
      'Record key person and operational risks with their mitigation. Decide with the client which to fix before sale and log the rest as gaps.',
    ],
    watch: ['Do not run the team role-mapping session in People until the delegation roadmap exists.'],
    templates: ['Owner Dependency Scorecard', 'Risk Register Template', 'Digital Access Log Template'],
  },
  M4: {
    purpose:
      "Get employment records complete, compliant and documented, and record who does what once the owner steps out. Role changes are made where they help the sale and logged as gaps where they don't.",
    steps: [
      'Collect all employment and contractor agreements and file them in the DD folder.',
      'Check currency, validity and Fair Work compliance. Fix issues.',
      'Build the staff summary table and verify payroll, super and entitlements.',
      'Run the team role-mapping session using the delegation roadmap from Owner Dependency & Operations.',
      'Identify key staff, flight risks and gaps. Update job descriptions to match reality and log any role redesign as a gap for a decision.',
    ],
    watch: ['When to tell staff was decided in the workshop. Check it before any team session.'],
    templates: ['Employee Summary Table', 'HR Compliance Checklist', 'Contractor Register'],
  },
  M5: {
    purpose:
      'Evidence that revenue is real, contracted and likely to continue. Concentration and churn are disclosed as found, and addressed before sale only where it is worth the time.',
    steps: [
      'Get sales data by customer: 12 months and three years.',
      'Analyse concentration and confirm contracts exist for key customers. Formalise the top 5 to 10.',
      'Review forward orders and guaranteed commitments.',
      'Document the government versus private mix and the recurring versus one-off mix.',
      'Summarise risks and lines at risk, then work the contract and customer DD items.',
    ],
    watch: ['Verbal arrangements with key customers are the most common gap. Get them in writing.'],
    templates: [
      'Customer Revenue Summary Template',
      'Customer Risk Analysis Sheet',
      'Simple Client Agreement Template',
      'Client Testimonial Request Email',
    ],
  },
  M6: {
    purpose: 'Confirm the business owns what it says it owns: IP, domains, digital assets, brand and goodwill.',
    steps: [
      'Collect IP registrations. Verify domain ownership and renewals.',
      'Confirm business ownership of websites, emails and social accounts.',
      'Document licensing, royalties, confidentiality and non-compete agreements.',
      'Build the IP Register and summarise brand positioning and goodwill.',
    ],
    watch: ['Digital assets registered in a personal name are a transfer problem. Fix them now.'],
    templates: ['IP Register Template', 'Brand Asset Inventory Sheet', 'Digital Access Log Template'],
  },
  M7: {
    purpose: 'Confirm tax and regulatory compliance is current and documented, with nothing waiting to surprise a buyer.',
    steps: [
      'Collect tax returns, BAS, PAYG and payroll tax records.',
      'Identify ATO liabilities, payment plans, Division 7A loans and CGT implications.',
      'Review ASIC and PPSR, and industry-specific taxes and levies.',
      'Review regulator correspondence and document any investigations.',
      'Produce the compliance summary.',
    ],
    watch: ['Tax advice sits with the accountant. Record the position and refer.'],
    templates: ['ATO Tracker + ASIC Summary Sheet', 'Compliance Summary Report'],
  },
  M8: {
    purpose:
      'Test the data room before a buyer does. Every DD item current, indexed and clearly named, with an executive summary on top.',
    steps: [
      'Run the full DD checklist for completeness and currency.',
      'Update anything out of date, including items flagged for review at this module.',
      'Build the document index and confirm naming conventions.',
      'Run a mock due diligence session.',
      'Write the executive summary of strengths, opportunities and risks.',
      'Set the version control protocol for the data room.',
    ],
    watch: ['Pinned last. Starts when every other module is complete or explicitly parked.'],
    templates: ['Data Room Folder Template', 'Buyer Q&A Prep Sheet'],
  },
  TRANSITION: {
    purpose:
      'Plan what happens after the sale: key person risk, customer and supplier handover, post-sale contracts and transition management.',
    steps: [
      'Work through the five sub-items with the client.',
      'Confirm any earn-out, vendor finance or consultancy arrangement with the lawyer.',
      'Set the transition meeting cadence.',
    ],
    watch: [],
    templates: [],
  },
  SALE_PLANNER: {
    purpose:
      'Record the sale decisions: type, structure, best value proposition, marketing plan, and the issues to address before listing.',
    steps: [
      'Confirm type and structure with the client and the appraisal.',
      'Answer the marketing plan questions.',
      'Work the issues list and note where each is handled.',
    ],
    watch: [],
    templates: [],
  },
  CLOSEOUT: {
    purpose: 'Close the program: decide whether a fresh appraisal is needed, refer for listing, and agree ongoing assistance.',
    steps: [
      'Review the final position against the original appraisal.',
      'Refer to Benchmark Business Sales for listing.',
      'Agree what ongoing assistance looks like and close the engagement.',
    ],
    watch: [],
    templates: [],
  },
};

/** "Run with" hints shown beside each module. */
export const RUN_WITH: Record<string, string> = {
  M1: 'Feeds Tax, Compliance & Regulatory and the appraisal refresh.',
  M2: 'Shares DD categories with Tax, Compliance & Regulatory. Lease items flow to Sale Planner.',
  M3: 'The delegation roadmap is the input to People. Run this first.',
  M4: 'Needs the delegation roadmap from Owner Dependency & Operations.',
  M5: 'Contract items overlap with Legal, Compliance & Property.',
  M6: 'Digital access log is shared with Owner Dependency & Operations.',
  M7: 'Depends on clean financials from Financial Clarity & Reporting.',
  M8: 'Runs last. Reviews every flagged item across all modules.',
};

/** The program workflow, shown against the engagement. `stage` is a stage code, or 'modules'. */
export const WORKFLOW: { stage: string; label: string }[] = [
  { stage: 'DIAG', label: 'Trinity diagnostic completed and report generated' },
  { stage: 'APPRAISAL', label: 'Financial assessment, then appraisal conducted and report produced' },
  { stage: 'PRIORITISE', label: 'Advisor reviews everything, finalises prioritisation, builds the roadmap' },
  { stage: 'WORKSHOP', label: 'Client planning workshop' },
  { stage: 'modules', label: 'Program modules run in roadmap order, two or more at once where useful' },
  { stage: 'M8', label: 'Final module: Due Diligence Preparation' },
  { stage: 'TRANSITION', label: 'Transition and handover planning' },
  { stage: 'SALE_PLANNER', label: 'Sale Planner Checklist' },
  {
    stage: 'CLOSEOUT',
    label: 'Re-appraisal if needed, referral to Benchmark Business Sales, ongoing assistance, then close the program',
  },
];

export const PROGRAM_RULES: { title: string; body: string }[] = [
  {
    title: 'Scope',
    body: 'Sale Ready is a preparation program. It finds, verifies, documents and discloses what a buyer will ask for. Improvements can be done inside it, small or large, provided the client and the team stay clear that preparation to sell is the focus. A DD item marked No is a gap, and the advisor chooses the handling: fix in Sale Ready, disclose as is, or refer to Value Builder. Referred gaps sit on a list for the advisor; Trinity does not create Value Builder items from them.',
  },
  {
    title: 'Order',
    body: 'The four phases before the modules always run in sequence. Modules run in roadmap order and can overlap. Due Diligence Preparation is pinned last.',
  },
  {
    title: 'Proposed order',
    body: "The diagnostic engine proposes the module order once the diagnostic and appraisal are in. The advisor adjusts it in Prioritisation and again after the workshop. The reset button restores the engine's proposal.",
  },
  {
    title: 'Task creation',
    body: 'Phase tasks are created when the engagement is created. Module tasks are created when the advisor starts the module, so the Tasks list only ever carries live work.',
  },
  {
    title: 'Task groups',
    body: 'Every module has three groups: must-do (QA required), optional enhancements, and client-specific tasks added by the advisor or by AI. Only must-do tasks gate completion.',
  },
  {
    title: 'Status',
    body: 'Not started until the advisor starts the stage, or something is ticked. In progress from then. Complete only when the advisor marks it, and only when every must-do task is done.',
  },
  {
    title: 'Tasks and due diligence',
    body: 'Tasks are what the advisor and client do. Due diligence items are what a buyer will ask to see: the evidence. Tasks never complete DD items. A module cannot be marked complete while any of its DD items has no status, so nothing can be skipped by accident. One master DD checklist of 210 items across 16 categories, every item belonging to exactly one module or phase. Edit it in either place and it updates in both. Notes are advised for any status other than Yes.',
  },
  {
    title: 'Review at M8',
    body: 'Any DD item can be flagged for re-review at Due Diligence Preparation. Flagged items surface at the top of that module.',
  },
  {
    title: 'Documents and storage',
    body: "The files live in the data room in Files, one folder per DD category and sub-item, in Benchmark's Google Drive, not on Trinity's servers. Trinity indexes the files; a buyer never receives a Drive link.",
  },
  {
    title: 'Roles',
    body: 'The advisor runs the program. The owner sees the Roadmap (read-only, no opening stages), the Due diligence checklist and the Files tabs only. Admin edits the program guide, task templates and DD checklist for all future engagements.',
  },
  {
    title: 'Reference',
    body: 'Type of sale, structure and best value proposition are decided at appraisal, confirmed at the workshop, and recorded in the Sale Planner.',
  },
];

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
