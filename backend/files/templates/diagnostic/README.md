# Diagnostic Document Templates

This directory contains Word document templates (.docx files) that can be used to generate documents from diagnostic data.

## Template Format

### Placeholder Syntax

Templates use double curly braces to indicate placeholders that will be replaced with diagnostic data:

```
{{field_name}}
```

### Example

If your template contains:
```
Business Name: {{business_name}}
Industry: {{industry_type}}
```

The system will look for `business_name` and `industry_type` in the diagnostic's `user_responses` and replace them with the actual values.

### Placeholder Rules

1. **Placeholder names** must match field names from the diagnostic form
2. **Case-sensitive**: `{{BusinessName}}` and `{{business_name}}` are different
3. **Missing data**: If a field is not found in `user_responses`, it will be replaced with `[Not provided]`
4. **Supported locations**: Placeholders can be used in:
   - Paragraph text
   - Table cells
   - Headers and footers (if supported)

### Adding Templates

1. Create a Word document (.docx) with your desired format
2. Add placeholders using `{{field_name}}` syntax
3. Save the file in this directory
4. The template will automatically appear in the dropdown when generating documents

### Template Naming

- Use descriptive names (e.g., `business-plan-template.docx`, `summary-report.docx`)
- Display names are automatically generated from filenames (hyphens and underscores become spaces, words are capitalized)

### Example Template Structure

```
Document Title: {{business_name}} - Business Plan

Company Information:
- Business Name: {{business_name}}
- Industry: {{industry_type}}
- Founded: {{business_founded_year}}
- Location: {{business_location}}

Business Description:
{{business_description}}

Key Objectives:
{{business_objectives}}
```

### Supported Field Types

The system supports:
- Text fields
- Number fields
- Date fields (as strings)
- Lists/arrays (converted to strings)
- Nested objects (converted to strings)

For complex data structures, the value will be converted to a string representation.

