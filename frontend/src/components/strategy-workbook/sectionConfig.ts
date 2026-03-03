export interface WorkbookSectionConfig {
  /** The key in the extracted_data JSON object (matches backend _normalize_extracted_data keys) */
  key: string;
  /** The human-friendly display label shown in the accordion header */
  label: string;
}

/**
 * Defines the ordered list of strategy workbook sections for display purposes.
 * The array order IS the display order.
 *
 * Each entry maps a backend `extracted_data` key to a user-facing display label.
 * Sections whose key does not exist in the extracted data will be skipped during rendering.
 *
 * Note: `clarification_questions` is deliberately excluded — it is handled
 * separately in a dedicated UI area above the accordion.
 */
export const WORKBOOK_SECTION_ORDER: readonly WorkbookSectionConfig[] = [
  { key: 'visioning', label: 'Visioning' },
  { key: 'business_model', label: 'Business Model' },
  { key: 'market_segmentation', label: 'Market Segmentation' },
  { key: 'porters_5_forces', label: 'Porters Observations' },
  { key: 'pestel', label: 'PESTEL Observations' },
  { key: 'swot', label: 'SWOT Analysis' },
  { key: 'customer_analysis', label: 'Customer References' },
  { key: 'product_analysis', label: 'Product / Service References' },
  { key: 'competitor_analysis', label: 'Competitor Insights' },
  { key: 'growth_opportunities', label: 'Growth Initiatives' },
  { key: 'financial_targets', label: 'Financial Numbers' },
  { key: 'risks', label: 'Risks' },
  { key: 'strategic_priorities', label: 'Strategic Priorities' },
  { key: 'key_actions', label: 'Key Actions' },
] as const;
