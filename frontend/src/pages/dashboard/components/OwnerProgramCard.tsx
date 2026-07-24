import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, ClipboardList, CreditCard, Loader2, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { getAccount, type Account } from '@/lib/selfServiceApi';

/**
 * Program summary shown above the dashboard for self-service business owners.
 *
 * Gives the owner the one thing the shared client dashboard cannot: where they
 * are in their program, and the next action to take.
 */
export function OwnerProgramCard() {
  const navigate = useNavigate();
  const [account, setAccount] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAccount()
      .then(setAccount)
      .catch(() => setAccount(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="card-trinity p-6 flex items-center gap-3">
        <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Loading your program...</span>
      </div>
    );
  }

  if (!account) return null;

  const subscribed = !!account.subscription && ['active', 'trialing'].includes(account.subscription.status);

  // Not paid up - the only useful action is to finish signing up.
  if (!subscribed) {
    return (
      <div className="card-trinity p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="font-heading text-lg font-bold text-foreground mb-1">
              Finish setting up your account
            </p>
            <p className="text-sm text-muted-foreground">
              Choose your program to unlock your diagnostic and start working the modules.
            </p>
          </div>
          <Button onClick={() => navigate('/onboarding/checkout')} className="btn-primary">
            <span className="flex items-center gap-2">
              Choose a program
              <ArrowRight className="w-4 h-4" />
            </span>
          </Button>
        </div>
      </div>
    );
  }

  const diagnosticDone = account.diagnostic_status === 'completed';
  const diagnosticRunning = account.diagnostic_status === 'processing';

  return (
    <div className="card-trinity p-6">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-5">
        <div>
          <p className="text-sm text-muted-foreground mb-1">Your program</p>
          <p className="font-heading text-xl font-bold text-foreground">
            {account.program_label ?? account.subscription?.plan_name}
          </p>
        </div>
        <Badge className="bg-emerald-100 text-emerald-700">Active</Badge>
      </div>

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          {diagnosticDone ? (
            <CheckCircle2 className="w-5 h-5 text-accent shrink-0 mt-0.5" />
          ) : (
            <ClipboardList className="w-5 h-5 text-muted-foreground shrink-0 mt-0.5" />
          )}
          <div>
            <p className="font-medium text-foreground">
              {diagnosticDone
                ? 'Your diagnostic report is ready'
                : diagnosticRunning
                ? 'We are generating your report'
                : 'Complete your diagnostic'}
            </p>
            <p className="text-sm text-muted-foreground">
              {diagnosticDone
                ? 'Review your recommendations and your recommended starting module.'
                : diagnosticRunning
                ? 'This usually takes a few minutes. We will email you when it is ready.'
                : 'Answer the questions to get your AI-generated report and recommended path.'}
            </p>
          </div>
        </div>

        {account.engagement_id && (
          <Button
            onClick={() => navigate(`/dashboard/engagements/${account.engagement_id}`)}
            className={diagnosticDone ? '' : 'btn-primary'}
            variant={diagnosticDone ? 'outline' : 'default'}
            disabled={diagnosticRunning}
          >
            <span className="flex items-center gap-2">
              {diagnosticDone ? 'View my report' : 'Go to my diagnostic'}
              <ArrowRight className="w-4 h-4" />
            </span>
          </Button>
        )}
      </div>

      <div className="mt-5 pt-5 border-t border-border flex items-center gap-6 flex-wrap text-sm">
        <button
          type="button"
          onClick={() => navigate('/dashboard/team')}
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <Users className="w-4 h-4" />
          {account.seats.team_members_used} of {account.seats.team_member_limit} team seats used
        </button>
        <button
          type="button"
          onClick={() => navigate('/dashboard/billing')}
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <CreditCard className="w-4 h-4" />
          Manage billing
        </button>
      </div>
    </div>
  );
}
