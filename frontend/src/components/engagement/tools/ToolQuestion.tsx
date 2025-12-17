import {
  DropdownQuestion,
  TextQuestion,
  RadioGroupQuestion,
  MatrixDynamicQuestion,
  CommentQuestion,
  MultipleTextQuestion,
  FileQuestion,
  BooleanQuestion,
  CheckboxQuestion,
} from './question-types';

interface ToolQuestionProps {
  question: any;
  value: any;
  onChange: (value: any) => void;
  allResponses: Record<string, any>;
  diagnosticId?: string;
}

// Helper to evaluate conditional visibility
function evaluateCondition(condition: string, responses: Record<string, any>): boolean {
  // Handle complex AND/OR conditions
  // Example: "{sells_physical_products} == 'Yes' and ({do_you_sell_online_via_your_own_ecommerce_store} == 'Yes' or {sell_on_marketplaces} == 'Yes')"
  if (condition.includes(' and ') || condition.includes(' or ')) {
    // Split by 'and' first (higher precedence)
    if (condition.includes(' and ')) {
      const parts = condition.split(' and ');
      return parts.every(part => evaluateCondition(part.trim(), responses));
    }
    // Split by 'or'
    if (condition.includes(' or ')) {
      const parts = condition.split(' or ');
      return parts.some(part => evaluateCondition(part.trim(), responses));
    }
  }
  
  // Remove parentheses if present
  const cleanCondition = condition.replace(/^\(|\)$/g, '').trim();
  
  // Handle == comparison: "{business_founded_by_you} == 'No'"
  const eqMatch = cleanCondition.match(/\{(\w+)\}\s*==\s*'([^']+)'/);
  if (eqMatch) {
    const [, fieldName, expectedValue] = eqMatch;
    return responses[fieldName] === expectedValue;
  }
  
  // Handle != comparison: "{senior_mgmt_strategy_review_frequency} != 'Never'"
  const neqMatch = cleanCondition.match(/\{(\w+)\}\s*!=\s*'([^']+)'/);
  if (neqMatch) {
    const [, fieldName, expectedValue] = neqMatch;
    return responses[fieldName] !== expectedValue;
  }
  
  // Handle <> comparison (not equal): "{team_position_descriptions} <> 'No one'"
  const neqMatch2 = cleanCondition.match(/\{(\w+)\}\s*<>\s*'([^']+)'/);
  if (neqMatch2) {
    const [, fieldName, expectedValue] = neqMatch2;
    return responses[fieldName] !== expectedValue;
  }
  
  // Handle >= comparisons: "{leases_properties} >= 2"
  const gteMatch = cleanCondition.match(/\{(\w+)\}\s*>=\s*(\d+)/);
  if (gteMatch) {
    const [, fieldName, minValue] = gteMatch;
    const fieldValue = parseInt(responses[fieldName]) || 0;
    return fieldValue >= parseInt(minValue);
  }
  
  // Handle > comparisons: "{retail_store_count} > 1"
  const gtMatch = cleanCondition.match(/\{(\w+)\}\s*>\s*(\d+)/);
  if (gtMatch) {
    const [, fieldName, minValue] = gtMatch;
    const fieldValue = parseInt(responses[fieldName]) || 0;
    return fieldValue > parseInt(minValue);
  }
  
  // Handle < comparisons: "{busy_rating} < 86"
  const ltMatch = cleanCondition.match(/\{(\w+)\}\s*<\s*(\d+)/);
  if (ltMatch) {
    const [, fieldName, maxValue] = ltMatch;
    const fieldValue = parseInt(responses[fieldName]) || 0;
    return fieldValue < parseInt(maxValue);
  }
  
  // Handle 'contains' condition: "{warehousing_and_logistics_mgmt_type} contains 'external'"
  const containsMatch = cleanCondition.match(/\{(\w+)\}\s+contains\s+'([^']+)'/);
  if (containsMatch) {
    const [, fieldName, searchValue] = containsMatch;
    const fieldValue = responses[fieldName];
    if (typeof fieldValue === 'string') {
      return fieldValue.toLowerCase().includes(searchValue.toLowerCase());
    }
    return false;
  }

  // Handle notempty: "{performance_issues_description} notempty"
  const notEmptyMatch = cleanCondition.match(/\{(\w+)\}\s*notempty/i);
  if (notEmptyMatch) {
    const [, fieldName] = notEmptyMatch;
    const value = responses[fieldName];
    return value !== undefined && value !== null && String(value).trim().length > 0;
  }

  // Handle allof list check: "{financial_performance_since_acquisition} allof ['Same','Worse']"
  const allOfMatch = cleanCondition.match(/\{(\w+)\}\s*allof\s*\[(.+)\]/i);
  if (allOfMatch) {
    const [, fieldName, listRaw] = allOfMatch;
    const expectedValues = listRaw
      .split(',')
      .map((s) => s.replace(/['"\[\]]/g, '').trim())
      .filter(Boolean);
    const value = responses[fieldName];
    if (Array.isArray(value)) {
      return expectedValues.every((v) => value.includes(v));
    }
    return expectedValues.includes(String(value));
  }
  
  return true;
}

export function ToolQuestion({ question, value, onChange, allResponses, diagnosticId }: ToolQuestionProps) {
  // Check conditional visibility
  if (question.visibleIf) {
    const isVisible = evaluateCondition(question.visibleIf, allResponses);
    if (!isVisible) return null;
  }

  // Render based on question type
  switch (question.type) {
    case 'dropdown':
      return <DropdownQuestion question={question} value={value} onChange={onChange} />;
    
    case 'text':
      return <TextQuestion question={question} value={value} onChange={onChange} />;
    
    case 'radiogroup':
      return <RadioGroupQuestion question={question} value={value} onChange={onChange} />;
    
    case 'matrixdynamic':
      return <MatrixDynamicQuestion question={question} value={value} onChange={onChange} />;
    
    case 'comment':
      return <CommentQuestion question={question} value={value} onChange={onChange} />;
    
    case 'multipletext':
      return <MultipleTextQuestion question={question} value={value} onChange={onChange} />;
    
    case 'file':
      return (
        <FileQuestion
          question={question}
          value={value}
          onChange={onChange}
          diagnosticId={diagnosticId}
        />
      );
    
    case 'boolean':
      return <BooleanQuestion question={question} value={value} onChange={onChange} />;
    
    case 'checkbox':
      return <CheckboxQuestion question={question} value={value} onChange={onChange} />;
    
    default:
      return <div className="p-4 border border-yellow-500 bg-yellow-50 rounded-md">Unsupported question type: {question.type}</div>;
  }
}