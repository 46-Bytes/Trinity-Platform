import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

interface CheckboxQuestionProps {
  question: {
    name: string;
    title: string;
    description?: string;
    choices: (string | { value: string; text: string })[];
  };
  value: string[] | null;
  onChange: (value: string[]) => void;
}

export function CheckboxQuestion({ question, value, onChange }: CheckboxQuestionProps) {
  // Normalize value to array
  const selectedValues = value || [];

  // Helper to normalize choices - handle both string and object formats
  const normalizeChoice = (choice: string | { value: string; text: string }) => {
    if (typeof choice === 'string') {
      return { value: choice, text: choice };
    }
    return choice;
  };

  const handleToggle = (choiceValue: string, checked: boolean) => {
    if (checked) {
      // Add to selection
      onChange([...selectedValues, choiceValue]);
    } else {
      // Remove from selection
      onChange(selectedValues.filter(v => v !== choiceValue));
    }
  };

  return (
    <div className="space-y-4 w-full min-w-0">
      <div>
        <Label className="break-words">{question.title}</Label>
        {question.description && (
          <p className="text-sm text-muted-foreground mt-1 break-words">{question.description}</p>
        )}
      </div>

      <div className="space-y-3">
        {question.choices.map((choice, index) => {
          const normalized = normalizeChoice(choice);
          const choiceValue = normalized.value;
          const choiceText = normalized.text;
          const isChecked = selectedValues.includes(choiceValue);

          return (
            <div key={choiceValue || index} className="flex items-center space-x-2">
              <Checkbox
                id={`${question.name}-${choiceValue}`}
                checked={isChecked}
                onCheckedChange={(checked) => handleToggle(choiceValue, checked as boolean)}
              />
              <Label
                htmlFor={`${question.name}-${choiceValue}`}
                className="font-normal cursor-pointer text-sm leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                {choiceText}
              </Label>
            </div>
          );
        })}
      </div>
    </div>
  );
}

