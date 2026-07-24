import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CreditCard, ExternalLink, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
import { useToast } from '@/hooks/use-toast';
import {
  cancelSubscription,
  getAccount,
  getBillingPortal,
  toBackendUrl,
  type Account,
} from '@/lib/selfServiceApi';

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  trialing: 'bg-blue-100 text-blue-700',
  pending: 'bg-amber-100 text-amber-700',
  past_due: 'bg-orange-100 text-orange-700',
  cancelled: 'bg-muted text-muted-foreground',
};

const formatDate = (value: string | null) =>
  value ? new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : '-';

/** Subscription and billing for self-service business owners (Feature 7). */
export default function BillingPage() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [account, setAccount] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [working, setWorking] = useState(false);

  const load = async () => {
    try {
      setAccount(await getAccount());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load your billing details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handlePortal = async () => {
    setWorking(true);
    try {
      const { redirect_url } = await getBillingPortal();
      window.location.href = toBackendUrl(redirect_url);
    } catch (err) {
      toast({
        title: 'Billing portal unavailable',
        description: err instanceof Error ? err.message : 'Please try again later.',
        variant: 'destructive',
      });
      setWorking(false);
    }
  };

  const handleCancel = async () => {
    setWorking(true);
    try {
      setAccount(await cancelSubscription(true));
      toast({
        title: 'Subscription cancelled',
        description: 'You keep access until the end of your current billing period.',
      });
    } catch (err) {
      toast({
        title: 'Could not cancel',
        description: err instanceof Error ? err.message : 'Please try again.',
        variant: 'destructive',
      });
    } finally {
      setCancelOpen(false);
      setWorking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card-trinity p-6">
        <div className="text-center py-12">
          <p className="text-destructive mb-2">Could not load billing</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  const subscription = account?.subscription;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-heading text-2xl font-bold text-foreground">Billing</h1>
        <p className="text-muted-foreground mt-1">Manage your Trinity subscription.</p>
      </div>

      {!subscription ? (
        <div className="card-trinity p-6 text-center py-16">
          <CreditCard className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
          <p className="font-medium text-foreground mb-1">No subscription yet</p>
          <p className="text-sm text-muted-foreground mb-6">
            Choose a program to get started with Trinity.
          </p>
          <Button onClick={() => navigate('/onboarding/checkout')} className="btn-primary">
            Choose a program
          </Button>
        </div>
      ) : (
        <>
          <div className="card-trinity p-6">
            <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
              <div>
                <p className="text-sm text-muted-foreground mb-1">Current plan</p>
                <p className="font-heading text-xl font-bold text-foreground">
                  {account?.program_label ?? subscription.plan_name}
                </p>
              </div>
              <Badge className={STATUS_STYLES[subscription.status] ?? STATUS_STYLES.cancelled}>
                {subscription.status.replace('_', ' ')}
              </Badge>
            </div>

            <dl className="grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-sm text-muted-foreground">Monthly price</dt>
                <dd className="font-medium text-foreground">
                  {subscription.monthly_price ? `$${subscription.monthly_price}` : 'Pricing TBC'}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">Seats</dt>
                <dd className="font-medium text-foreground">
                  {account?.seats.team_members_used ?? 0} of {account?.seats.team_member_limit ?? 0}{' '}
                  team members
                </dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">
                  {subscription.cancel_at_period_end ? 'Access ends' : 'Renews on'}
                </dt>
                <dd className="font-medium text-foreground">
                  {formatDate(subscription.current_period_end)}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">Payment method</dt>
                <dd className="font-medium text-foreground capitalize">
                  {subscription.provider === 'manual' ? 'Not required' : subscription.provider}
                </dd>
              </div>
            </dl>

            {subscription.cancel_at_period_end && (
              <div className="mt-6 p-4 bg-muted border border-border rounded-lg">
                <p className="text-sm text-muted-foreground">
                  Your subscription is set to end on {formatDate(subscription.current_period_end)}.
                  You keep full access until then.
                </p>
              </div>
            )}
          </div>

          <div className="flex gap-3 flex-wrap">
            {subscription.provider !== 'manual' && (
              <Button variant="outline" onClick={handlePortal} disabled={working}>
                <ExternalLink className="w-4 h-4 mr-2" />
                Manage payment details
              </Button>
            )}
            {!subscription.cancel_at_period_end && subscription.status !== 'cancelled' && (
              <Button variant="outline" onClick={() => setCancelOpen(true)} disabled={working}>
                Cancel subscription
              </Button>
            )}
          </div>
        </>
      )}

      <AlertDialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel your subscription?</AlertDialogTitle>
            <AlertDialogDescription>
              You'll keep full access to your program until the end of your current billing period
              ({formatDate(subscription?.current_period_end ?? null)}). Your data stays with us in
              case you come back.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={working}>Keep my subscription</AlertDialogCancel>
            <AlertDialogAction onClick={handleCancel} disabled={working}>
              {working ? 'Cancelling...' : 'Cancel subscription'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
