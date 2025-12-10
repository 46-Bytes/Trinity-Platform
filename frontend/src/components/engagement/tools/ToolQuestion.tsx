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
}

// Helper to evaluate conditional visibility
function evaluateCondition(condition: string, responses: Record<string, any>): boolean {
  // Example: "{business_founded_by_you} == 'No'"
  // Parse and evaluate the condition
  const match = condition.match(/\{(\w+)\}\s*==\s*'([^']+)'/);
  if (match) {
    const [, fieldName, expectedValue] = match;
    return responses[fieldName] === expectedValue;
  }
  
  // Handle >= comparisons: "{leases_properties} >= 2"
  const numMatch = condition.match(/\{(\w+)\}\s*>=\s*(\d+)/);
  if (numMatch) {
    const [, fieldName, minValue] = numMatch;
    const fieldValue = parseInt(responses[fieldName]) || 0;
    return fieldValue >= parseInt(minValue);
  }
  
  return true;
}

export function ToolQuestion({ question, value, onChange, allResponses }: ToolQuestionProps) {
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
      return <FileQuestion question={question} value={value} onChange={onChange} />;
    
    case 'boolean':
      return <BooleanQuestion question={question} value={value} onChange={onChange} />;
    
    case 'checkbox':
      return <CheckboxQuestion question={question} value={value} onChange={onChange} />;
    
    default:
      return <div className="p-4 border border-yellow-500 bg-yellow-50 rounded-md">Unsupported question type: {question.type}</div>;
  }
}