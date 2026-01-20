import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

export function MultipleTextQuestion({ question, value, onChange }) {
  // value is an object with keys matching item names
  const currentValue = value || {};

  const handleItemChange = (itemName: string, itemValue: string) => {
    onChange({
      ...currentValue,
      [itemName]: itemValue,
    });
  };

  return (
    <div className="space-y-4 w-full min-w-0">
      <div>
        <Label className="text-lg font-semibold break-words">{question.title}</Label>
        {question.description && (
          <p className="text-sm text-muted-foreground mt-1 break-words">{question.description}</p>
        )}
      </div>
      
      <div className="space-y-4 border rounded-lg p-4 bg-muted/30 w-full min-w-0">
        {question.items.map((item) => (
          <div key={item.name} className="space-y-2 w-full min-w-0">
            <Label htmlFor={`${question.name}-${item.name}`} className="font-medium break-words">
              {item.title}
            </Label>
            <Input
              id={`${question.name}-${item.name}`}
              type="text"
              value={currentValue[item.name] || ''}
              onChange={(e) => handleItemChange(item.name, e.target.value)}
              placeholder={`Enter ${item.title.toLowerCase()}`}
              className="focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-offset-0"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

