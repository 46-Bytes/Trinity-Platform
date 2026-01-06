import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useAppDispatch } from '@/store/hooks';
import { createFirm } from '@/store/slices/firmReducer';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface User {
  id: string;
  email: string;
  name?: string;
  role: string;
  firm_id?: string | null;
}

interface Subscription {
  id: string;
  plan_name: string;
  seat_count: number;
  monthly_price: number;
  status: string;
  firm_id?: string | null;
}

interface CreateFirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

interface FirmFormData {
  firm_name: string;
  admin_name: string;
  admin_email: string;
  subscription_id: string;
  billing_email?: string;
}

export function CreateFirmDialog({
  open,
  onOpenChange,
  onSuccess,
}: CreateFirmDialogProps) {
  const dispatch = useAppDispatch();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [availableUsers, setAvailableUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [availableSubscriptions, setAvailableSubscriptions] = useState<Subscription[]>([]);
  const [loadingSubscriptions, setLoadingSubscriptions] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
    reset,
    formState,
  } = useForm<FirmFormData>({
    defaultValues: {
      firm_name: '',
      admin_name: '',
      admin_email: '',
      subscription_id: '',
      billing_email: '',
    },
  });

  const subscriptionId = watch('subscription_id');
  // Fetch available subscriptions when dialog opens
  useEffect(() => {
    if (open) {
      fetchAvailableSubscriptions();
      reset();
    }
  }, [open]);

  const fetchAvailableSubscriptions = async () => {
    setLoadingSubscriptions(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      // Fetch all subscriptions that are not assigned to a firm
      const response = await fetch(`${API_BASE_URL}/api/subscriptions`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const subscriptions = await response.json();
        // Filter to only include subscriptions without a firm_id (available subscriptions)
        const available = subscriptions.filter(
          (sub: Subscription) => !sub.firm_id
        );
        setAvailableSubscriptions(available);
      }
    } catch (error) {
      console.error('Error fetching subscriptions:', error);
      toast.error('Failed to load available subscriptions');
    } finally {
      setLoadingSubscriptions(false);
    }
  };

  const onSubmit = async (data: FirmFormData) => {
    if (!data.admin_name || !data.admin_email) {
      toast.error('Please provide firm admin name and email');
      return;
    }
    if (!data.subscription_id) {
      toast.error('Please select a subscription');
      return;
    }

    setIsSubmitting(true);
    try {
      await dispatch(createFirm({
        firm_name: data.firm_name,
        admin_name: data.admin_name,
        admin_email: data.admin_email,
        subscription_id: data.subscription_id,
        billing_email: data.billing_email || undefined,
      })).unwrap();

      toast.success('Firm created successfully');
      onOpenChange(false);
      reset();
      if (onSuccess) {
        onSuccess();
      }
    } catch (error: any) {
      toast.error(error || 'Failed to create firm');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Create New Firm</DialogTitle>
          <DialogDescription>
            Create a new firm account. Select an admin user and an existing subscription.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="firm_name">Firm Name *</Label>
            <Input
              id="firm_name"
              placeholder="Enter firm name"
              {...register('firm_name', {
                required: 'Firm name is required',
                minLength: {
                  value: 2,
                  message: 'Firm name must be at least 2 characters',
                },
              })}
            />
            {errors.firm_name && (
              <p className="text-sm text-destructive">{errors.firm_name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="admin_name">Firm Admin Name *</Label>
            <Input
              id="admin_name"
              placeholder="Enter firm admin name"
              {...register('admin_name', {
                required: 'Admin name is required',
                minLength: {
                  value: 2,
                  message: 'Admin name must be at least 2 characters',
                },
              })}
            />
            {errors.admin_name && (
              <p className="text-sm text-destructive">{errors.admin_name.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="admin_email">Firm Admin Email *</Label>
            <Input
              id="admin_email"
              type="email"
              placeholder="admin@example.com"
              {...register('admin_email', {
                required: 'Admin email is required',
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: 'Invalid email address',
                },
              })}
            />
            {errors.admin_email && (
              <p className="text-sm text-destructive">{errors.admin_email.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="subscription_id">Subscription *</Label>
            <Select
              value={subscriptionId}
              onValueChange={(value) => {
                setValue('subscription_id', value, { shouldValidate: true });
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder={loadingSubscriptions ? 'Loading subscriptions...' : 'Select a subscription'} />
              </SelectTrigger>
              <SelectContent>
                {availableSubscriptions.map((sub) => (
                  <SelectItem key={sub.id} value={sub.id}>
                    {sub.plan_name} - {sub.seat_count} seats - ${sub.monthly_price}/month
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {formState.touchedFields.subscription_id && !subscriptionId && (
              <p className="text-sm text-destructive">Please select a subscription</p>
            )}
            {availableSubscriptions.length === 0 && !loadingSubscriptions && (
              <p className="text-sm text-muted-foreground">
                No available subscriptions found. Create a subscription first.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="billing_email">Billing Email (Optional)</Label>
            <Input
              id="billing_email"
              type="email"
              placeholder="billing@example.com"
              {...register('billing_email', {
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: 'Invalid email address',
                },
              })}
            />
            {errors.billing_email && (
              <p className="text-sm text-destructive">{errors.billing_email.message}</p>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !subscriptionId}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Firm
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

