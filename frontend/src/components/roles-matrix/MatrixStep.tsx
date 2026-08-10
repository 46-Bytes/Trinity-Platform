import { useEffect, useState } from 'react';
import { useAppDispatch } from '@/store/hooks';
import {
  generateMatrix,
  saveMatrixRows,
  exportMatrix,
  type MatrixRow,
  type RolesMatrix,
} from '@/store/slices/rolesMatrixReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ArrowLeft,
  Copy,
  Download,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';

interface MatrixStepProps {
  matrix: RolesMatrix;
  isGenerating: boolean;
  isSaving: boolean;
  isExporting: boolean;
  onBack: () => void;
}

/** Column order matches the Job Roles tab exactly. */
const COLUMNS: { key: keyof MatrixRow; label: string; width: string }[] = [
  { key: 'name', label: 'Name', width: 'min-w-[9rem]' },
  { key: 'role_description', label: 'Role Descriptions', width: 'min-w-[16rem]' },
  { key: 'time', label: 'Time', width: 'min-w-[9rem]' },
  { key: 'priorities', label: 'Priorities', width: 'min-w-[8rem]' },
  { key: 'retain', label: 'Retain', width: 'min-w-[5rem]' },
  { key: 'gain', label: 'Gain', width: 'min-w-[5rem]' },
  { key: 'lose', label: 'Lose', width: 'min-w-[5rem]' },
  { key: 'action', label: 'Action', width: 'min-w-[14rem]' },
  { key: 'resp', label: 'Resp', width: 'min-w-[7rem]' },
  { key: 'when', label: 'When', width: 'min-w-[8rem]' },
];

const EMPTY_ROW: MatrixRow = {
  name: '',
  role_description: '',
  time: '',
  priorities: '',
  retain: '',
  gain: '',
  lose: '',
  action: '',
  resp: '',
  when: '',
};

export function MatrixStep({ matrix, isGenerating, isSaving, isExporting, onBack }: MatrixStepProps) {
  const dispatch = useAppDispatch();
  const [rows, setRows] = useState<MatrixRow[]>([]);
  const [isDirty, setIsDirty] = useState(false);

  // Pull rows in from the server whenever the stored matrix changes
  useEffect(() => {
    setRows((matrix.matrix_rows || []).map((row) => ({ ...EMPTY_ROW, ...row })));
    setIsDirty(false);
  }, [matrix.matrix_rows]);

  const hasRows = rows.length > 0;

  const updateCell = (rowIndex: number, key: keyof MatrixRow, value: string) => {
    setRows((prev) => prev.map((row, i) => (i === rowIndex ? { ...row, [key]: value } : row)));
    setIsDirty(true);
  };

  const addRow = () => {
    setRows((prev) => [...prev, { ...EMPTY_ROW }]);
    setIsDirty(true);
  };

  const removeRow = (rowIndex: number) => {
    setRows((prev) => prev.filter((_, i) => i !== rowIndex));
    setIsDirty(true);
  };

  const handleGenerate = async () => {
    try {
      await dispatch(generateMatrix({ matrixId: matrix.id })).unwrap();
      toast.success('Matrix built');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to build the matrix');
    }
  };

  const handleSave = async () => {
    try {
      await dispatch(saveMatrixRows({ matrixId: matrix.id, rows })).unwrap();
      setIsDirty(false);
      toast.success('Matrix saved');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save the matrix');
    }
  };

  const handleExport = async () => {
    if (isDirty) {
      toast.error('Save your changes before exporting');
      return;
    }
    try {
      await dispatch(exportMatrix(matrix.id)).unwrap();
      toast.success('Matrix exported');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to export the matrix');
    }
  };

  const handleCopy = async () => {
    const header = COLUMNS.map((column) => column.label).join('\t');
    const body = rows
      .map((row) => COLUMNS.map((column) => row[column.key] ?? '').join('\t'))
      .join('\n');
    try {
      await navigator.clipboard.writeText(`${header}\n${body}`);
      toast.success('Matrix copied — paste straight into Excel');
    } catch {
      toast.error('Could not copy to the clipboard');
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Roles &amp; Responsibilities matrix</CardTitle>
          <CardDescription>
            One row per responsibility. The name appears on the first row of each person's block only,
            and blank cells are left blank.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <Button onClick={handleGenerate} disabled={isGenerating} className="flex-1">
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Building...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  {hasRows ? 'Rebuild matrix' : 'Build matrix'}
                </>
              )}
            </Button>
            {hasRows && (
              <>
                <Button variant="outline" onClick={handleSave} disabled={isSaving || !isDirty}>
                  {isSaving ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  Save changes
                </Button>
                <Button variant="outline" onClick={handleCopy}>
                  <Copy className="w-4 h-4 mr-2" />
                  Copy for Excel
                </Button>
                <Button onClick={handleExport} disabled={isExporting}>
                  {isExporting ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="w-4 h-4 mr-2" />
                  )}
                  Export .xlsx
                </Button>
              </>
            )}
          </div>

          {isDirty && (
            <p className="text-sm text-muted-foreground">
              You have unsaved changes. Save them before exporting.
            </p>
          )}
        </CardContent>
      </Card>

      {hasRows && (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    {COLUMNS.map((column) => (
                      <TableHead key={column.key} className={column.width}>
                        {column.label}
                      </TableHead>
                    ))}
                    <TableHead className="w-12" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row, rowIndex) => (
                    <TableRow key={rowIndex}>
                      {COLUMNS.map((column) => (
                        <TableCell key={column.key} className={column.width}>
                          <Input
                            value={row[column.key] ?? ''}
                            onChange={(e) => updateCell(rowIndex, column.key, e.target.value)}
                            className="h-9 border-transparent hover:border-input focus-visible:border-input"
                            aria-label={`${column.label} row ${rowIndex + 1}`}
                          />
                        </TableCell>
                      ))}
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeRow(rowIndex)}
                          aria-label={`Remove row ${rowIndex + 1}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="p-4 border-t">
              <Button variant="outline" size="sm" onClick={addRow}>
                <Plus className="w-4 h-4 mr-2" />
                Add row
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Button variant="outline" onClick={onBack} className="w-full sm:w-auto">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to extraction
      </Button>
    </div>
  );
}
