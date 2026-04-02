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
 */
export const PLAN_SECTIONS: readonly PlanSectionConfig[] = [
  { key: 'executive_summary', title: 'Executive Summary', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'strategic_intent', title: 'Strategic Intent Overview', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'business_context', title: 'Business and Context Overview', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'external_internal_analysis', title: 'External and Internal Analysis', required: true, hasDiagnosticImplications: true, surfaceThemesAfter: true },
  { key: 'growth_opportunities', title: 'Growth Opportunities and Strategic Direction', required: true, hasDiagnosticImplications: true, surfaceThemesAfter: false },
  { key: 'functional_strategies', title: 'Functional and Thematic Strategies', required: true, hasDiagnosticImplications: true, surfaceThemesAfter: false },
  { key: 'financial_overview', title: 'Financial Overview', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'strategic_priorities', title: 'Strategic Priorities and Key Initiatives', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'implementation_roadmap', title: 'Implementation Roadmap', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'risk_matrix', title: 'Risk Matrix and Mitigation', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'actions_next_steps', title: 'Actions List and Next Steps', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'strategic_alignment', title: 'Integrated Strategic Implications & Alignment', required: true, hasDiagnosticImplications: false, surfaceThemesAfter: false },
  { key: 'appendices', title: 'Appendices', required: false, hasDiagnosticImplications: false, surfaceThemesAfter: false },
] as const;
