/**
 * Step 5: Snapshot Table Component
 * Displays the Key Findings & Recommendations Snapshot table
 */
import React, { useState } from 'react';
import { Loader2, CheckCircle2, AlertCircle, Pencil, Save, X, RefreshCw } from 'lucide-react';
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
}

export function SnapshotTableStep({ projectId, onComplete, onBack, className }: SnapshotTableStepProps) {
  const [snapshotTable, setSnapshotTable] = useState<SnapshotTable | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<SnapshotRow | null>(null);
  const [tokensUsed, setTokensUsed] = useState(0);

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
      setTokensUsed(result.tokens_used || 0);
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

  return (
    <Card className={cn('w-full', className)}>
      <CardHeader>
        <CardTitle>Step 5: Snapshot Table</CardTitle>
        <CardDescription>
          Review the Key Findings & Recommendations Snapshot. This table provides a concise overview.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Generate Button */}
        {!snapshotTable && !isGenerating && (
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
        {snapshotTable && (
          <>
            {/* Token Usage */}
            {tokensUsed > 0 && (
              <p className="text-sm text-muted-foreground">
                Tokens used: {tokensUsed.toLocaleString()}
              </p>
            )}

            {/* Table Title */}
            <h3 className="text-lg font-semibold">{snapshotTable.title}</h3>

            {/* Table */}
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">#</TableHead>
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
                              <Button variant="ghost" size="sm" onClick={saveEdit}>
                                <Save className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={cancelEdit}>
                                <X className="w-4 h-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </>
                      ) : (
                        // View Mode
                        <>
                          <TableCell className="font-bold">{row.rank}</TableCell>
                          <TableCell className="font-medium">{row.priority_area}</TableCell>
                          <TableCell>{row.key_finding}</TableCell>
                          <TableCell>{row.recommendation}</TableCell>
                          <TableCell>
                            <Button variant="ghost" size="sm" onClick={() => startEdit(index)}>
                              <Pencil className="w-4 h-4" />
                            </Button>
                          </TableCell>
                        </>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

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
