import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

export function TextQuestion({ question, value, onChange }) {
  return (
    <div className="space-y-2">
      <Label>{question.title}</Label>
      {question.description && (
        <p className="text-sm text-muted-foreground">{question.description}</p>
      )}
      
      <Input
        type={question.inputType || 'text'}
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        min={question.min}
        max={question.max}
        step={question.step}
        placeholder={question.placeholder}
      />
    </div>
  );
}

