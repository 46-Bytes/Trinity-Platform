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
  // Handle equality comparisons: "{business_founded_by_you} == 'No'"
  const equalityMatch = condition.match(/\{(\w+)\}\s*==\s*'([^']+)'/);
  if (equalityMatch) {
    const [, fieldName, expectedValue] = equalityMatch;
    return responses[fieldName] === expectedValue;
  }
  
  // Handle not equal comparisons with <>: "{key_reports_review_frequency} <> 'Never'"
  const notEqualAngleMatch = condition.match(/\{(\w+)\}\s*<>\s*'([^']+)'/);
  if (notEqualAngleMatch) {
    const [, fieldName, expectedValue] = notEqualAngleMatch;
    return responses[fieldName] !== expectedValue;
  }
  
  // Handle not equal comparisons with !=: "{senior_mgmt_strategy_review_frequency} != 'Never'"
  const notEqualMatch = condition.match(/\{(\w+)\}\s*!=\s*'([^']+)'/);
  if (notEqualMatch) {
    const [, fieldName, expectedValue] = notEqualMatch;
    return responses[fieldName] !== expectedValue;
  }
  
  // Handle >= comparisons: "{leases_properties} >= 2"
  const greaterOrEqualMatch = condition.match(/\{(\w+)\}\s*>=\s*(\d+)/);
  if (greaterOrEqualMatch) {
    const [, fieldName, minValue] = greaterOrEqualMatch;
    const rawValue = responses[fieldName];
    // Only evaluate if field has a value (not undefined/null/empty string)
    if (rawValue === undefined || rawValue === null || rawValue === '') return false;
    const fieldValue = parseInt(rawValue);
    return !isNaN(fieldValue) && fieldValue >= parseInt(minValue);
  }
  
  // Handle > comparisons: "{retail_store_count} > 1"
  const greaterThanMatch = condition.match(/\{(\w+)\}\s*>\s*(\d+)/);
  if (greaterThanMatch) {
    const [, fieldName, minValue] = greaterThanMatch;
    const rawValue = responses[fieldName];
    // Only evaluate if field has a value (not undefined/null/empty string)
    if (rawValue === undefined || rawValue === null || rawValue === '') return false;
    const fieldValue = parseInt(rawValue);
    return !isNaN(fieldValue) && fieldValue > parseInt(minValue);
  }
  
  // Handle < comparisons: "{sales_marketing_satisfaction} < 6"
  const lessThanMatch = condition.match(/\{(\w+)\}\s*<\s*(\d+)/);
  if (lessThanMatch) {
    const [, fieldName, maxValue] = lessThanMatch;
    const rawValue = responses[fieldName];
    // Only evaluate if field has a value (not undefined/null/empty string)
    if (rawValue === undefined || rawValue === null || rawValue === '') return false;
    const fieldValue = parseInt(rawValue);
    return !isNaN(fieldValue) && fieldValue < parseInt(maxValue);
  }
  
  // Handle <= comparisons: "{some_field} <= 5"
  const lessOrEqualMatch = condition.match(/\{(\w+)\}\s*<=\s*(\d+)/);
  if (lessOrEqualMatch) {
    const [, fieldName, maxValue] = lessOrEqualMatch;
    const rawValue = responses[fieldName];
    // Only evaluate if field has a value (not undefined/null/empty string)
    if (rawValue === undefined || rawValue === null || rawValue === '') return false;
    const fieldValue = parseInt(rawValue);
    return !isNaN(fieldValue) && fieldValue <= parseInt(maxValue);
  }
  
  // Handle allof comparisons: "{field} allof ['Value1', 'Value2']"
  // Checks if field value matches ANY value in the array
  const allofMatch = condition.match(/\{(\w+)\}\s+allof\s+\[(.+)\]/);
  if (allofMatch) {
    const [, fieldName, valuesStr] = allofMatch;
    const actualValue = responses[fieldName];
    // Parse the array values - they're quoted strings like 'Value1', 'Value2'
    const expectedValues = valuesStr.match(/'([^']+)'/g)?.map(v => v.slice(1, -1)) || [];
    return expectedValues.includes(actualValue);
  }
  
  // Handle contains comparisons: "{field} contains 'text'"
  // Checks if field value contains the specified substring
  const containsMatch = condition.match(/\{(\w+)\}\s+contains\s+'([^']+)'/);
  if (containsMatch) {
    const [, fieldName, searchText] = containsMatch;
    const actualValue = responses[fieldName] || '';
    return String(actualValue).includes(searchText);
  }
  
  // If no pattern matches, default to showing the question (safer than hiding)
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