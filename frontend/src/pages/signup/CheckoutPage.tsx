import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Check, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';
import {
  createCheckout,
  getAccount,
  getPrograms,
  toBackendUrl,
  type Plan,
  type Program,
} from '@/lib/selfServiceApi';

/**
 * Checkout step of the self-service funnel.
 *
 * The owner arrives here after Auth0 signup, confirms their program and pays.
 * With the manual billing provider the subscription activates on the spot and
 * we jump straight to the completion screen; with Stripe (Feature 8) the
 * redirect_url points at a Checkout Session instead.
 */
export default function CheckoutPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user, isLoading: authLoading } = useAuth();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [program, setProgram] = useState<Program | null>(
    (searchParams.get('program') as Program) || null,
  );
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cancelled = searchParams.get('cancelled') === '1';

  useEffect(() => {
    if (authLoading) return;

    Promise.all([getPrograms(), getAccount()])
      .then(([catalogue, account]) => {
        setPlans(catalogue.plans);

        // Already paid up - nothing to do here.
        if (account.subscription && ['active', 'trialing'].includes(account.subscription.status)) {
          navigate('/onboarding/complete', { replace: true });
          return;
        }

        // Prefer the program they already started paying for.
        const pending = account.subscription?.program ?? null;
        setProgram((current) => current ?? pending ?? catalogue.plans[0]?.program ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load your account.'))
      .finally(() => setLoading(false));
  }, [authLoading, navigate]);

  const handleCheckout = async () => {
    if (!program) return;

    setSubmitting(true);
    setError(null);

    try {
      const result = await createCheckout(program);

      if (result.activated_immediately) {
        navigate('/onboarding/complete', { replace: true });
        return;
      }

      // External payment page (Stripe Checkout).
      window.location.href = toBackendUrl(result.redirect_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Checkout failed. Please try again.');
      setSubmitting(false);
    }
  };

  const selectedPlan = plans.find((plan) => plan.program === program);

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8 bg-background">
      <div className="w-full max-w-lg animate-scale-in">
        <div className="mb-8 text-center">
          <img src="/logo.png" alt="Trinity Logo" className="w-24 h-24 object-contain mx-auto mb-4" />
          <h1 className="font-heading text-3xl font-bold text-foreground mb-2">
            Confirm your program
          </h1>
          <p className="text-muted-foreground">
            {user?.businessName
              ? `Setting up Trinity for ${user.businessName}.`
              : 'One more step and your workspace is ready.'}
          </p>
        </div>

        {cancelled && (
          <div className="mb-6 p-4 bg-muted border border-border rounded-lg">
            <p className="text-sm text-muted-foreground">
              Payment was cancelled. You can try again whenever you're ready.
            </p>
          </div>
        )}

        {error && (
          <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        <div className="grid gap-3 mb-6">
          {plans.map((plan) => {
            const selected = program === plan.program;
            return (
              <button
                key={plan.program}
                type="button"
                onClick={() => setProgram(plan.program)}
                aria-pressed={selected}
                className={`text-left rounded-lg border p-4 transition-colors ${
                  selected
                    ? 'border-accent bg-accent/5 ring-1 ring-accent'
                    : 'border-border hover:border-accent/50'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-foreground">{plan.label}</p>
                    <p className="text-sm text-muted-foreground mt-1">{plan.description}</p>
                  </div>
                  {selected && <Check className="w-5 h-5 text-accent shrink-0 mt-0.5" />}
                </div>
              </button>
            );
          })}
        </div>

        {selectedPlan && (
          <div className="card-trinity p-6 mb-6">
            <p className="font-medium text-foreground mb-3">What's included</p>
            <ul className="space-y-2">
              {selectedPlan.features.map((feature) => (
                <li key={feature} className="flex items-start gap-2 text-sm text-muted-foreground">
                  <Check className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                  {feature}
                </li>
              ))}
            </ul>
            <div className="mt-4 pt-4 border-t border-border flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Includes {selectedPlan.team_member_limit} team member seats
              </span>
              <span className="font-heading font-bold text-lg text-foreground">
                {selectedPlan.monthly_price > 0
                  ? `${selectedPlan.currency} $${selectedPlan.monthly_price}/mo`
                  : 'Pricing TBC'}
              </span>
            </div>
          </div>
        )}

        <Button
          onClick={handleCheckout}
          className="w-full btn-primary h-11"
          size="lg"
          disabled={submitting || !program}
        >
          {submitting ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Processing...
            </span>
          ) : (
            <span className="flex items-center gap-2">
              Subscribe and start
              <ArrowRight className="w-4 h-4" />
            </span>
          )}
        </Button>
      </div>
    </div>
  );
}
