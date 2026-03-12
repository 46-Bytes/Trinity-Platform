#!/usr/bin/env python3
"""
Auto-fill diagnostic questions for a given diagnostic ID or engagement ID.

Usage (direct DB mode - no server needed):
    python fill_diagnostic.py --diagnostic-id <UUID>
    python fill_diagnostic.py --engagement-id <UUID>

Usage (API mode - requires running server):
    python fill_diagnostic.py --diagnostic-id <UUID> --api --token eyJ...

Options:
    --api            Use API mode instead of direct DB (requires running server)
    --base-url       API base URL (default: http://localhost:8000)
    --cookie         Session cookie string for auth (API mode only)
    --token          Bearer token for auth (API mode only)
    --submit         Also submit the diagnostic for AI processing after filling
    --user-id        User ID for submission (required if --submit is used)
    --dry-run        Print responses without sending

The script will:
1. Fetch the diagnostic (or find it from the engagement)
2. Determine the type (sale_ready or value_builder) from the engagement
3. Fill all questions with realistic test data
4. Save responses via direct DB update (default) or API call (--api)
"""

import argparse
import json
import sys
import os

# Add backend root to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import requests as http_requests
except ImportError:
    http_requests = None

# ---------------------------------------------------------------------------
# Test data: Sale Ready
# ---------------------------------------------------------------------------
SALE_READY_RESPONSES = {
    # ── Page: general ──
    "industry_type": "Professional services",
    "primary_contact_person_name": "John Smith",
    "primary_contact_person_email": "john.smith@example.com",
    "primary_contact_person_mobile_phone": "+61412345678",
    "primary_contact_person_role_or_title": "Managing Director",
    "business_details": [
        {
            "companyName": "Smith Consulting Pty Ltd",
            "tradingName": "Smith Consulting",
            "abn": "12345678901",
            "directors": "John Smith, Jane Smith"
        }
    ],
    "headquarter_business_address": "123 Business St, Sydney NSW 2000",
    "other_office_addresses": [
        {"addresses": "456 Branch Rd, Melbourne VIC 3000"}
    ],
    "business_email": "info@smithconsulting.com.au",
    "business_phone": "+61212345678",
    "business_websites": "https://www.smithconsulting.com.au",
    "accountant_company_name": "ABC Accounting Services",
    "accountant_contact_person": "Sarah Johnson",
    "accountant_address": "789 Accountant Ave, Sydney NSW 2000",
    "accountant_phone": "+61298765432",
    "accountant_email": "sarah@abcaccounting.com.au",
    "reason_for_sale": "Retirement and looking to transition the business to new ownership",
    "business_description": "Professional consulting services specializing in business strategy and operations optimization for mid-market companies",
    "business_founded_by_you": "Yes",
    "business_age": 15,
    "last_year_turnover": "$1,000,001 - $5,000,000",
    "Intend_to_do_post_sale": [
        {"Name": "John Smith", "Response": "Retire and travel"},
        {"Name": "Jane Smith", "Response": "Start a new venture in a different industry"}
    ],

    # ── Page: legal-licensing ──
    "business_structure": "Proprietary Limited Company",
    "other_shareholders_count": "2",
    "directors_total_count": "2",
    "operational_licenses_needed": "No",
    "currently_facing_legal_actions": "No",
    "regulatory_compliance": "Yes",
    "business_regulations_compliance_details": "Comply with Australian Consumer Law, Privacy Act, and workplace health and safety regulations",
    "business_location_count": "1-10",
    "does_the_business_own_any_properties": "No",
    "leases_properties": "1",
    "business_property_1": {
        "business_property_address": "123 Business St, Sydney NSW 2000",
        "premise_type": "Office",
        "lease_terms": "5 years",
        "options": "2 x 5 year options",
        "current_term_expiry_date": "2027-12-31",
        "rent": "$65,000 per annum",
        "rent_include_outgoings": "$78,000 per annum",
        "rent_review_method": "CPI or 3%, whichever is greater",
        "next_review_date": "2026-12-31",
        "council_rates_per_quarter": "$2,500",
        "water_rates_per_quarter": "$400",
        "body_corporate_per_quarter": "$1,200",
        "property_ownership_entity_name": "N/A - Leased",
        "real_property_description": "Level 5, Suite 502",
        "strata_or_torrens_title": "Strata",
        "annual_rates": "$10,000",
        "annual_corporate_fees": "$4,800",
        "zoning": "Commercial B2",
        "land_area": "250 sqm",
        "construction_type": "Concrete and glass commercial tower",
        "estimated_age_of_building": "15 years",
        "number_of_parking_spaces": "4",
        "proposed_annual_rental": "$68,000",
        "total_annual_outgoings": "$14,800"
    },
    "property_upgrades_needed": "No",
    "written_contracts_with_key_customers": "Yes, all of them",
    "lease_assignment_clause_known": "Yes, it does",
    "business_registrations_current": "Yes",
    "shareholder_agreements_in_place": "Yes",
    "insurance_coverage_confirmed": "Yes, all of these",
    "workplace_incidents_investigations": "No",

    # ── Page: financial ──
    "do_you_have_any_debts_in_the_business": "Yes",
    "list_business_debts": [
        {"debt": "Equipment Finance", "remainingAmount": "$25,000", "remainingTerm": "2 years"}
    ],
    "debt_repayment_consistency": "Yes",
    "are_your_activity_statements_up_to_date": "Yes",
    "are_your_business_tax_returns_up_to_date": "Yes",
    "do_you_have_a_bookkeeper": "Yes",
    "bookkeeper_internal_or_external": "External",
    "accountant_meeting_freq": "quarterly",
    "key_reports_review_frequency": "Monthly",
    "which_reports_do_you_review": [
        "P&L", "Balance Sheet", "Bank Statements",
        "Cash flow Forecast", "Budget", "Debtors",
        "Sales and Marketing Data Report"
    ],
    "profit_or_loss_last_year": "Profit",
    "net_profit_amount_if_profitable": "$250,001 - $500,000",
    "profitability_concerns": "No significant concerns. Market is stable and we have strong client relationships.",
    "personal_business_expenses_separated": "Yes",
    "normalised_ebitda_calculated": "Yes",
    "financial_forecasts_exist": "Yes",
    "balance_sheets_reconciled": "Yes",
    "personal_expenses_through_business": "No",
    "fixed_asset_register_exists": "Yes",
    "top_3_business_expenses": ["Permanent staff", "Property mortgage or lease", "Marketing"],
    "stock_current_estimate": "0",
    "lowest_manageable_stock_level": "0",
    "minimum_stock_value_to_sell": "0",
    "unfinished_work_over_three_days": "Yes",
    "wip_value_if_sold_tomorrow": "$150,000",
    "forward_orders_list": [
        {
            "forwardOrdersDescription": "Strategic planning project for manufacturing client",
            "completeOrderDaysRequired": "90",
            "dollarValue": "$120,000"
        },
        {
            "forwardOrdersDescription": "Operations optimization for retail client",
            "completeOrderDaysRequired": "60",
            "dollarValue": "$80,000"
        }
    ],
    "wc_debtors_capital_required": "$200,000",
    "wc_creditors_capital_required": "$50,000",
    "wc_stock_capital_required": "$0",
    "wc_inventory_capital_required": "$0",
    "wc_wip_capital_required": "$150,000",
    "wc_bonds_capital_required": "$10,000",
    "wc_other_item": "None",
    "encumbrances_list": [
        {
            "item": "Office equipment",
            "loanType": "Finance lease",
            "financier": "ABC Finance",
            "monthlyPayment": "$1,200",
            "finalPaymentDue": "2027-06-30"
        }
    ],

    # ── Page: financial_docs ──
    # NOTE: docs_* fields are file uploads - skipped (cannot be auto-filled)

    # ── Page: operations ──
    "trading_days": [
        {
            "monday": "9:00 AM - 5:00 PM",
            "tuesday": "9:00 AM - 5:00 PM",
            "wednesday": "9:00 AM - 5:00 PM",
            "thursday": "9:00 AM - 5:00 PM",
            "friday": "9:00 AM - 5:00 PM",
            "saturday": "Closed",
            "sunday": "Closed"
        }
    ],
    "public_holiday_trading": "No",
    "additional_business_operations_info": "We operate Monday to Friday with occasional client meetings on weekends by appointment",
    "owners_duties": [
        {
            "ownerName": "John Smith",
            "approximateHoursPerWeek": "45",
            "dayToDayDuties": "Client meetings, project oversight, team management, strategic planning",
            "periodicDuties": "Business development, networking, financial reviews, board meetings"
        }
    ],
    "customer_relationships_owner_managed_pct": "40",
    "has_succession_plan_in_place": "Yes",
    "succession_plan_proactive_implementation": "Yes",
    "succession_plan_effectiveness": "Yes",
    "succession_plan_for_business_continuity": "Yes",
    "family_members_operating": "No",
    "directors_share_vision": "Yes",
    "is_ceo_and_gm_same_or_diff_people": "Same",
    "is_ceo_another_shareholder": "Yes",
    "can_the_business_operate_without_you": "Yes",
    "business_operate_completely_without_guidance": "No",
    "how_much_is_the_business_reliant_on_you": "Moderately reliant - the business can operate for 2-4 weeks without the owner",
    "when_you_are_not_around": "Operations Manager handles day-to-day operations and senior consultants manage their own projects",
    "business_has_board": "No",
    "business_has_divisional_structure": "Yes",
    "how_many_divisions_do_you_have": "3",
    "do_you_run_internal_management_meetings": "Yes",
    "mgmt_meeting_process": "Structured agenda with minutes and action items tracked",
    "internal_mgmt_meetings_frequency": "Weekly",
    "do_you_run_internal_team_meetings": "Yes",
    "internal_team_meetings_frequency": "Weekly",
    "run_divisional_mgmt_meetings": "Yes in every division",
    "mgmt_meetings_frequency": ["Weekly", "Monthly"],
    "mgmt_meetings_tools": ["Agenda", "Meeting Minutes", "Action/tasking sheet"],
    "runs_divisional_team_meetings": "Yes in every division",
    "team_meetings_frequency": ["Weekly", "Monthly"],
    "team_meetings_tools": ["Agenda", "Meeting Minutes", "Action/tasking sheet"],
    "senior_mgmt_strategy_review_frequency": "Monthly",
    "sr_mgmt_strategy_review_tools": ["Agenda", "Meeting Minutes", "Action/tasking sheet"],
    "next_2_years_invest_more": "Yes",
    "util_production_equip": "N/A",
    "util_manufacturing_facility": "N/A",
    "util_manufacturing_team": "N/A",
    "processes_documented": "Yes",
    "business_process_review_date": "in the past 6 months",
    "processes_and_systems_effectiveness_rating": 8,
    "business_automation_tools": "Yes",
    "operational_reports_review": "Yes",
    "types_of_operational_reports_reviewed": "Weekly KPI dashboard, Monthly financial reports, Quarterly project performance reports",
    "do_you_sell_online_via_your_own_ecommerce_store": "No",
    "sell_on_marketplaces": "No",
    "business_tech_stack": "Microsoft 365, Xero accounting, HubSpot CRM, Slack, Asana for project management, Zoom",
    "process_reengineering_done": "Yes",
    "tech_sync_efficiency": "Yes",
    "tech_support_access": "Yes",
    "tech_rating_vs_competitors": 8,

    # ── Page: human-resources ──
    "fte_count": 8,
    "pte_count": 2,
    "casual_emp_count": 0,
    "contractor_count": 3,
    "staff_details": [
        {
            "staffName": "Senior Consultant 1",
            "positionType": "Full time",
            "jobTitle": "Senior Business Consultant",
            "briefJobDescription": "Lead consulting projects, client relationship management",
            "hoursPerWeek": "40",
            "grossWagesPerWeek": "$2,500",
            "keyEmployee": "Yes",
            "doesPayrollTaxApply": "Yes"
        },
        {
            "staffName": "Operations Manager",
            "positionType": "Full time",
            "jobTitle": "Operations Manager",
            "briefJobDescription": "Oversee daily operations, resource allocation, process management",
            "hoursPerWeek": "40",
            "grossWagesPerWeek": "$2,200",
            "keyEmployee": "Yes",
            "doesPayrollTaxApply": "Yes"
        },
        {
            "staffName": "Business Consultant",
            "positionType": "Full time",
            "jobTitle": "Business Consultant",
            "briefJobDescription": "Project support, research, client engagement",
            "hoursPerWeek": "38",
            "grossWagesPerWeek": "$1,800",
            "keyEmployee": "No",
            "doesPayrollTaxApply": "Yes"
        },
        {
            "staffName": "Marketing Coordinator",
            "positionType": "Part time",
            "jobTitle": "Marketing & Communications",
            "briefJobDescription": "Digital marketing, content creation, client communications",
            "hoursPerWeek": "25",
            "grossWagesPerWeek": "$1,200",
            "keyEmployee": "No",
            "doesPayrollTaxApply": "Yes"
        },
        {
            "staffName": "Office Administrator",
            "positionType": "Full time",
            "jobTitle": "Office Administrator",
            "briefJobDescription": "Reception, admin support, document management",
            "hoursPerWeek": "38",
            "grossWagesPerWeek": "$1,400",
            "keyEmployee": "No",
            "doesPayrollTaxApply": "Yes"
        }
    ],
    "workplace_agreements": True,
    "workplace_agreements_details": "Standard employment contracts with all permanent staff, including confidentiality and non-compete clauses",
    "staff_have_signed_contracts": "Yes",
    "superannuation_payments_up_to_date": "Yes",
    "qualified_staff_availability": "Moderately competitive market. Takes 2-3 months to find qualified consultants",
    "outsources_work": "Yes",
    "percent_work_complete_3rd_parties": 15,
    "has_3rd_party_service_level_agreements": "Yes",
    "team_position_descriptions": "Everyone",
    "last_time_team_position_descriptions_reviewed": "in the past 12 months",
    "has_hr_policies_and_procs": "Yes",
    "performance_review_freq": "quarterly",
    "busy_rating": 85,
    "underperforming_staff_identification": "No",
    "staff_recruitment_need": "Yes",
    "staff_retention_threat_six_months": "No",
    "staffing_and_hr_challenges": "No",
    "team_cohesion_satisfaction": "Yes",
    "hr_metrics_tracking": "Yes",
    "measured_hr_data_types": ["Absenteeism", "Annual leave", "Sick leave"],

    # ── Page: customers ──
    "percentage_chance_of_losing_key_customers": 20,
    "has_crm": "Yes",
    "crm_system_effectiveness": 8,
    "customer_data_utilization": "Yes",
    "percentage_of_revenue_from_largest_customer": 15,
    "percentage_of_revenue_from_top_3_customers": 35,
    "major_customers_count": "6",
    "major_customers_total_annual_sales": "$800,000",
    "repeat_customer_sales_percentage": "75",
    "new_customer_sales_percentage": "25",
    "new_customer_monthly_sales_value": "$50,000",
    "sales_seasonal": "No",
    "twelve_month_sales_change_reason": "Steady growth due to increased demand for business consulting services and successful referral network",
    "active_customers_count": 45,
    "have_customers_on_service_or_supply_contracts": "Yes",
    "percentage_of_customers_on_service_contracts": 40,
    "has_dedicated_customer_service_person_or_team": "No",
    "has_customer_service_procedures_in_place": "Yes",
    "formal_written_customer_agreements": "Yes",
    "sells_physical_products": "No",
    "sell_deliver_provide_services_any_type": "Yes",
    "types_of_services": ["Intellectual service (example: accounting)", "Professional services"],
    "service_type_standard_or_custom": "Both",
    "revenue_from_custom_services": 60,
    "last_time_reviewed_products_services": "6 months ago",
    "why_reviewed_products_services_now": "Following market research",
    "last_time_updated_prices": "1 year ago",
    "why_update_prices_now": "Following market research",
    "rating_product_service_right_for_market": 8,
    "our_prices_are_the_same_as_that_of_competitors": "Higher",
    "our_productservice_mix_needs_to_change": "No",
    "our_customers_understand_our_productsservices": "Yes",
    "products_services_still_relevant_in_2_yrs": "Yes",
    "different_products_services_in_2_yrs": "Some changes are expected",
    "easy_supplier_access": "Yes",
    "our_margins_are_higher_than_industry_standard": "Yes",
    "has_sales_marketing_strategy": "Yes",
    "sales_marketing_strategy_review_date": "in the past 12 months",
    "has_sales_marketing_plan": "Yes",
    "sales_marketing_plan_review_date": "in the past 6 months",
    "sales_marketing_plan_implementation": "Yes",
    "growth_areas_in_sales_marketing_plan": "Yes",
    "do_you_have_a_clearly_articulated_sales_process": "Yes",
    "segmented_customer_list": "Yes",
    "total_marketing_budget": "$50,001 - $100,000",
    "online_marketing_budget": "$25,001 - $50,000",
    "offline_marketing_budget": "$25,001 - $50,000",
    "know_roi_for_all_money_spent_on_marketing": "Yes",
    "roi_per_dollar_spent_on_marketing": 4,
    "do_you_track_and_monitor_sales_and_marketing_data": "Yes",
    "method_for_capturing_sales_data": ["Google Analytics", "Your website", "Email marketing", "Customer market research"],
    "understands_captured_sales_data": "Yes",
    "sales_data_utilization_method": ["Make strategic decisions", "Make sales and marketing decisions", "Develop sales and marketing plans"],
    "sales_marketing_satisfaction": 8,

    # ── Page: competitive-forces ──
    "strategic_business_plan": "Yes",
    "strategic_plan_last_review": "in the past 12 months",
    "intellectual_property_excluded": [],
    "does_your_business_have_a_style_guide": "Yes",
    "style_guide_last_updated": "in the past 2 years",
    "does_the_business_have_a_website": "Yes",
    "website_last_updated_date": "in the past 6 months",
    "brand_consistency_rating": 8,
    "registered_trademarks": "Yes",
    "owns_all_digital_assets": "Yes",
    "nda_noncompete_with_key_staff": "Yes",
    "proprietary_methods_trade_secrets": "Yes",
    "premises_update_needed": "No",
    "strongest_advantage": "Strong client relationships built over 15 years, deep industry expertise, and a proven methodology that delivers measurable results",
    "main_competitor_analysis": [
        {
            "competitorName": "BigFirm Consulting",
            "competitorSize": "Bigger",
            "competitorPrice": "More Expensive",
            "competitorStrengths": "Brand recognition, large team, international presence",
            "competitorWeaknesses": "Less personalized service, higher overhead costs"
        },
        {
            "competitorName": "Local Advisors Pty Ltd",
            "competitorSize": "Same",
            "competitorPrice": "Same",
            "competitorStrengths": "Local market knowledge, competitive pricing",
            "competitorWeaknesses": "Limited service range, smaller team"
        },
        {
            "competitorName": "Strategy Partners",
            "competitorSize": "Bigger",
            "competitorPrice": "More Expensive",
            "competitorStrengths": "Strong brand, diverse service offering",
            "competitorWeaknesses": "Less flexible, longer engagement times"
        }
    ],
    "entry_barriers": "Building reputation and trust takes significant time. Industry expertise and qualified consultants are difficult to find.",
    "what_new_threats_could_impact_your_business": "Increased competition from international firms, AI-driven consulting tools, economic downturn affecting client budgets",
    "customer_alternative_options": "In-house consulting teams, DIY business improvement programs, online courses and resources, other consulting firms",
    "supplier_threats": "Not applicable as we don't rely on physical product suppliers",
    "buyer_threats": "Clients increasingly demanding lower fees and faster turnaround times",
    "industry_challenges_2yr": "Economic uncertainty, pressure on pricing, talent retention, increased competition",
    "industry_opportunities_2yr": "Digital transformation projects, sustainability consulting, government stimulus programs, growth in SME sector",
    "list_the_strengths_within_your_business": "Strong client relationships, experienced team, proven methodologies, solid reputation, diversified client base",
    "list_the_weaknesses_within_your_business": "Dependent on key personnel, limited digital marketing presence, no proprietary technology platform",
    "list_the_opportunities_available_to_your_business": "Expand into new industry sectors, develop online consulting products, strategic partnerships, geographic expansion",
    "list_the_threats_within_your_business": "Key staff departure, client concentration risk, economic downturn, new market entrants",

    # ── Page: tax-compliance ──
    "outstanding_ato_liabilities": "No",
    "payroll_tax_correctly_lodged": "Yes",
    "division_7a_loan_arrangements": "No",
    "regulatory_correspondence_audits": "No",
    "cgt_implications_discussed": "Yes",
    "ppsr_registrations_current": "Yes",

    # ── Page: due-diligence ──
    "documents_centrally_organised": "Yes",
    "previous_dd_experience": "No",
    "can_produce_documents_48hrs": "Yes",
    "written_business_overview_exists": "Yes",

    # ── Page: page1 ──
    "is_there_anything_else_youd_like_to_share": "The business has strong fundamentals and is well-positioned for future growth. We are looking for a buyer who will maintain our commitment to quality and client service."
}


