import { ChevronUp, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ModuleReorderControlsProps {
  disabled?: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

/** Advisor-only up/down reorder controls for a module card. */
export function ModuleReorderControls({ disabled, canMoveUp, canMoveDown, onMoveUp, onMoveDown }: ModuleReorderControlsProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-6 w-6"
        disabled={disabled || !canMoveUp}
        onClick={onMoveUp}
        aria-label="Move module up"
      >
        <ChevronUp className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-6 w-6"
        disabled={disabled || !canMoveDown}
        onClick={onMoveDown}
        aria-label="Move module down"
      >
        <ChevronDown className="h-4 w-4" />
      </Button>
    </div>
  );
}
