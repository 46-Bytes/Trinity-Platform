/**
 * Step 5: Snapshot Table Component
 * Displays the Key Findings & Recommendations Snapshot table
 */
import React, { useState, useEffect, useRef } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Pencil, Save, X, RefreshCw, ChevronUp, ChevronDown, Plus, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface SnapshotRow {
  rank: number;
  priority_area: string;
  key_finding: string;
  recommendation: string;
}

export interface SnapshotTable {
  title: string;
  rows: SnapshotRow[];
}

interface SnapshotTableStepProps {
  projectId: string;
  onComplete: (snapshotTable: SnapshotTable) => void;
  onBack: () => void;
  className?: string;
  onLoadingStateChange?: (isLoading: boolean) => void;
}

export function SnapshotTableStep({ projectId, onComplete, onBack, className, onLoadingStateChange }: SnapshotTableStepProps) {
  const [snapshotTable, setSnapshotTable] = useState<SnapshotTable | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<SnapshotRow | null>(null);
  // Use ref to store the callback to avoid infinite loops
  const onLoadingStateChangeRef = useRef(onLoadingStateChange);
  useEffect(() => {
    onLoadingStateChangeRef.current = onLoadingStateChange;
  }, [onLoadingStateChange]);

  // Load existing snapshot table on mount
  useEffect(() => {
    const loadExistingData = async () => {
      setIsInitialLoading(true);
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          credentials: 'include',
        });

        if (response.ok) {
          const result = await response.json();
          const project = result.project;
          
          // Load existing snapshot table if available
          // snapshot_table can be: {snapshot_table: {...}} or just the object
          if (project?.snapshot_table) {
            const tableData = project.snapshot_table.snapshot_table || project.snapshot_table;
            if (tableData && tableData.rows && Array.isArray(tableData.rows) && tableData.rows.length > 0) {
              setSnapshotTable(tableData);
            }
          }
        }
      } catch (err) {
        console.error('Failed to load existing snapshot table:', err);
      } finally {
        setIsInitialLoading(false);
      }
    };

    if (projectId) {
      loadExistingData();
    }
  }, [projectId]);

  // Notify parent of loading state changes
  useEffect(() => {
    if (onLoadingStateChangeRef.current) {
      onLoadingStateChangeRef.current(isLoading || isGenerating);
    }
  }, [isLoading, isGenerating]);

  // Generate snapshot table
  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE_URL}/api/poc/${projectId}/step5/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to generate snapshot table' }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const result = await response.json();
      const tableData = result.snapshot_table?.snapshot_table || result.snapshot_table || { title: 'Key Findings & Recommendations Snapshot', rows: [] };
      setSnapshotTable(tableData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate snapshot table');
    } finally {
      setIsGenerating(false);
    }
  };

  // Confirm and proceed
  const handleConfirm = async () => {
    if (!snapshotTable) return;
    setIsLoading(true);
    onComplete(snapshotTable);
    setIsLoading(false);
  };

  // Start editing row
  const startEdit = (index: number) => {
    if (snapshotTable) {
      setEditingIndex(index);
      setEditForm({ ...snapshotTable.rows[index] });
    }
  };

  // Save edit
  const saveEdit = () => {
    if (editingIndex !== null && editForm && snapshotTable) {
      const updatedRows = [...snapshotTable.rows];
      updatedRows[editingIndex] = editForm;
      setSnapshotTable({ ...snapshotTable, rows: updatedRows });
      setEditingIndex(null);
      setEditForm(null);
    }
  };

  // Cancel edit
  const cancelEdit = () => {
    setEditingIndex(null);
    setEditForm(null);
  };

  const renumberRanks = (rows: SnapshotRow[]) =>
    rows.map((r, i) => ({ ...r, rank: i + 1 }));

  const moveRowUp = (index: number) => {
    if (index <= 0 || !snapshotTable) return;
    const rows = [...snapshotTable.rows];
    [rows[index - 1], rows[index]] = [rows[index], rows[index - 1]];
    setSnapshotTable({ ...snapshotTable, rows: renumberRanks(rows) });
    if (editingIndex === index) setEditingIndex(index - 1);
    else if (editingIndex === index - 1) setEditingIndex(index);
  };

  const moveRowDown = (index: number) => {
    if (!snapshotTable || index >= snapshotTable.rows.length - 1) return;
    const rows = [...snapshotTable.rows];
    [rows[index], rows[index + 1]] = [rows[index + 1], rows[index]];
    setSnapshotTable({ ...snapshotTable, rows: renumberRanks(rows) });
    if (editingIndex === index) setEditingIndex(index + 1);
    else if (editingIndex === index + 1) setEditingIndex(index);
  };

  const addRow = () => {
    if (!snapshotTable) return;
    const rows = [...snapshotTable.rows];
    const nextRank = rows.length + 1;
    const newRow: SnapshotRow = {
      rank: nextRank,
      priority_area: '',
      key_finding: '',
      recommendation: '',
    };
    rows.push(newRow);
    setSnapshotTable({ ...snapshotTable, rows });
    setEditingIndex(rows.length - 1);
    setEditForm(newRow);
  };

  const deleteRow = (index: number) => {
    if (!snapshotTable?.rows.length) return;
    if (!window.confirm('Remove this row from the snapshot table?')) return;
    const rows = snapshotTable.rows.filter((_, i) => i !== index);
    setSnapshotTable({ ...snapshotTable, rows: renumberRanks(rows) });
    if (editingIndex === index) {
      setEditingIndex(null);
      setEditForm(null);
    } else if (editingIndex !== null && editingIndex > index) {
      setEditingIndex(editingIndex - 1);
    }
  };

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle>Step 5: Snapshot Table</CardTitle>
        <CardDescription>
          Review the Key Findings & Recommendations Snapshot. This table provides a concise overview.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Initial Loading State */}
        {isInitialLoading && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Loading existing snapshot table...</p>
          </div>
        )}

        {/* Generate Button */}
        {!isInitialLoading && !snapshotTable && !isGenerating && (
          <div className="text-center py-8">
            <p className="text-muted-foreground mb-4">
              Click below to generate the snapshot table from your expanded findings.
            </p>
            <Button onClick={handleGenerate} size="lg">
              <RefreshCw className="w-4 h-4 mr-2" />
              Generate Snapshot Table
            </Button>
          </div>
        )}

        {/* Loading State */}
        {isGenerating && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Generating snapshot table...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-5 h-5 text-red-500" />
            <span className="text-red-700">{error}</span>
            <Button variant="outline" size="sm" onClick={handleGenerate} className="ml-auto">
              Retry
            </Button>
          </div>
        )}

        {/* Snapshot Table */}
        {!isInitialLoading && snapshotTable && (
          <>
            {/* Table Title */}
            <h3 className="text-lg font-semibold">{snapshotTable.title}</h3>

            {/* Table */}
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">#</TableHead>
                    <TableHead className="w-20">Order</TableHead>
                    <TableHead className="w-1/5">Priority Area</TableHead>
                    <TableHead className="w-2/5">Key Finding</TableHead>
                    <TableHead className="w-2/5">Recommendation</TableHead>
                    <TableHead className="w-16">Edit</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {snapshotTable.rows.map((row, index) => (
                    <TableRow key={index}>
                      {editingIndex === index && editForm ? (
                        // Edit Mode
                        <>
                          <TableCell className="font-bold">{row.rank}</TableCell>
                          <TableCell>
                            <div className="flex flex-col gap-0.5">
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => moveRowUp(index)} disabled={index === 0} title="Move up">
                                <ChevronUp className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => moveRowDown(index)} disabled={index === snapshotTable.rows.length - 1} title="Move down">
                                <ChevronDown className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Input
                              value={editForm.priority_area}
                              onChange={(e) => setEditForm({ ...editForm, priority_area: e.target.value })}
                              className="h-8"
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              value={editForm.key_finding}
                              onChange={(e) => setEditForm({ ...editForm, key_finding: e.target.value })}
                              className="h-8"
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              value={editForm.recommendation}
                              onChange={(e) => setEditForm({ ...editForm, recommendation: e.target.value })}
                              className="h-8"
                            />
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button variant="ghost" size="sm" onClick={saveEdit} title="Save">
                                <Save className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={cancelEdit} title="Cancel">
                                <X className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => deleteRow(index)} className="text-destructive hover:text-destructive" title="Delete row">
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </>
                      ) : (
                        // View Mode
                        <>
                          <TableCell className="font-bold">{row.rank}</TableCell>
                          <TableCell>
                            <div className="flex flex-col gap-0.5">
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => moveRowUp(index)} disabled={index === 0} title="Move up">
                                <ChevronUp className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => moveRowDown(index)} disabled={index === snapshotTable.rows.length - 1} title="Move down">
                                <ChevronDown className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                          <TableCell className="font-medium">{row.priority_area}</TableCell>
                          <TableCell>{row.key_finding}</TableCell>
                          <TableCell>{row.recommendation}</TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button variant="ghost" size="sm" onClick={() => startEdit(index)} title="Edit">
                                <Pencil className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => deleteRow(index)} className="text-destructive hover:text-destructive" title="Delete row">
                                <Trash2 className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <Button type="button" variant="outline" className="mt-2" onClick={addRow}>
              <Plus className="w-4 h-4 mr-2" />
              Add row
            </Button>

            {/* Action Buttons */}
            <div className="flex justify-between pt-4 border-t">
              <div className="flex gap-2">
                <Button variant="outline" onClick={onBack}>
                  Back
                </Button>
                <Button variant="outline" onClick={handleGenerate}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Regenerate
                </Button>
              </div>
              <Button onClick={handleConfirm} disabled={isLoading || !snapshotTable}>
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Continue to 12-Month Plan
                  </>
                )}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