# ---------------------------------------------------------------------------
# Test data: Value Builder
# ---------------------------------------------------------------------------
VALUE_BUILDER_RESPONSES = {
    # ── Page: general ──
    "industry_type": "Professional services",
    "primary_contact_person_name": "John Smith",
    "primary_contact_person_email": "john.smith@example.com",
    "primary_contact_person_mobile_phone": "+61412345678",
    "primary_contact_person_role_or_title": "Managing Director",
    "business_details": [
        {
            "companyName": "Smith Consulting Pty Ltd",
            "tradingName": "Smith Consulting",
            "abn": "12345678901",
            "directors": "John Smith, Jane Smith"
        }
    ],
    "headquarter_business_address": "123 Business St, Sydney NSW 2000",
    "other_office_addresses": [
        {"addresses": "456 Branch Rd, Melbourne VIC 3000"}
    ],
    "business_email": "info@smithconsulting.com.au",
    "business_phone": "+61212345678",
    "business_websites": "https://www.smithconsulting.com.au",
    "accountant_company_name": "ABC Accounting Services",
    "accountant_contact_person": "Sarah Johnson",
    "accountant_address": "789 Accountant Ave, Sydney NSW 2000",
    "accountant_phone": "+61298765432",
    "accountant_email": "sarah@abcaccounting.com.au",
    "business_description": "Professional consulting services specializing in business strategy and operations optimization for mid-market companies",
    "growth_goals": [
        "Grow revenue",
        "Improve profitability",
        "Build a management team",
        "Improve systems and processes"
    ],
    "owner_hours_per_week": "40-50",
    "fix_one_thing": "Reduce my day-to-day involvement in client delivery so I can focus more on strategy and growth",
    "business_founded_by_you": "Yes",
    "business_age": 15,
    "last_year_turnover": "$1,000,001 - $5,000,000",

    # ── Page: legal-licensing ──
    "business_structure": "Proprietary Limited Company",
    "other_shareholders_count": "2",
    "directors_total_count": "2",
    "operational_licenses_needed": "No",
    "currently_facing_legal_actions": "No",
    "regulatory_compliance": "Yes",
    "business_regulations_compliance_details": "Comply with Australian Consumer Law, Privacy Act, and workplace health and safety regulations",
    "business_location_count": "1-10",
    "does_the_business_own_any_properties": "No",
    "leases_properties": "1",
    "business_property_1": {
        "business_property_address": "123 Business St, Sydney NSW 2000",
        "premise_type": "Office",
        "lease_terms": "5 years",
        "options": "2 x 5 year options",
        "current_term_expiry_date": "2027-12-31",
        "rent": "$65,000 per annum",
        "rent_include_outgoings": "$78,000 per annum",
        "rent_review_method": "CPI or 3%, whichever is greater",
        "next_review_date": "2026-12-31",
        "council_rates_per_quarter": "$2,500",
        "water_rates_per_quarter": "$400",
        "body_corporate_per_quarter": "$1,200",
        "property_ownership_entity_name": "N/A - Leased",
        "real_property_description": "Level 5, Suite 502",
        "strata_or_torrens_title": "Strata",
        "annual_rates": "$10,000",
        "annual_corporate_fees": "$4,800",
        "zoning": "Commercial B2",
        "land_area": "250 sqm",
        "construction_type": "Concrete and glass commercial tower",
        "estimated_age_of_building": "15 years",
        "number_of_parking_spaces": "4",
        "proposed_annual_rental": "$68,000",
        "total_annual_outgoings": "$14,800"
    },
    "property_upgrades_needed": "No",
    "written_contracts_with_key_customers": "Yes, all of them",
    "business_registrations_current": "Yes",
    "shareholder_agreements_in_place": "Yes",
    "insurance_coverage_confirmed": "Yes, all of these",
    "workplace_incidents_investigations": "No",
    "outstanding_ato_liabilities": "No",
    "payroll_tax_correctly_lodged": "Yes",
    "division_7a_loan_arrangements": "No",
    "regulatory_correspondence_audits": "No",
    "ppsr_registrations_current": "Yes",

    # ── Page: financial ──
    "do_you_have_any_debts_in_the_business": "Yes",
    "list_business_debts": [
        {"debt": "Equipment Finance", "remainingAmount": "$25,000", "remainingTerm": "2 years"}
    ],
    "debt_repayment_consistency": "Yes",
    "are_your_activity_statements_up_to_date": "Yes",
    "are_your_business_tax_returns_up_to_date": "Yes",
    "do_you_have_a_bookkeeper": "Yes",
    "bookkeeper_internal_or_external": "External",
    "accountant_meeting_freq": "quarterly",
    "key_reports_review_frequency": "Monthly",
    "which_reports_do_you_review": [
        "P&L", "Balance Sheet", "Bank Statements",
        "Cash flow Forecast", "Budget", "Debtors",
        "Sales and Marketing Data Report"
    ],
    "profit_or_loss_last_year": "Profit",
    "net_profit_amount_if_profitable": "$250,001 - $500,000",
    "profitability_concerns": "No significant concerns. Market is stable and we have strong client relationships.",
    "personal_business_expenses_separated": "Yes",
    "normalised_ebitda_calculated": "Yes",
    "financial_forecasts_exist": "Yes",
    "balance_sheets_reconciled": "Yes",
    "personal_expenses_through_business": "No",
    "fixed_asset_register_exists": "Yes",
    "top_3_business_expenses": ["Permanent staff", "Property mortgage or lease", "Marketing"],
    "stock_current_estimate": "0",
    "lowest_manageable_stock_level": "0",
    "unfinished_work_over_three_days": "Yes",
    "forward_orders_list": [
        {
            "forwardOrdersDescription": "Strategic planning project for manufacturing client",
            "completeOrderDaysRequired": "90",
            "dollarValue": "$120,000"
        },
        {
            "forwardOrdersDescription": "Operations optimization for retail client",
            "completeOrderDaysRequired": "60",
            "dollarValue": "$80,000"
        }
    ],
    "wc_debtors_capital_required": "$200,000",
    "wc_creditors_capital_required": "$50,000",
    "wc_stock_capital_required": "$0",
    "wc_inventory_capital_required": "$0",
    "wc_wip_capital_required": "$150,000",
    "wc_bonds_capital_required": "$10,000",
    "wc_other_item": "None",
    "encumbrances_list": [
        {
            "item": "Office equipment",
            "loanType": "Finance lease",
            "financier": "ABC Finance",
            "monthlyPayment": "$1,200",
            "finalPaymentDue": "2027-06-30"
        }
    ],
    "revenue_trend_3years": "Consistent growth of 10-15% year over year",
    "gross_margin_by_line": "Strategy consulting: 65%, Operations consulting: 55%, Training/workshops: 70%",
    "cash_flow_forecast": "Positive cash flow maintained throughout the year with seasonal dip in January",
    "tracks_kpis": "Yes",

    # ── Page: financial_docs ──
    # NOTE: docs_* fields are file uploads - skipped (cannot be auto-filled)

    # ── Page: operations ──
    "trading_days": [
        {
            "monday": "9:00 AM - 5:00 PM",
            "tuesday": "9:00 AM - 5:00 PM",
            "wednesday": "9:00 AM - 5:00 PM",
            "thursday": "9:00 AM - 5:00 PM",
            "friday": "9:00 AM - 5:00 PM",
            "saturday": "Closed",
            "sunday": "Closed"
        }
    ],
    "public_holiday_trading": "No",
    "additional_business_operations_info": "We operate Monday to Friday with occasional client meetings on weekends",
    "owners_duties": [
        {
            "ownerName": "John Smith",
            "approximateHoursPerWeek": "45",
            "dayToDayDuties": "Client meetings, project oversight, team management, strategic planning",
            "periodicDuties": "Business development, networking, financial reviews"
        }
    ],
    "customer_relationships_owner_managed_pct": "40",
    "has_succession_plan_in_place": "Yes",
    "succession_plan_proactive_implementation": "Yes",
    "succession_plan_effectiveness": "Yes",
    "succession_plan_for_business_continuity": "Yes",
    "family_members_operating": "No",
    "directors_share_vision": "Yes",
    "is_ceo_and_gm_same_or_diff_people": "Same",
    "is_ceo_another_shareholder": "Yes",
    "can_the_business_operate_without_you": "Yes",
    "business_operate_completely_without_guidance": "No",
    "how_much_is_the_business_reliant_on_you": "Moderately reliant - the business can operate for 2-4 weeks without the owner",
    "when_you_are_not_around": "Operations Manager handles day-to-day operations and senior consultants manage their own projects",
    "business_has_board": "No",
    "business_has_divisional_structure": "Yes",
    "how_many_divisions_do_you_have": "3",
    "do_you_run_internal_management_meetings": "Yes",
    "mgmt_meeting_process": "Structured agenda with minutes and action items tracked",
    "internal_mgmt_meetings_frequency": "Weekly",
    "do_you_run_internal_team_meetings": "Yes",
    "internal_team_meetings_frequency": "Weekly",
    "run_divisional_mgmt_meetings": "Yes in every division",
    "mgmt_meetings_frequency": ["Weekly", "Monthly"],
    "mgmt_meetings_tools": ["Agenda", "Meeting Minutes", "Action/tasking sheet"],
    "runs_divisional_team_meetings": "Yes in every division",
    "team_meetings_frequency": ["Weekly", "Monthly"],
    "team_meetings_tools": ["Agenda", "Meeting Minutes", "Action/tasking sheet"],
    "senior_mgmt_strategy_review_frequency": "Monthly",
    "sr_mgmt_strategy_review_tools": ["Agenda", "Meeting Minutes", "Action/tasking sheet"],
    "next_2_years_invest_more": "Yes",
    "util_production_equip": "N/A",
    "util_manufacturing_facility": "N/A",
    "util_manufacturing_team": "N/A",
    "processes_documented": "Yes",
    "business_process_review_date": "in the past 6 months",
    "processes_and_systems_effectiveness_rating": 8,
    "business_automation_tools": "Yes",
    "operational_reports_review": "Yes",
    "types_of_operational_reports_reviewed": "Weekly KPI dashboard, Monthly financial reports, Quarterly project performance reports",
    "do_you_sell_online_via_your_own_ecommerce_store": "No",
    "sell_on_marketplaces": "No",
    "business_tech_stack": "Microsoft 365, Xero accounting, HubSpot CRM, Slack, Asana, Zoom",
    "process_reengineering_done": "Yes",
    "tech_sync_efficiency": "Yes",
    "tech_support_access": "Yes",
    "tech_rating_vs_competitors": 8,
    "scalability_capacity": "Current systems can support 2x revenue growth without major changes. Beyond that, will need additional staff and upgraded project management tools.",
    "documents_well_organised": "Yes",

    # ── Page: human-resources ──
    "fte_count": 8,
    "pte_count": 2,
    "casual_emp_count": 0,
    "contractor_count": 3,
    "staff_details": [
        {
            "staffName": "Senior Consultant 1",
            "positionType": "Full time",
            "jobTitle": "Senior Business Consultant",
            "briefJobDescription": "Lead consulting projects, client relationship management",
            "hoursPerWeek": "40",
            "grossWagesPerWeek": "$2,500",
            "keyEmployee": "Yes",
            "doesPayrollTaxApply": "Yes"
        },
        {
            "staffName": "Operations Manager",
            "positionType": "Full time",
            "jobTitle": "Operations Manager",
            "briefJobDescription": "Oversee daily operations, resource allocation",
            "hoursPerWeek": "40",
            "grossWagesPerWeek": "$2,200",
            "keyEmployee": "Yes",
            "doesPayrollTaxApply": "Yes"
        },
        {
            "staffName": "Business Consultant",
            "positionType": "Full time",
            "jobTitle": "Business Consultant",
            "briefJobDescription": "Project support, research, client engagement",
            "hoursPerWeek": "38",
            "grossWagesPerWeek": "$1,800",
            "keyEmployee": "No",
            "doesPayrollTaxApply": "Yes"
        },
        {
            "staffName": "Marketing Coordinator",
            "positionType": "Part time",
            "jobTitle": "Marketing & Communications",
            "briefJobDescription": "Digital marketing, content creation",
            "hoursPerWeek": "25",
            "grossWagesPerWeek": "$1,200",
            "keyEmployee": "No",
            "doesPayrollTaxApply": "Yes"
        },
        {
            "staffName": "Office Administrator",
            "positionType": "Full time",
            "jobTitle": "Office Administrator",
            "briefJobDescription": "Reception, admin support, document management",
            "hoursPerWeek": "38",
            "grossWagesPerWeek": "$1,400",
            "keyEmployee": "No",
            "doesPayrollTaxApply": "Yes"
        }
    ],
    "workplace_agreements": True,
    "workplace_agreements_details": "Standard employment contracts with confidentiality and non-compete clauses",
    "staff_have_signed_contracts": "Yes",
    "superannuation_payments_up_to_date": "Yes",
    "qualified_staff_availability": "Moderately competitive market. Takes 2-3 months to find qualified consultants",
    "outsources_work": "Yes",
    "percent_work_complete_3rd_parties": 15,
    "has_3rd_party_service_level_agreements": "Yes",
    "team_position_descriptions": "Everyone",
    "last_time_team_position_descriptions_reviewed": "in the past 12 months",
    "has_hr_policies_and_procs": "Yes",
    "performance_review_freq": "quarterly",
    "busy_rating": 85,
    "underperforming_staff_identification": "No",
    "staff_recruitment_need": "Yes",
    "staff_retention_threat_six_months": "No",
    "staffing_and_hr_challenges": "No",
    "team_cohesion_satisfaction": "Yes",
    "hr_metrics_tracking": "Yes",
    "measured_hr_data_types": ["Absenteeism", "Annual leave", "Sick leave"],

    # ── Page: customers ──
    "percentage_chance_of_losing_key_customers": 20,
    "has_crm": "Yes",
    "crm_system_effectiveness": 8,
    "customer_data_utilization": "Yes",
    "percentage_of_revenue_from_largest_customer": 15,
    "percentage_of_revenue_from_top_3_customers": 35,
    "major_customers_count": "6",
    "major_customers_total_annual_sales": "$800,000",
    "repeat_customer_sales_percentage": "75",
    "new_customer_sales_percentage": "25",
    "new_customer_monthly_sales_value": "$50,000",
    "sales_seasonal": "No",
    "twelve_month_sales_change_reason": "Steady growth due to increased demand and successful referral network",
    "active_customers_count": 45,
    "have_customers_on_service_or_supply_contracts": "Yes",
    "percentage_of_customers_on_service_contracts": 40,
    "has_dedicated_customer_service_person_or_team": "No",
    "has_customer_service_procedures_in_place": "Yes",
    "formal_written_customer_agreements": "Yes",
    "sells_physical_products": "No",
    "sell_deliver_provide_services_any_type": "Yes",
    "types_of_services": ["Intellectual service (example: accounting)", "Professional services"],
    "service_type_standard_or_custom": "Both",
    "revenue_from_custom_services": 60,
    "last_time_reviewed_products_services": "6 months ago",
    "why_reviewed_products_services_now": "Following market research",
    "last_time_updated_prices": "1 year ago",
    "why_update_prices_now": "Following market research",
    "rating_product_service_right_for_market": 8,
    "our_prices_are_the_same_as_that_of_competitors": "Higher",
    "our_productservice_mix_needs_to_change": "No",
    "our_customers_understand_our_productsservices": "Yes",
    "products_services_still_relevant_in_2_yrs": "Yes",
    "different_products_services_in_2_yrs": "Some changes are expected",
    "easy_supplier_access": "Yes",
    "our_margins_are_higher_than_industry_standard": "Yes",
    "has_sales_marketing_strategy": "Yes",
    "sales_marketing_strategy_review_date": "in the past 12 months",
    "has_sales_marketing_plan": "Yes",
    "sales_marketing_plan_review_date": "in the past 6 months",
    "sales_marketing_plan_implementation": "Yes",
    "growth_areas_in_sales_marketing_plan": "Yes",
    "do_you_have_a_clearly_articulated_sales_process": "Yes",
    "segmented_customer_list": "Yes",
    "total_marketing_budget": "$50,001 - $100,000",
    "online_marketing_budget": "$25,001 - $50,000",
    "offline_marketing_budget": "$25,001 - $50,000",
    "know_roi_for_all_money_spent_on_marketing": "Yes",
    "roi_per_dollar_spent_on_marketing": 4,
    "do_you_track_and_monitor_sales_and_marketing_data": "Yes",
    "method_for_capturing_sales_data": ["Google Analytics", "Your website", "Email marketing", "Customer market research"],
    "understands_captured_sales_data": "Yes",
    "sales_data_utilization_method": ["Make strategic decisions", "Make sales and marketing decisions", "Develop sales and marketing plans"],
    "sales_marketing_satisfaction": 8,
    "recurring_revenue_percentage": "35",
    "regular_price_increases": "Yes",

    # ── Page: competitive-forces ──
    "strategic_business_plan": "Yes",
    "strategic_plan_last_review": "in the past 12 months",
    "does_your_business_have_a_style_guide": "Yes",
    "style_guide_last_updated": "in the past 2 years",
    "does_the_business_have_a_website": "Yes",
    "website_last_updated_date": "in the past 6 months",
    "brand_consistency_rating": 8,
    "registered_trademarks": "Yes",
    "owns_all_digital_assets": "Yes",
    "nda_noncompete_with_key_staff": "Yes",
    "proprietary_methods_trade_secrets": "Yes",
    "premises_update_needed": "No",
    "strongest_advantage": "Strong client relationships built over 15 years, deep industry expertise, and a proven methodology that delivers measurable results",
    "main_competitor_analysis": [
        {
            "competitorName": "BigFirm Consulting",
            "competitorSize": "Bigger",
            "competitorPrice": "More Expensive",
            "competitorStrengths": "Brand recognition, large team",
            "competitorWeaknesses": "Less personalized service"
        },
        {
            "competitorName": "Local Advisors Pty Ltd",
            "competitorSize": "Same",
            "competitorPrice": "Same",
            "competitorStrengths": "Local market knowledge",
            "competitorWeaknesses": "Limited service range"
        },
        {
            "competitorName": "Strategy Partners",
            "competitorSize": "Bigger",
            "competitorPrice": "More Expensive",
            "competitorStrengths": "Strong brand, diverse offerings",
            "competitorWeaknesses": "Less flexible, longer engagement times"
        }
    ],
    "entry_barriers": "Building reputation takes significant time. Industry expertise and qualified consultants are difficult to find.",
    "what_new_threats_could_impact_your_business": "AI-driven consulting tools, economic downturn, international firm expansion into local market",
    "customer_alternative_options": "In-house consulting teams, DIY programs, online courses, other consulting firms",
    "supplier_threats": "Not applicable as we don't rely on physical product suppliers",
    "buyer_threats": "Clients demanding lower fees and faster turnaround times",
    "industry_challenges_2yr": "Economic uncertainty, pricing pressure, talent retention, increased competition",
    "industry_opportunities_2yr": "Digital transformation, sustainability consulting, government programs, SME growth",
    "list_the_strengths_within_your_business": "Strong client relationships, experienced team, proven methodologies, solid reputation",
    "list_the_weaknesses_within_your_business": "Dependent on key personnel, limited digital marketing, no proprietary tech platform",
    "list_the_opportunities_available_to_your_business": "Expand into new sectors, develop online products, strategic partnerships",
    "list_the_threats_within_your_business": "Key staff departure, client concentration risk, economic downturn, new entrants",
    "competitor_replication_difficulty": "Our deep industry relationships and proprietary methodology would take 5-10 years to replicate",

    # ── Page: growth-strategy ──
    "documented_growth_strategy": "Yes",
    "biggest_growth_constraint": "Finding and retaining qualified senior consultants is the primary constraint on growth",
    "next_growth_opportunity": "Expanding into digital transformation consulting for mid-market companies",
    "new_products_services_12months": "Yes - launching a digital transformation advisory practice and an online business assessment tool",

    # ── Page: page1 ──
    "is_there_anything_else_youd_like_to_share": "We have invested significantly in developing our methodology and tools. The business has strong fundamentals and is well-positioned for future growth."
}


