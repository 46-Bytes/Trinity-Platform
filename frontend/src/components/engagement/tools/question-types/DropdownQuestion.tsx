import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface DropdownQuestionProps {
  question: any;
  value: any;
  onChange: (value: any) => void;
  allResponses?: Record<string, any>;
  onFieldChange?: (fieldName: string, value: any) => void;
}

export function DropdownQuestion({ question, value, onChange, allResponses = {}, onFieldChange }: DropdownQuestionProps) {
  // Generate choices from range if choicesMin/choicesMax are provided
  let choices: (string | { value: string; text: string })[] = question.choices || [];
  
  if (question.choicesMin !== undefined && question.choicesMax !== undefined) {
    choices = [];
    for (let i = question.choicesMin; i <= question.choicesMax; i++) {
      choices.push(String(i));
    }
  }

  // Helper to normalize choices - handle both string and object formats
  const normalizeChoice = (choice: string | { value: string; text: string }) => {
    if (typeof choice === 'string') {
      return { value: choice, text: choice };
    }
    return choice;
  };

  // Field name for storing the "other" description
  const otherFieldName = `${question.name}_other`;
  const otherValue = allResponses[otherFieldName] || '';

  // Handle dropdown value change
  const handleDropdownChange = (newValue: string) => {
    onChange(newValue);
    // Clear the "other" field if a non-other option is selected
    if (newValue !== 'other' && otherValue && onFieldChange) {
      onFieldChange(otherFieldName, '');
    }
  };

  // Handle "other" description change
  const handleOtherChange = (otherDescription: string) => {
    if (onFieldChange) {
      onFieldChange(otherFieldName, otherDescription);
    }
  };

  const isOtherSelected = value === 'other';

  return (
    <div className="space-y-2">
      <Label>{question.title}</Label>
      {question.description && (
        <p className="text-sm text-muted-foreground">{question.description}</p>
      )}
      
      <Select value={value || ""} onValueChange={handleDropdownChange}>
        <SelectTrigger>
          <SelectValue placeholder="Select an option" />
        </SelectTrigger>
        <SelectContent>
          {choices.map((choice, index) => {
            const normalized = normalizeChoice(choice);
            const choiceValue = normalized.value;
            const choiceText = normalized.text;
            const choiceKey = typeof choice === 'string' ? choice : choiceValue;
            
            return (
              <SelectItem key={choiceKey || index} value={String(choiceValue)}>
                {choiceText}
              </SelectItem>
            );
          })}
          {question.showOtherItem && (
            <SelectItem value="other">Other (describe)</SelectItem>
          )}
        </SelectContent>
      </Select>

      {/* Show text input when "other" is selected */}
      {isOtherSelected && question.showOtherItem && (
        <div className="mt-3">
          <Label htmlFor={otherFieldName}>
            {question.otherText || "Please describe"}
          </Label>
          <Input
            id={otherFieldName}
            type="text"
            value={otherValue}
            onChange={(e) => handleOtherChange(e.target.value)}
            placeholder={question.otherPlaceholder || "Please describe"}
          />
        </div>
      )}
    </div>
  );
}