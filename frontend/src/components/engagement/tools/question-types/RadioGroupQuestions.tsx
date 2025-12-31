import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

export function RadioGroupQuestion({ question, value, onChange }) {
  // Helper to normalize choices - handle both string and object formats
  const normalizeChoice = (choice: string | { value: string; text: string }) => {
    if (typeof choice === 'string') {
      return { value: choice, text: choice };
    }
    return choice;
  };

  return (
    <div className="space-y-3 w-full min-w-0">
      <Label className="break-words">{question.title}</Label>
      {question.description && (
        <p className="text-sm text-muted-foreground break-words">{question.description}</p>
      )}
      
      <RadioGroup value={value || ""} onValueChange={onChange}>
        {question.choices.map((choice, index) => {
          const normalized = normalizeChoice(choice);
          const choiceValue = normalized.value;
          const choiceText = normalized.text;
          const choiceKey = typeof choice === 'string' ? choice : choiceValue;
          
          return (
            <div key={choiceKey || index} className="flex items-center space-x-2">
              <RadioGroupItem value={String(choiceValue)} id={`${question.name}-${choiceValue}`} />
              <Label htmlFor={`${question.name}-${choiceValue}`} className="font-normal cursor-pointer">
                {choiceText}
              </Label>
            </div>
          );
        })}
        {question.showNoneItem && (
          <div className="flex items-center space-x-2">
            <RadioGroupItem value="none" id={`${question.name}-none`} />
            <Label htmlFor={`${question.name}-none`} className="font-normal cursor-pointer">
              None
            </Label>
          </div>
        )}
      </RadioGroup>
    </div>
  );
}