# ---------------------------------------------------------------------------
# DIRECT DATABASE MODE (default - no server needed)
# ---------------------------------------------------------------------------

def fill_via_db(args):
    """Fill diagnostic by directly updating the database."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from uuid import UUID

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in .env file.")
        print("  Make sure you have a .env file in the backend/ directory.")
        sys.exit(1)

    engine = create_engine(db_url, pool_pre_ping=True, echo=False)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        from app.models.diagnostic import Diagnostic
        from app.models.engagement import Engagement
    except ImportError:
        print("ERROR: Could not import app models. Make sure you're running from the backend/ directory")
        print("  or the backend/seed/ directory.")
        sys.exit(1)

    print("=" * 60)
    print("  DIAGNOSTIC AUTO-FILL SCRIPT (Direct DB Mode)")
    print("=" * 60)

    # 1. Resolve diagnostic
    if args.diagnostic_id:
        diag = db.query(Diagnostic).filter(Diagnostic.id == UUID(args.diagnostic_id)).first()
        if not diag:
            print(f"ERROR: Diagnostic {args.diagnostic_id} not found.")
            sys.exit(1)
    elif args.engagement_id:
        diagnostics = db.query(Diagnostic).filter(
            Diagnostic.engagement_id == UUID(args.engagement_id)
        ).all()
        if not diagnostics:
            print("ERROR: No diagnostics found for this engagement.")
            sys.exit(1)
        diag = None
        for d in diagnostics:
            if d.status in ("draft", "in_progress"):
                diag = d
                break
        if not diag:
            diag = diagnostics[0]
        print(f"  Found diagnostic: {diag.id} (status: {diag.status})")
    else:
        print("ERROR: Provide either --diagnostic-id or --engagement-id")
        sys.exit(1)

    # 2. Get engagement type
    eng = db.query(Engagement).filter(Engagement.id == diag.engagement_id).first()
    if not eng:
        print(f"ERROR: Engagement {diag.engagement_id} not found.")
        sys.exit(1)
    eng_type = eng.tool or "value_builder"

    print(f"\n  Diagnostic ID : {diag.id}")
    print(f"  Engagement ID : {eng.id}")
    print(f"  Engagement    : {eng.engagement_name}")
    print(f"  Type          : {eng_type}")

    # 3. Pick correct response set
    if eng_type == "sale_ready":
        responses = SALE_READY_RESPONSES
        print(f"  Responses     : Sale Ready ({len(responses)} fields)")
    else:
        responses = VALUE_BUILDER_RESPONSES
        print(f"  Responses     : Value Builder ({len(responses)} fields)")

    print()

    # 4. Dry-run
    if args.dry_run:
        print("DRY RUN - would write the following responses:\n")
        print(json.dumps(responses, indent=2, default=str)[:2000])
        print(f"\n... ({len(responses)} total fields)")
        db.close()
        return

    # 5. Update database directly
    print("Updating diagnostic in database...")

    # File upload field keys that should NOT be set to string values
    FILE_UPLOAD_KEYS = {
        "docs_profit_loss_statements", "docs_balance_sheets",
        "docs_plant_equipment_lists", "docs_additional_staff_list",
        "docs_last_3_years_fin_statements", "docs_last_3_years_fin_statements_by_ca",
        "docs_mgt_accts_last_fin_statements", "docs_mgt_accts_last_fin_statements_by_ca",
        "docs_forecast_vs_actual", "docs_profit_cashflow_forecast",
        "docs_last_3_yrs_tax_returns",
    }

    # Merge new responses with existing ones (if any)
    existing = diag.user_responses or {}
    existing.update(responses)

    # Remove any file upload keys that were incorrectly set to strings
    for key in FILE_UPLOAD_KEYS:
        if key in existing and isinstance(existing[key], str):
            del existing[key]

    from sqlalchemy.orm.attributes import flag_modified
    diag.user_responses = existing
    flag_modified(diag, "user_responses")
    diag.status = "in_progress"
    db.commit()
    db.refresh(diag)

    print(f"SUCCESS - Diagnostic updated (status: {diag.status})")
    print(f"  {len(responses)} response fields written to database.")

    db.close()
    print("\nDone!")


# ---------------------------------------------------------------------------
# API MODE (requires running server)
# ---------------------------------------------------------------------------

def get_headers(args):
    """Build auth headers from CLI args."""
    headers = {"Content-Type": "application/json"}
    if args.token:
        headers["Authorization"] = f"Bearer {args.token}"
    return headers


def get_cookies(args):
    """Build cookies dict from CLI args."""
    if args.cookie:
        cookies = {}
        for part in args.cookie.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies
    return {}


def api_get(url, args):
    resp = http_requests.get(url, headers=get_headers(args), cookies=get_cookies(args))
    resp.raise_for_status()
    return resp.json()


def api_patch(url, payload, args):
    resp = http_requests.patch(url, json=payload, headers=get_headers(args), cookies=get_cookies(args))
    resp.raise_for_status()
    return resp.json()


def api_post(url, payload, args):
    resp = http_requests.post(url, json=payload, headers=get_headers(args), cookies=get_cookies(args))
    resp.raise_for_status()
    return resp.json()


def fill_via_api(args):
    """Fill diagnostic via API calls (requires running server)."""
    if http_requests is None:
        print("ERROR: 'requests' package not installed.")
        sys.exit(1)

    base = args.base_url.rstrip("/")

    print("=" * 60)
    print("  DIAGNOSTIC AUTO-FILL SCRIPT (API Mode)")
    print("=" * 60)

    # 1. Resolve diagnostic
    if args.diagnostic_id:
        diag = api_get(f"{base}/api/diagnostics/{args.diagnostic_id}", args)
        diag_id = diag["id"]
        eng_id = diag["engagement_id"]
    elif args.engagement_id:
        diagnostics = api_get(f"{base}/api/diagnostics/engagement/{args.engagement_id}", args)
        if not diagnostics:
            print("ERROR: No diagnostics found for this engagement.")
            sys.exit(1)
        diag = None
        for d in diagnostics:
            if d["status"] in ("draft", "in_progress"):
                diag = d
                break
        if not diag:
            diag = diagnostics[0]
        diag_id = diag["id"]
        eng_id = args.engagement_id
        print(f"  Found diagnostic: {diag_id} (status: {diag['status']})")
    else:
        print("ERROR: Provide either --diagnostic-id or --engagement-id")
        sys.exit(1)

    eng = api_get(f"{base}/api/engagements/{eng_id}", args)
    eng_type = eng.get("tool", "value_builder")

    print(f"\n  Diagnostic ID : {diag_id}")
    print(f"  Engagement ID : {eng_id}")
    print(f"  Type          : {eng_type}")

    if eng_type == "sale_ready":
        responses = SALE_READY_RESPONSES
        print(f"  Responses     : Sale Ready ({len(responses)} fields)")
    else:
        responses = VALUE_BUILDER_RESPONSES
        print(f"  Responses     : Value Builder ({len(responses)} fields)")

    print()

    if args.dry_run:
        print("DRY RUN - would send the following payload:\n")
        print(json.dumps({"user_responses": responses, "status": "in_progress"}, indent=2, default=str)[:2000])
        return

    print("Sending responses to API...")
    payload = {"user_responses": responses, "status": "in_progress"}
    try:
        result = api_patch(f"{base}/api/diagnostics/{diag_id}/responses", payload, args)
        print(f"SUCCESS - Diagnostic updated (status: {result.get('status', 'unknown')})")
    except http_requests.HTTPError as e:
        print(f"ERROR updating responses: {e}")
        if e.response is not None:
            print(f"  Status: {e.response.status_code}")
            print(f"  Body:   {e.response.text[:500]}")
        sys.exit(1)

    if args.submit:
        if not args.user_id:
            print("\nERROR: --user-id is required when using --submit")
            sys.exit(1)
        print("\nSubmitting diagnostic for AI processing...")
        try:
            result = api_post(
                f"{base}/api/diagnostics/{diag_id}/submit",
                {"completed_by_user_id": args.user_id},
                args,
            )
            print(f"SUCCESS - Diagnostic submitted (status: {result.get('status', 'unknown')})")
        except http_requests.HTTPError as e:
            print(f"ERROR submitting: {e}")
            sys.exit(1)

    print("\nDone!")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Auto-fill diagnostic questions with test data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Direct DB mode (default - no server needed)
  python fill_diagnostic.py --diagnostic-id <UUID>
  python fill_diagnostic.py --engagement-id <UUID>

  # API mode (requires running server + auth)
  python fill_diagnostic.py --diagnostic-id <UUID> --api --token eyJ...

  # Dry run (preview without saving)
  python fill_diagnostic.py --diagnostic-id <UUID> --dry-run
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--diagnostic-id", help="Diagnostic UUID to fill")
    group.add_argument("--engagement-id", help="Engagement UUID (picks first active diagnostic)")

    parser.add_argument("--api", action="store_true", help="Use API mode (requires running server + auth)")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--cookie", help="Session cookie string (API mode only)")
    parser.add_argument("--token", help="Bearer token (API mode only)")
    parser.add_argument("--submit", action="store_true", help="Also submit for AI processing (API mode only)")
    parser.add_argument("--user-id", help="User UUID (required for --submit)")
    parser.add_argument("--dry-run", action="store_true", help="Preview payload without saving")

    args = parser.parse_args()

    if args.api:
        if not args.cookie and not args.token:
            print("WARNING: No auth provided (--cookie or --token). API calls may fail.\n")
        fill_via_api(args)
    else:
        fill_via_db(args)


if __name__ == "__main__":
    main()
