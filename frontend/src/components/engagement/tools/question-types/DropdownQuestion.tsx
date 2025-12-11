import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function DropdownQuestion({ question, value, onChange }) {
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

  return (
    <div className="space-y-2">
      <Label>{question.title}</Label>
      {question.description && (
        <p className="text-sm text-muted-foreground">{question.description}</p>
      )}
      
      <Select value={value || ""} onValueChange={onChange}>
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
            <SelectItem value="other">Other</SelectItem>
          )}
        </SelectContent>
      </Select>
    </div>
  );
}