export interface PlanSectionConfig {
  /** Key matching the backend sections JSONB array entry */
  key: string;
  /** Human-friendly display title */
  title: string;
  /** Whether the section is required for plan completion */
  required: boolean;
  /** Whether the section should end with a "Strategic Implications" subsection */
  hasDiagnosticImplications: boolean;
  /** Whether to surface emerging strategic themes after this section is approved */
  surfaceThemesAfter: boolean;
}

/**
 * Ordered list of Strategic Business Plan sections.
 * The array order IS the default drafting order.
 * required=false sections can be skipped without blocking plan completion.
 */
export const PLAN_SECTIONS: readonly PlanSectionConfig[] = [
  { key: 'executive_summary',          title: 'Executive Summary',                                    required: true,  hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'strategic_intent',           title: 'Strategic Intent Overview',                            required: true,  hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'business_context',           title: 'Business and Context Overview',                        required: true,  hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'external_internal_analysis', title: 'External and Internal Analysis',                       required: true,  hasDiagnosticImplications: true,  surfaceThemesAfter: true  },
  { key: 'key_resources_capabilities', title: 'Key Resources and Capabilities',                       required: false, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'customer_dynamics',          title: 'Customer Dynamics',                                    required: false, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'growth_opportunities',       title: 'Growth Opportunities and Strategic Direction',         required: true,  hasDiagnosticImplications: true,  surfaceThemesAfter: false },
  { key: 'operations_strategy',        title: 'Operational Strategy and Key Recommendations',         required: false, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'hr_strategy',                title: 'Human Resource Strategy and Key Recommendations',      required: false, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'marketing_sales_strategy',   title: 'Marketing and Sales Strategy',                        required: false, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'financial_overview',         title: 'Financial Overview',                                   required: true,  hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'risk_matrix',                title: 'Risk Matrix and Analysis',                             required: true,  hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'actions_next_steps',         title: 'Actions List (Implementation Plan)',                   required: true,  hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'strategic_alignment',        title: 'Integrated Strategic Implications and Alignment',      required: false, hasDiagnosticImplications: false, surfaceThemesAfter: false },
] as const;
