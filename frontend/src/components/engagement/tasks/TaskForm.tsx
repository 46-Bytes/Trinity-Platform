import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { useAuth } from '@/context/AuthContext';
import type { Task, TaskCreatePayload, TaskUpdatePayload } from '@/store/slices/tasksReducer';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const taskFormSchema = z.object({
  title: z.string().min(1, 'Title is required').max(255, 'Title must be less than 255 characters'),
  description: z.string().optional(),
  status: z.enum(['pending', 'in_progress', 'completed', 'cancelled']).optional(),
  priority: z.enum(['low', 'medium', 'high', 'urgent']).optional(),
  assignedToUserIds: z.array(z.string()).optional(),
  createdByUserId: z.string().optional(),
  dueDate: z.string().optional(),
});

type TaskFormValues = z.infer<typeof taskFormSchema>;

interface TaskFormProps {
  task?: Task;
  engagementId?: string;
  onSubmit: (data: TaskCreatePayload | TaskUpdatePayload) => void;
  onCancel: () => void;
}

export function TaskForm({ task, engagementId, onSubmit, onCancel }: TaskFormProps) {
  const isEditMode = !!task;
  const { user } = useAuth();
  const [engagement, setEngagement] = useState<{ 
    clientId?: string; 
    primaryAdvisorId?: string; 
    secondaryAdvisorIds?: string[];
  } | null>(null);
  const [isLoadingEngagement, setIsLoadingEngagement] = useState(false);

  // Fetch engagement details for both create and edit modes
  useEffect(() => {
    const engagementIdToFetch = engagementId || task?.engagementId;
    if (engagementIdToFetch) {
      setIsLoadingEngagement(true);
      const token = localStorage.getItem('auth_token');
      fetch(`${API_BASE_URL}/api/engagements/${engagementIdToFetch}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
        .then((res) => res.json())
        .then((data) => {
          // Convert UUIDs to strings if needed
          const secondaryIds = (data.secondary_advisor_ids || []).map((id: any) => 
            typeof id === 'string' ? id : String(id)
          );
          setEngagement({
            clientId: data.client_id ? String(data.client_id) : undefined,
            primaryAdvisorId: data.primary_advisor_id ? String(data.primary_advisor_id) : undefined,
            secondaryAdvisorIds: secondaryIds,
          });
        })
        .catch((err) => {
          console.error('Failed to fetch engagement:', err);
        })
        .finally(() => {
          setIsLoadingEngagement(false);
        });
    }
  }, [engagementId, task?.engagementId]);

  const form = useForm<TaskFormValues>({
    resolver: zodResolver(taskFormSchema),
    defaultValues: {
      title: task?.title || '',
      description: task?.description || '',
      status: task?.status || 'pending',
      priority: task?.priority || 'medium',
      assignedToUserIds: task?.assignedToUserIds || [],
      createdByUserId: user?.id || '',
      dueDate: task?.dueDate || '',
    },
  });

  const ALL_ADVISORS_MARKER = '__ALL_ADVISORS__';

  const getAllAdvisorIds = (): string[] => {
    const advisorIds: string[] = [];
    if (engagement?.primaryAdvisorId) {
      advisorIds.push(String(engagement.primaryAdvisorId));
    }
    if (engagement?.secondaryAdvisorIds && engagement.secondaryAdvisorIds.length > 0) {
      const primaryIdStr = engagement.primaryAdvisorId ? String(engagement.primaryAdvisorId) : '';
      engagement.secondaryAdvisorIds.forEach((advisorId) => {
        const advisorIdStr = String(advisorId);
        // Avoid duplicates if primary advisor is also in secondary list
        if (advisorIdStr !== primaryIdStr) {
          advisorIds.push(advisorIdStr);
        }
      });
    }
    return advisorIds;
  };

  // Determine which buttons to show based on user role
  const getAssignmentButtons = () => {
    if (!user) return null;

    const userRole = user.role;
    const buttons: Array<{ label: string; userId: string }> = [];

    if (userRole === 'firm_admin') {
      // Firm Admin: Only two buttons - Assign to Client and Assign to Advisor(s)
      if (engagement?.clientId) {
        buttons.push({ label: 'Assign to Client', userId: String(engagement.clientId) });
      }
      // Check if there are any advisors (primary or secondary)
      const advisorIds = getAllAdvisorIds();
      if (advisorIds.length > 0) {
        buttons.push({ label: 'Assign to Advisor(s)', userId: ALL_ADVISORS_MARKER });
      }
    } else if (userRole === 'firm_advisor') {
      // Firm Advisor: Assign to Self, Assign to Client
      if (user.id) {
        buttons.push({ label: 'Assign to Self', userId: user.id });
      }
      if (engagement?.clientId) {
        buttons.push({ label: 'Assign to Client', userId: String(engagement.clientId) });
      }
    } else if (userRole === 'client') {
      // Client (in firm context): Assign to Advisors, Assign to Self
      // Add primary advisor
      if (engagement?.primaryAdvisorId) {
        buttons.push({ label: 'Assign to Advisor', userId: String(engagement.primaryAdvisorId) });
      }
      // Add secondary advisors
      if (engagement?.secondaryAdvisorIds && engagement.secondaryAdvisorIds.length > 0) {
        const primaryIdStr = engagement.primaryAdvisorId ? String(engagement.primaryAdvisorId) : '';
        engagement.secondaryAdvisorIds.forEach((advisorId) => {
          const advisorIdStr = String(advisorId);
          if (advisorIdStr !== primaryIdStr) {
            buttons.push({ label: 'Assign to Advisor', userId: advisorIdStr });
          }
        });
      }
      // Assign to self
      if (user.id) {
        buttons.push({ label: 'Assign to Self', userId: user.id });
      }
    } else if (userRole === 'advisor') {
      // Solo Advisor: Assign to Self, Assign to Client
      if (user.id) {
        buttons.push({ label: 'Assign to Self', userId: user.id });
      }
      if (engagement?.clientId) {
        buttons.push({ label: 'Assign to Client', userId: engagement.clientId });
      }
    } else if (userRole === 'admin' || userRole === 'super_admin') {
      // Admin: Assign to Advisor, Assign to Client
      if (engagement?.primaryAdvisorId) {
        buttons.push({ label: 'Assign to Advisor', userId: engagement.primaryAdvisorId });
      }
      if (engagement?.clientId) {
        buttons.push({ label: 'Assign to Client', userId: engagement.clientId });
      }
    }

    return buttons;
  };

  const assignmentButtons = getAssignmentButtons();

  const handleAssignmentClick = (userId: string) => {
    if (userId === ALL_ADVISORS_MARKER) {
      // Assign to all advisors
      const advisorIds = getAllAdvisorIds();
      form.setValue('assignedToUserIds', advisorIds);
    } else {
      // Single assignment - use array with one element
      form.setValue('assignedToUserIds', [userId]);
    }
  };

  const handleSubmit = async (values: TaskFormValues) => {
    if (isEditMode) {
      // Update mode - only send changed fields
      const updates: TaskUpdatePayload = {};
      if (values.title !== task.title) updates.title = values.title;
      if (values.description !== task.description) updates.description = values.description;
      if (values.status !== task.status) updates.status = values.status as any;
      if (values.priority !== task.priority) updates.priority = values.priority as any;
      
      // Handle assignment changes - compare arrays
      const currentIds = task?.assignedToUserIds || [];
      const newIds = values.assignedToUserIds || [];
      if (JSON.stringify(currentIds.sort()) !== JSON.stringify(newIds.sort())) {
        updates.assignedToUserIds = newIds.length > 0 ? newIds : undefined;
      }
      
      if (values.dueDate !== task.dueDate) {
        updates.dueDate = values.dueDate || undefined;
      }
      values.createdByUserId = user?.id;
      onSubmit(updates);
    } else {
      // Create mode
      const engagementIdToUse = engagementId || task?.engagementId;
      
      onSubmit({
        engagementId: engagementIdToUse || '',
        title: values.title,
        description: values.description,
        status: values.status as any,
        priority: values.priority as any,
        assignedToUserIds: values.assignedToUserIds && values.assignedToUserIds.length > 0 ? values.assignedToUserIds : undefined,
        createdByUserId: user?.id || '',
        dueDate: values.dueDate || undefined,
      } as TaskCreatePayload);
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title *</FormLabel>
              <FormControl>
                <Input placeholder="Enter task title" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea placeholder="Enter task description" {...field} rows={4} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="status"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Status</FormLabel>
                <Select onValueChange={field.onChange} defaultValue={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select status" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="priority"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Priority</FormLabel>
                <Select onValueChange={field.onChange} defaultValue={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select priority" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="assignedToUserIds"
            render={({ field }) => {
              // Check if all advisors are selected (for firm_admin)
              const advisorIds = getAllAdvisorIds();
              const isAllAdvisorsSelected = user?.role === 'firm_admin' && 
                advisorIds.length > 0 && 
                field.value && 
                field.value.length === advisorIds.length &&
                advisorIds.every(id => field.value?.includes(id));
              
              // Check if a specific user is selected
              const isUserSelected = (userId: string) => {
                return field.value?.includes(userId) || false;
              };
              
              return (
                <FormItem>
                  <FormLabel>Assigned To</FormLabel>
                  {assignmentButtons && assignmentButtons.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {assignmentButtons.map((button) => {
                        const isSelected = button.userId === ALL_ADVISORS_MARKER 
                          ? isAllAdvisorsSelected 
                          : isUserSelected(button.userId);
                        return (
                          <Button
                            key={button.userId}
                            type="button"
                            variant={isSelected ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => handleAssignmentClick(button.userId)}
                          >
                            {button.label}
                          </Button>
                        );
                      })}
                    </div>
                  )}
                  {user?.role === 'firm_admin' && isAllAdvisorsSelected && (
                    <p className="text-sm text-muted-foreground mt-1">
                      Task will be assigned to all advisors associated with this engagement.
                    </p>
                  )}
                  <FormMessage />
                </FormItem>
              );
            }}
          />

          <FormField
            control={form.control}
            name="dueDate"
            render={({ field }) => {
              // Get today's date in YYYY-MM-DD format for min attribute
              const today = new Date().toISOString().split('T')[0];
              
              return (
                <FormItem>
                  <FormLabel>Due Date</FormLabel>
                  <FormControl>
                    <Input 
                      type="date" 
                      {...field} 
                      min={today}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              );
            }}
          />
        </div>

        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit">{isEditMode ? 'Update Task' : 'Create Task'}</Button>
        </div>
      </form>
    </Form>
  );
}

