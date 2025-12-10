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
    <div className="space-y-4">
      <div>
        <Label className="text-lg font-semibold">{question.title}</Label>
        {question.description && (
          <p className="text-sm text-muted-foreground mt-1">{question.description}</p>
        )}
      </div>
      
      <div className="space-y-4 border rounded-lg p-4 bg-muted/30">
        {question.items.map((item) => (
          <div key={item.name} className="space-y-2">
            <Label htmlFor={`${question.name}-${item.name}`} className="font-medium">
              {item.title}
            </Label>
            <Input
              id={`${question.name}-${item.name}`}
              type="text"
              value={currentValue[item.name] || ''}
              onChange={(e) => handleItemChange(item.name, e.target.value)}
              placeholder={`Enter ${item.title.toLowerCase()}`}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

