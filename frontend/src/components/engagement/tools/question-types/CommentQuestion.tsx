import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function CommentQuestion({ question, value, onChange }) {
  return (
    <div className="space-y-2 w-full min-w-0">
      <Label className="break-words">{question.title}</Label>
      {question.description && (
        <p className="text-sm text-muted-foreground break-words">{question.description}</p>
      )}
      
      <Textarea
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        maxLength={question.maxLength}
        placeholder={question.placeholder || "Enter your response..."}
        className="min-h-[100px] focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-offset-0"
      />
      {question.maxLength && (
        <p className="text-xs text-muted-foreground text-right">
          {(value || '').length} / {question.maxLength}
        </p>
      )}
    </div>
  );
}

