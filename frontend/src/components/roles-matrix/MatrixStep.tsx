import { useEffect, useMemo, useState } from 'react';
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
import { Label } from '@/components/ui/label';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
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

/** Same columns, minus Name — Name is shown once per role as the accordion header instead. */
const DETAIL_COLUMNS = COLUMNS.filter((column) => column.key !== 'name');

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

  /**
   * Group the flat row list into one block per role, splitting wherever a row
   * carries a name — mirrors the existing "name on first row of the block" convention.
   */
  const roleGroups = useMemo(() => {
    const groups: { key: string; indices: number[] }[] = [];
    rows.forEach((row, index) => {
      if (row.name?.trim() || groups.length === 0) {
        groups.push({ key: `role-${index}`, indices: [index] });
      } else {
        groups[groups.length - 1].indices.push(index);
      }
    });
    return groups;
  }, [rows]);

  // Look up each role's job title from the staff list gathered during Inputs.
  const titleByName = useMemo(() => {
    const map = new Map<string, string>();
    (matrix.staff || []).forEach((member) => {
      if (member.name && member.role_title) {
        map.set(member.name.trim().toLowerCase(), member.role_title);
      }
    });
    return map;
  }, [matrix.staff]);

  const updateCell = (rowIndex: number, key: keyof MatrixRow, value: string) => {
    setRows((prev) => prev.map((row, i) => (i === rowIndex ? { ...row, [key]: value } : row)));
    setIsDirty(true);
  };

  /**
   * Insert directly beneath a row so the new responsibility stays inside that
   */
  const insertRowBelow = (rowIndex: number) => {
    setRows((prev) => [
      ...prev.slice(0, rowIndex + 1),
      { ...EMPTY_ROW },
      ...prev.slice(rowIndex + 1),
    ]);
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
                <Button
                  onClick={handleExport}
                  disabled={isExporting || isDirty}
                  title={isDirty ? 'Save your changes before exporting' : undefined}
                >
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
          <CardContent className="pt-6">
            <Accordion type="multiple" className="w-full space-y-3">
              {roleGroups.map((group) => {
                const nameIndex = group.indices[0];
                const name = rows[nameIndex]?.name?.trim() || '';
                const title = name ? titleByName.get(name.toLowerCase()) : undefined;
                const displayLabel = title || name || 'Unnamed role';
                return (
                  <AccordionItem
                    key={group.key}
                    value={group.key}
                    className="border rounded-md bg-background px-4"
                  >
                    <AccordionTrigger className="hover:no-underline">
                      <span className="font-semibold text-base text-foreground truncate pr-3">
                        {displayLabel}
                      </span>
                    </AccordionTrigger>
                    <AccordionContent className="space-y-4 p-2 pt-4">
                      <div className="max-w-sm">
                        <Label htmlFor={`role-name-${nameIndex}`}>Name</Label>
                        <Input
                          id={`role-name-${nameIndex}`}
                          value={rows[nameIndex]?.name ?? ''}
                          onChange={(e) => updateCell(nameIndex, 'name', e.target.value)}
                          className="h-9 mt-1"
                        />
                      </div>

                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              {DETAIL_COLUMNS.map((column) => (
                                <TableHead key={column.key} className={column.width}>
                                  {column.label}
                                </TableHead>
                              ))}
                              <TableHead className="w-24" />
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {group.indices.map((rowIndex) => (
                              <TableRow key={rowIndex}>
                                {DETAIL_COLUMNS.map((column) => (
                                  <TableCell key={column.key} className={column.width}>
                                    <Input
                                      value={rows[rowIndex][column.key] ?? ''}
                                      onChange={(e) => updateCell(rowIndex, column.key, e.target.value)}
                                      className="h-9 border-black"
                                      aria-label={`${column.label} row ${rowIndex + 1}`}
                                    />
                                  </TableCell>
                                ))}
                                <TableCell className="w-24">
                                  <div className="flex items-center gap-1">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => insertRowBelow(rowIndex)}
                                      aria-label={`Insert a row below row ${rowIndex + 1}`}
                                      title="Add a responsibility below this row"
                                    >
                                      <Plus className="w-4 h-4" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => removeRow(rowIndex)}
                                      aria-label={`Remove row ${rowIndex + 1}`}
                                      title="Remove this row"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
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
