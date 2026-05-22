import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { BlockEditor } from './BlockEditor';
import { ChevronUp, ChevronDown, Pencil, X, Check } from 'lucide-react';
import type { EmployeePlanSection } from '@/store/slices/strategicBusinessPlanReducer';

interface EmployeeDocumentEditorProps {
  sections: EmployeePlanSection[];
  onChange: (sections: EmployeePlanSection[]) => void;
  onSave: (sections: EmployeePlanSection[]) => void;
  isSaving: boolean;
}

export function EmployeeDocumentEditor({ sections, onChange, onSave, isSaving }: EmployeeDocumentEditorProps) {
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [draftContent, setDraftContent] = useState<string>('');

  const move = (index: number, direction: -1 | 1) => {
    const next = index + direction;
    if (next < 0 || next >= sections.length) return;
    const updated = [...sections];
    [updated[index], updated[next]] = [updated[next], updated[index]];
    onChange(updated);
  };

  const toggleIncluded = (key: string) => {
    onChange(sections.map((s) => (s.key === key ? { ...s, included: !s.included } : s)));
  };

  const startEdit = (section: EmployeePlanSection) => {
    setEditingKey(section.key);
    setDraftContent(section.content);
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setDraftContent('');
  };

  const saveEdit = (key: string) => {
    onChange(sections.map((s) => (s.key === key ? { ...s, content: draftContent } : s)));
    setEditingKey(null);
    setDraftContent('');
  };

  return (
    <div className="space-y-3">
      {sections.map((section, index) => (
        <div
          key={section.key}
          className="border rounded-lg overflow-hidden"
        >
          {/* Section header row */}
          <div className="flex items-center gap-3 px-4 py-3 bg-muted/30">
            <Checkbox
              id={`include-${section.key}`}
              checked={section.included}
              onCheckedChange={() => toggleIncluded(section.key)}
            />
            <label
              htmlFor={`include-${section.key}`}
              className="flex-1 text-sm font-medium cursor-pointer select-none"
            >
              {section.title}
            </label>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                disabled={index === 0}
                onClick={() => move(index, -1)}
                type="button"
              >
                <ChevronUp className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                disabled={index === sections.length - 1}
                onClick={() => move(index, 1)}
                type="button"
              >
                <ChevronDown className="h-4 w-4" />
              </Button>
              {editingKey === section.key ? (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-green-600 hover:text-green-700"
                    onClick={() => saveEdit(section.key)}
                    type="button"
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    onClick={cancelEdit}
                    type="button"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => startEdit(section)}
                  type="button"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          {/* Inline editor — shown when this section is being edited */}
          {editingKey === section.key && (
            <div className="p-4 border-t bg-background">
              <BlockEditor
                html={draftContent}
                onChange={setDraftContent}
              />
            </div>
          )}
        </div>
      ))}

      <div className="flex justify-end pt-2">
        <Button
          onClick={() => {
            let finalSections = sections;
            if (editingKey) {
              finalSections = sections.map((s) => s.key === editingKey ? { ...s, content: draftContent } : s);
              onChange(finalSections);
              setEditingKey(null);
              setDraftContent('');
            }
            onSave(finalSections);
          }}
          disabled={isSaving}
        >
          {isSaving ? 'Saving…' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}
