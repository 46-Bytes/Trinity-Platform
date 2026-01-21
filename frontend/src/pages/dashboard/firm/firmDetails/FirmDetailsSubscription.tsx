// Wrapper component for subscription details for a specific firm
import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useAppSelector } from '@/store/hooks';
import { Loader2, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FirmDetailsContext {
  firmId: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function FirmDetailsSubscription() {
  const { firmId } = useOutletContext<FirmDetailsContext>();
  const { firm, isLoading } = useAppSelector((state) => state.firm);
  const [subscription, setSubscription] = useState<any>(null);
  const [loadingSub, setLoadingSub] = useState(false);

  useEffect(() => {
    if (firmId) {
      setLoadingSub(true);
      const token = localStorage.getItem('auth_token');
      fetch(`${API_BASE_URL}/api/firms/${firmId}/subscription`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      })
      .then(res => {
        if (res.ok) {
          return res.json();
        }
        // If 404, no subscription exists - that's okay
        if (res.status === 404) {
          return null;
        }
        // If 403, permission denied - log but don't throw
        if (res.status === 403) {
          console.error('Permission denied to view subscription');
          return null;
        }
        throw new Error(`Failed to fetch subscription: ${res.status}`);
      })
      .then(data => {
        setSubscription(data);
        setLoadingSub(false);
      })
      .catch((error) => {
        console.error('Error fetching subscription:', error);
        setSubscription(null);
        setLoadingSub(false);
      });
    }
  }, [firmId]);

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    } catch {
      return 'N/A';
    }
  };

  if (isLoading || loadingSub) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-accent" />
        <span className="ml-2 text-muted-foreground">Loading subscription...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="card-trinity p-6">
        <h2 className="font-heading text-xl font-semibold mb-6">Subscription Details</h2>
        {subscription ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">Plan Name</label>
                <p className="font-medium mt-1">{subscription.plan_name}</p>
              </div>
              <div>
                <label className="text-sm text-muted-foreground">Seat Count</label>
                <p className="font-medium mt-1">{subscription.seat_count} seats</p>
              </div>
              <div>
                <label className="text-sm text-muted-foreground">Monthly Price</label>
                <p className="font-medium mt-1">${subscription.monthly_price?.toFixed(2) || '0.00'}</p>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">Status</label>
                <div className="mt-1">
                  <span className={cn(
                    "status-badge",
                    subscription.status === 'active' ? "status-success" : "status-warning"
                  )}>
                    {subscription.status}
                  </span>
                </div>
              </div>
              {subscription.cancelled_at && (
                <div>
                  <label className="text-sm text-muted-foreground">Cancelled At</label>
                  <div className="flex items-center gap-2 mt-1">
                    <Calendar className="w-4 h-4 text-muted-foreground" />
                    <p className="font-medium">{formatDate(subscription.cancelled_at)}</p>
                  </div>
                </div>
              )}
              <div>
                <label className="text-sm text-muted-foreground">Cancel at Period End</label>
                <p className="font-medium mt-1">{subscription.cancel_at_period_end ? 'Yes' : 'No'}</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            No subscription found for this firm
          </div>
        )}
      </div>
    </div>
  );
}

