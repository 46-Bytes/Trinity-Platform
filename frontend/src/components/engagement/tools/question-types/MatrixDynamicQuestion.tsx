import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Plus, Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function MatrixDynamicQuestion({ question, value, onChange }) {
  // value is an array of objects, each representing a row
  const currentValue = value || [];

  const handleAddRow = () => {
    const newRow = {};
    question.columns.forEach((col) => {
      newRow[col.name] = '';
    });
    onChange([...currentValue, newRow]);
  };

  const handleRemoveRow = (index: number) => {
    const newValue = currentValue.filter((_, i) => i !== index);
    onChange(newValue);
  };

  const handleCellChange = (rowIndex: number, columnName: string, cellValue: string) => {
    const newValue = [...currentValue];
    newValue[rowIndex] = {
      ...newValue[rowIndex],
      [columnName]: cellValue,
    };
    onChange(newValue);
  };

  return (
    <div className="space-y-4 w-full" style={{ maxWidth: '100%', width: '100%', boxSizing: 'border-box' }}>
      <div>
        <Label className="text-lg font-semibold break-words">{question.title}</Label>
        {question.description && (
          <p className="text-sm text-muted-foreground mt-1 break-words">{question.description}</p>
        )}
      </div>

      <div className="w-full" style={{ maxWidth: '100%', width: '100%', overflow: 'visible', boxSizing: 'border-box' }}>
        <div className="border rounded-lg overflow-x-auto w-full" style={{ maxWidth: '100%', width: '100%', WebkitOverflowScrolling: 'touch', boxSizing: 'border-box' }}>
          <Table style={{ width: 'max-content', minWidth: '100%' }}>
            <TableHeader>
              <TableRow>
                <TableHead className="min-w-[3rem] px-2" style={{ width: '48px' }}>#</TableHead>
                {question.columns.map((column) => (
                  <TableHead key={column.name} className="px-2 break-words" style={{ minWidth: '120px', maxWidth: '200px', whiteSpace: 'normal', wordWrap: 'break-word' }}>{column.title}</TableHead>
                ))}
                <TableHead className="min-w-[4rem] px-2" style={{ width: '64px' }}>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {currentValue.length === 0 ? (
                <TableRow>
                  <TableCell 
                    colSpan={question.columns.length + 2} 
                    className="text-center text-muted-foreground py-8"
                  >
                    No entries yet. Click "Add Row" to start.
                  </TableCell>
                </TableRow>
              ) : (
                currentValue.map((row, rowIndex) => (
                  <TableRow key={rowIndex}>
                    <TableCell className="font-medium w-12">{rowIndex + 1}</TableCell>
                      {question.columns.map((column) => (
                        <TableCell key={column.name} className="px-2" style={{ minWidth: '120px', maxWidth: '200px' }}>
                          <Input
                            type="text"
                            value={row[column.name] || ''}
                            onChange={(e) => handleCellChange(rowIndex, column.name, e.target.value)}
                            placeholder={`Enter ${column.title.toLowerCase()}`}
                            className="w-full"
                          />
                        </TableCell>
                      ))}
                    <TableCell className="w-16">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveRow(rowIndex)}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={handleAddRow}
        className="w-full"
      >
        <Plus className="h-4 w-4 mr-2" />
        Add Row
      </Button>
    </div>
  );
}

