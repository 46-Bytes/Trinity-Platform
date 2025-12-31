import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";

interface BooleanQuestionProps {
  question: {
    name: string;
    title: string;
    description?: string;
  };
  value: boolean | string | null;
  onChange: (value: boolean | string) => void;
}

export function BooleanQuestion({ question, value, onChange }: BooleanQuestionProps) {
  // Normalize value to string for radio buttons
  const normalizedValue = value === true || value === "Yes" || value === "yes" ? "Yes" : 
                          value === false || value === "No" || value === "no" ? "No" : "";

  const handleChange = (newValue: string) => {
    // Convert to boolean if needed, or keep as string
    if (newValue === "Yes") {
      onChange(true);
    } else if (newValue === "No") {
      onChange(false);
    } else {
      onChange(newValue);
    }
  };

  return (
    <div className="space-y-3 w-full min-w-0">
      <Label className="break-words">{question.title}</Label>
      {question.description && (
        <p className="text-sm text-muted-foreground break-words">{question.description}</p>
      )}
      
      <RadioGroup value={normalizedValue} onValueChange={handleChange}>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="Yes" id={`${question.name}-yes`} />
          <Label htmlFor={`${question.name}-yes`} className="font-normal cursor-pointer">
            Yes
          </Label>
        </div>
        <div className="flex items-center space-x-2">
          <RadioGroupItem value="No" id={`${question.name}-no`} />
          <Label htmlFor={`${question.name}-no`} className="font-normal cursor-pointer">
            No
          </Label>
        </div>
      </RadioGroup>
    </div>
  );
}

