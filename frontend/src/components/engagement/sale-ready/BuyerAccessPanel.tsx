import { useEffect, useState } from 'react';
import { Eye, Plus, RotateCcw, Trash2, X } from 'lucide-react';
import { toast } from 'sonner';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  type EngagementBuyer,
  inviteBuyer,
  restoreBuyer,
  revokeBuyer,
  updateBuyerNda,
} from '@/store/slices/buyerAdminReducer';

interface BuyerAccessPanelProps {
  engagementId: string;
  readOnly?: boolean;
  /** Collapses the panel. The Files header owns whether it is open. */
  onClose?: () => void;
  /** Switches the Files tab to the buyer's view of this data room. */
  onPreview?: () => void;
}

/** Never, a date, or "Today, 09:14" for something that happened today. */
function formatAccess(value: string | null): string {
  if (!value) return 'Never';
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return 'Never';
  const time = at.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit', hour12: false });
  if (at.toDateString() === new Date().toDateString()) return `Today, ${time}`;
  return at.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
}

const STATUS_STYLE: Record<string, string> = {
  active: 'bg-success/10 text-success',
  invited: 'bg-primary/10 text-primary',
  revoked: 'bg-destructive/10 text-destructive',
};

/**
 * The advisor's controls over who the buyers are.
 *
 * Lives inside the Files tab as a collapsible panel, as in the mockup. Which
 * folders a buyer can see is set beside the folders themselves; this panel
 * invites, revokes, restores, records the NDA date, and shows what each buyer
 * has actually looked at.
 *
 * The buyer list and released-folder count are fetched by FilesView, which
 * needs the count for its header before this panel is ever opened.
 */
export function BuyerAccessPanel({
  engagementId,
  readOnly = false,
  onClose,
  onPreview,
}: BuyerAccessPanelProps) {
  const dispatch = useAppDispatch();
  const { buyers, releasedFolders, isSaving, error } = useAppSelector((s) => s.buyerAdmin);
  const [email, setEmail] = useState('');
  const [confirmRevoke, setConfirmRevoke] = useState<EngagementBuyer | null>(null);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const fail = (e: unknown) => toast.error(String(e));

  const invite = () => {
    if (!email.trim()) return;
    dispatch(inviteBuyer({ engagementId, email: email.trim() }))
      .unwrap()
      .then(() => {
        setEmail('');
        toast.success('Invitation sent. The buyer sets their password by email.');
      })
      .catch(fail);
  };

  return (
    <div className="space-y-5">
      <section className="card-trinity border-primary/30 bg-primary/[0.03] p-4 sm:p-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <h2 className="font-heading text-base font-semibold">Buyer access</h2>
          <div className="flex flex-shrink-0 gap-2">
            {onPreview && (
              <Button variant="outline" size="sm" onClick={onPreview}>
                <Eye className="mr-1.5 h-3.5 w-3.5" />
                Preview as buyer
              </Button>
            )}
            {onClose && (
              <Button variant="outline" size="sm" onClick={onClose}>
                <X className="mr-1.5 h-3.5 w-3.5" />
                Close
              </Button>
            )}
          </div>
        </div>
        <p className="mb-1 mt-1 max-w-3xl text-xs text-muted-foreground">
          Buyers sign in to Trinity and see only the folders released to them, read-only. Every open and download is
          recorded. Revoking ends their access without deleting the account, so it can be restored later. The NDA is
          handled outside Trinity; the date here is a record only and does not control access.
        </p>
        <p className="mb-4 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            {releasedFolders.length} folder{releasedFolders.length === 1 ? '' : 's'} released.
          </span>{' '}
          The same set for every buyer. Tick <span className="font-medium">Visible to buyers</span>{' '}
          on a folder below to release it.
        </p>

        {buyers.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No buyers have been invited to this engagement.
          </p>
        ) : (
          <div className="space-y-2">
            {buyers.map((buyer) => {
              const revoked = buyer.status !== 'active';
              const label = buyer.display_status ?? buyer.status;
              return (
                <div
                  key={buyer.id}
                  className={cn(
                    'flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:gap-3',
                    revoked && 'opacity-60'
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{buyer.name || buyer.email}</p>
                    {buyer.name && buyer.email && (
                      <p className="truncate text-xs text-muted-foreground">{buyer.email}</p>
                    )}
                  </div>

                  <div className="flex-shrink-0 sm:w-32">
                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Last access</p>
                    <p className="text-xs">{formatAccess(buyer.last_access_at ?? null)}</p>
                  </div>
                  <div className="flex-shrink-0 sm:w-16">
                    <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Opens</p>
                    <p className="text-xs">{buyer.open_count ?? 0}</p>
                  </div>

                  <span
                    className={cn(
                      'w-fit flex-shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize',
                      STATUS_STYLE[label] ?? STATUS_STYLE.revoked
                    )}
                  >
                    {label}
                  </span>
                  <div className="flex-shrink-0 sm:w-44">
                    <Label className="sr-only" htmlFor={`nda-${buyer.id}`}>
                      NDA signed
                    </Label>
                    <Input
                      id={`nda-${buyer.id}`}
                      type="date"
                      aria-label="NDA signed date"
                      className="h-8 text-xs"
                      disabled={readOnly || isSaving}
                      defaultValue={buyer.nda_signed_date ?? ''}
                      onBlur={(e) => {
                        if (e.target.value !== (buyer.nda_signed_date ?? '')) {
                          dispatch(updateBuyerNda({
                            engagementId, id: buyer.id, nda_signed_date: e.target.value || null,
                          })).unwrap().catch(fail);
                        }
                      }}
                    />
                  </div>
                  {revoked ? (
                    <Button
                      variant="outline" size="sm" className="flex-shrink-0"
                      disabled={readOnly || isSaving}
                      onClick={() =>
                        dispatch(restoreBuyer({ engagementId, id: buyer.id }))
                          .unwrap()
                          .then(() => toast.success('Access restored'))
                          .catch(fail)
                      }
                    >
                      <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                      Restore
                    </Button>
                  ) : (
                    <Button
                      variant="outline" size="sm" className="flex-shrink-0"
                      disabled={readOnly || isSaving}
                      onClick={() => setConfirmRevoke(buyer)}
                    >
                      <Trash2 className="mr-1.5 h-3.5 w-3.5 text-destructive" />
                      Revoke
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {!readOnly && (
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <Input
              type="email"
              value={email}
              disabled={isSaving}
              placeholder="Invite a buyer by email"
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && invite()}
              className="text-sm"
            />
            <Button onClick={invite} disabled={isSaving || !email.trim()} className="flex-shrink-0">
              <Plus className="mr-1.5 h-4 w-4" />
              Invite
            </Button>
          </div>
        )}
      </section>

      <AlertDialog open={confirmRevoke !== null} onOpenChange={(open) => !open && setConfirmRevoke(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke this buyer's access?</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmRevoke?.email}
              <span className="mt-2 block">
                They lose access immediately. The account is not deleted and the record of what they
                opened is kept, so access can be restored later.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!confirmRevoke) return;
                dispatch(revokeBuyer({ engagementId, id: confirmRevoke.id }))
                  .unwrap()
                  .then(() => toast.success('Access revoked'))
                  .catch(fail);
                setConfirmRevoke(null);
              }}
            >
              Revoke
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
