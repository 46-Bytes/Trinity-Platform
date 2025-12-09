import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { createEngagement, updateEngagement } from "@/store/slices/engagementReducer";
import type { Engagement } from "@/store/slices/engagementReducer";

// Zod validation schema
const engagementFormSchema = z.object({
  industryName: z.string().min(2, {
    message: "Industry name must be at least 2 characters.",
  }),
  engagementName: z.string().min(3, {
    message: "Engagement name must be at least 3 characters.",
  }),
});

type EngagementFormValues = z.infer<typeof engagementFormSchema>;

interface EngagementFormProps {
  onSubmit?: (values: EngagementFormValues) => void;
  onSuccess?: () => void;
  engagement?: Engagement | null; // For edit mode - if provided, form is in edit mode
  mode?: 'create' | 'edit';
}

export function EngagementForm({ 
  onSubmit, 
  onSuccess,
  engagement,
  mode = 'create'
}: EngagementFormProps) {
  const dispatch = useAppDispatch();
  const { isLoading } = useAppSelector((state) => state.engagement);
  
  // Determine if we're in edit mode
  const isEditMode = mode === 'edit' || !!engagement;

  const form = useForm<EngagementFormValues>({
    resolver: zodResolver(engagementFormSchema),
    defaultValues: {
      industryName: "",
      engagementName: "",
    },
  });

  // Pre-fill form when in edit mode
  useEffect(() => {
    if (engagement && isEditMode) {
      form.reset({
        industryName: engagement.description || "", // Map description to industryName
        engagementName: engagement.title || "",
      });
    }
  }, [engagement, isEditMode, form]);

  const handleFormSubmit = async (values: EngagementFormValues) => {
    // Call custom onSubmit if provided (for additional logic)
    if (onSubmit) {
      onSubmit(values);
      return;
    }

    try {
      if (isEditMode && engagement) {
        // Edit mode - update existing engagement
        await dispatch(updateEngagement({
          id: engagement.id,
          updates: {
            title: values.engagementName,
            description: values.industryName,
          }
        })).unwrap();
      } else {
        // Create mode - create new engagement
        await dispatch(createEngagement({
          clientId: "temp-client-id", // TODO: Get from client selection
          clientName: "Temporary Client", // TODO: Get from client selection
          title: values.engagementName,
          description: values.industryName,
          status: 'draft',
          startDate: new Date().toISOString(),
          assignedUsers: [],
        })).unwrap();
      }
      
      // Call success callback if provided
      if (onSuccess) {
        onSuccess();
      }
      
      // Reset form after successful submission (only in create mode)
      if (!isEditMode) {
        form.reset();
      }
    } catch (error) {
      console.error('Failed to save engagement:', error);
      // Error handling is done by Redux (stored in state.engagement.error)
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleFormSubmit)} className="space-y-6">
        <FormField
          control={form.control}
          name="industryName"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Industry Name</FormLabel>
              <FormControl>
                <Input 
                  placeholder="e.g., Technology, Healthcare, Finance" 
                  {...field} 
                />
              </FormControl>
              <FormDescription>
                Enter the industry sector for this engagement.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="engagementName"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Engagement Name</FormLabel>
              <FormControl>
                <Input 
                  placeholder="e.g., Q4 2024 Financial Audit" 
                  {...field} 
                />
              </FormControl>
              <FormDescription>
                Provide a descriptive name for this engagement.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={isLoading}>
          {isLoading ? (
            isEditMode ? "Updating..." : "Creating..."
          ) : (
            isEditMode ? "Update Engagement" : "Create Engagement"
          )}
        </Button>
      </form>
    </Form>
  );
}