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
    <div className="space-y-4">
      <div>
        <Label className="text-lg font-semibold">{question.title}</Label>
        {question.description && (
          <p className="text-sm text-muted-foreground mt-1">{question.description}</p>
        )}
      </div>

      <div className="border rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">#</TableHead>
              {question.columns.map((column) => (
                <TableHead key={column.name}>{column.title}</TableHead>
              ))}
              <TableHead className="w-16">Action</TableHead>
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
                  <TableCell className="font-medium">{rowIndex + 1}</TableCell>
                  {question.columns.map((column) => (
                    <TableCell key={column.name}>
                      <Input
                        type="text"
                        value={row[column.name] || ''}
                        onChange={(e) => handleCellChange(rowIndex, column.name, e.target.value)}
                        placeholder={`Enter ${column.title.toLowerCase()}`}
                        className="min-w-[150px]"
                      />
                    </TableCell>
                  ))}
                  <TableCell>
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

