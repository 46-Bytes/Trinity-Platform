import { useEffect } from 'react';
import { ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

import { Input } from '@/components/ui/input';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchRegister, updateRegisterEntry } from '@/store/slices/dataRoomReducer';

interface DocumentRegisterCardProps {
  engagementId: string;
  stageCode: string;
}

function formatDate(value: string | null): string {
  if (!value) return '';
  const at = new Date(value);
  return Number.isNaN(at.getTime())
    ? ''
    : at.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * The stage's document register.
 *
 * Generated, not authored: the rows are the files sitting in this stage's data
 * room folders, and there is no "add a row" control. Per the brief the name,
 * date and location come from the file itself; the advisor types only the
 * document ID, renewal date, renewal cost and notes.
 *
 * Renewal cost is in the client's program sheet on every stage tab but absent
 * from the mockup, so it is shown here and flagged for confirmation rather
 * than silently dropped.
 */
export function DocumentRegisterCard({ engagementId, stageCode }: DocumentRegisterCardProps) {
  const dispatch = useAppDispatch();
  const entries = useAppSelector((s) => s.dataRoom.register[stageCode]);

  useEffect(() => {
    dispatch(fetchRegister({ engagementId, stageCode }));
  }, [dispatch, engagementId, stageCode]);

  const save = (mediaId: string, changes: Record<string, unknown>) => {
    dispatch(updateRegisterEntry({ engagementId, stageCode, mediaId, changes }))
      .unwrap()
      .catch((e) => toast.error(e instanceof Error ? e.message : String(e)));
  };

  return (
    <section className="card-trinity p-4 sm:p-6">
      <h2 className="font-heading text-base font-semibold">Document register</h2>
      <p className="mb-4 mt-1 max-w-3xl text-xs text-muted-foreground">
        Generated from the files in this stage&apos;s data room folders. The name and date come from
        the file; fill in the rest.
      </p>

      {entries === undefined ? (
        <p className="py-6 text-center text-sm text-muted-foreground">Loading&#8230;</p>
      ) : entries.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No files in this stage yet. Upload one against a DD item or on the Files tab.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[54rem] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="pb-2 pr-3 font-semibold">Document</th>
                <th className="pb-2 pr-3 font-semibold">Added</th>
                <th className="pb-2 pr-3 font-semibold">Document ID</th>
                <th className="pb-2 pr-3 font-semibold">Renewal date</th>
                <th className="pb-2 pr-3 font-semibold">Renewal cost</th>
                <th className="pb-2 pr-3 font-semibold">Notes</th>
                <th className="pb-2 font-semibold sr-only">Open in Drive</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((row) => (
                <tr key={row.media_id} className="border-b border-border/60 align-top">
                  <td className="py-2 pr-3">
                    <span className="block max-w-[16rem] truncate font-medium">{row.file_name}</span>
                    <span className="block max-w-[16rem] truncate text-xs text-muted-foreground">
                      {row.sub_item_code} {row.sub_item ?? ''}
                    </span>
                  </td>
                  <td className="py-2 pr-3 text-xs text-muted-foreground">{formatDate(row.added_at)}</td>
                  <td className="py-2 pr-3">
                    <Input
                      className="h-8 w-28 text-xs"
                      aria-label={`Document ID for ${row.file_name}`}
                      defaultValue={row.document_id ?? ''}
                      placeholder="ID"
                      onBlur={(e) => {
                        if (e.target.value !== (row.document_id ?? '')) {
                          save(row.media_id, { document_id: e.target.value || null });
                        }
                      }}
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <Input
                      type="date"
                      className="h-8 w-36 text-xs"
                      aria-label={`Renewal date for ${row.file_name}`}
                      defaultValue={row.renewal_date ?? ''}
                      onBlur={(e) => {
                        if (e.target.value !== (row.renewal_date ?? '')) {
                          save(row.media_id, { renewal_date: e.target.value || null });
                        }
                      }}
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      className="h-8 w-28 text-xs"
                      aria-label={`Renewal cost for ${row.file_name}`}
                      defaultValue={row.renewal_cost ?? ''}
                      placeholder="0.00"
                      onBlur={(e) => {
                        const next = e.target.value === '' ? null : Number(e.target.value);
                        if (next !== row.renewal_cost) save(row.media_id, { renewal_cost: next });
                      }}
                    />
                  </td>
                  <td className="py-2 pr-3">
                    <Input
                      className="h-8 w-full min-w-[12rem] text-xs"
                      aria-label={`Notes for ${row.file_name}`}
                      defaultValue={row.notes ?? ''}
                      placeholder="Notes"
                      onBlur={(e) => {
                        if (e.target.value !== (row.notes ?? '')) {
                          save(row.media_id, { notes: e.target.value || null });
                        }
                      }}
                    />
                  </td>
                  <td className="py-2">
                    {row.drive_web_link && (
                      <a
                        href={row.drive_web_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open the file in Drive"
                        aria-label={`Open ${row.file_name} in Drive`}
                        className="inline-grid h-8 w-8 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
