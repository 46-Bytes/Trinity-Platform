import { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { createSubscription } from '@/store/slices/subscriptionReducer';
import { fetchFirms } from '@/store/slices/firmReducer';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useForm } from 'react-hook-form';

interface CreateSubscriptionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}

interface SubscriptionFormData {
  firm_id: string;
  plan_name: string;
  seat_count: number;
  billing_period: 'monthly' | 'annual';
  price: number;
  currency: string;
  start_date: string;
  end_date?: string;
}

export function CreateSubscriptionDialog({
  open,
  onOpenChange,
  onSuccess,
}: CreateSubscriptionDialogProps) {
  const dispatch = useAppDispatch();
  const { isCreating, error } = useAppSelector((state) => state.subscription);
  const { firms } = useAppSelector((state) => state.firm);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    setValue,
    watch,
  } = useForm<SubscriptionFormData>({
    defaultValues: {
      firm_id: '',
      plan_name: '',
      seat_count: 5,
      billing_period: 'monthly',
      price: 0,
      currency: 'USD',
      start_date: new Date().toISOString().split('T')[0],
    },
  });

  const selectedBillingPeriod = watch('billing_period');

  // Fetch firms when dialog opens
  useEffect(() => {
    if (open) {
      dispatch(fetchFirms());
    }
  }, [open, dispatch]);

  // Reset form when dialog closes
  useEffect(() => {
    if (!open) {
      reset();
    }
  }, [open, reset]);

  // Show error toast
  useEffect(() => {
    if (error) {
      toast.error(error);
    }
  }, [error]);

  const onSubmit = async (data: SubscriptionFormData) => {
    try {
      await dispatch(createSubscription({
        firm_id: data.firm_id || undefined,
        plan_name: data.plan_name,
        seat_count: Number(data.seat_count),
        billing_period: data.billing_period,
        price: Number(data.price),
        currency: data.currency,
        start_date: data.start_date,
        end_date: data.end_date || undefined,
      })).unwrap();

      toast.success('Subscription created successfully');
      onOpenChange(false);
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
    
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Create New Subscription</DialogTitle>
          <DialogDescription>
            Create a new subscription for a firm. All fields are required unless marked optional.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="firm_id">Firm *</Label>
            <Select
              value={watch('firm_id')}
              onValueChange={(value) => setValue('firm_id', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a firm" />
              </SelectTrigger>
              <SelectContent>
                {firms.map((firm) => (
                  <SelectItem key={firm.id} value={firm.id}>
                    {firm.firm_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.firm_id && (
              <p className="text-sm text-destructive">{errors.firm_id.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="plan_name">Plan Name *</Label>
            <Input
              id="plan_name"
              placeholder="e.g., Professional, Enterprise"
              {...register('plan_name', {
                required: 'Plan name is required',
              })}
            />
            {errors.plan_name && (
              <p className="text-sm text-destructive">{errors.plan_name.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="seat_count">Seat Count *</Label>
              <Input
                id="seat_count"
                type="number"
                min="1"
                placeholder="5"
                {...register('seat_count', {
                  required: 'Seat count is required',
                  min: { value: 1, message: 'Minimum 1 seat required' },
                  valueAsNumber: true,
                })}
              />
              {errors.seat_count && (
                <p className="text-sm text-destructive">{errors.seat_count.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="billing_period">Billing Period *</Label>
              <Select
                value={watch('billing_period')}
                onValueChange={(value: 'monthly' | 'annual') =>
                  setValue('billing_period', value)
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="monthly">Monthly</SelectItem>
                  <SelectItem value="annual">Annual</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="price">Price *</Label>
              <Input
                id="price"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                {...register('price', {
                  required: 'Price is required',
                  min: { value: 0, message: 'Price must be positive' },
                  valueAsNumber: true,
                })}
              />
              {errors.price && (
                <p className="text-sm text-destructive">{errors.price.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="currency">Currency *</Label>
              <Select
                value={watch('currency')}
                onValueChange={(value) => setValue('currency', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="USD">USD</SelectItem>
                  <SelectItem value="EUR">EUR</SelectItem>
                  <SelectItem value="GBP">GBP</SelectItem>
                  <SelectItem value="CAD">CAD</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="start_date">Start Date *</Label>
              <Input
                id="start_date"
                type="date"
                {...register('start_date', {
                  required: 'Start date is required',
                })}
              />
              {errors.start_date && (
                <p className="text-sm text-destructive">{errors.start_date.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="end_date">End Date (Optional)</Label>
              <Input
                id="end_date"
                type="date"
                {...register('end_date')}
              />
              {errors.end_date && (
                <p className="text-sm text-destructive">{errors.end_date.message}</p>
              )}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isCreating}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isCreating}>
              {isCreating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                'Create Subscription'
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

