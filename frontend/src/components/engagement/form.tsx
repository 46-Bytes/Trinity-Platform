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
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { createEngagement, updateEngagement, fetchUserRoleData } from "@/store/slices/engagementReducer";
import type { Engagement } from "@/store/slices/engagementReducer";

// Zod validation schema
const engagementFormSchema = z.object({
  businessName: z.string().min(2, {
    message: "Business name must be at least 2 characters.",
  }),
  industryName: z.string().min(2, {
    message: "Industry name must be at least 2 characters.",
  }),
  engagementName: z.string().min(3, {
    message: "Engagement name must be at least 3 characters.",
  }),
  description: z.string().min(10, {
    message: "Description must be at least 10 characters.",
  }),
  clientOrAdvisorId: z.string().min(1, {
    message: "Please select a client or advisor.",
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
  const { isLoading, userRoleData } = useAppSelector((state) => state.engagement);
  
  // Determine if we're in edit mode
  const isEditMode = mode === 'edit' || !!engagement;

  const form = useForm<EngagementFormValues>({
    resolver: zodResolver(engagementFormSchema),
    defaultValues: {
      businessName: "",
      industryName: "",
      engagementName: "",
      description: "",
      clientOrAdvisorId: "",
    },
  });

  // Fetch user role data on mount
  useEffect(() => {
    if (!userRoleData) {
      dispatch(fetchUserRoleData());
    }
  }, [dispatch, userRoleData]);

  // Pre-fill form when in edit mode
  useEffect(() => {
    if (engagement && isEditMode) {
      form.reset({
        businessName: engagement.businessName || "",
        industryName: engagement.industryName || "",
        engagementName: engagement.title || "",
        description: engagement.description || "",
        clientOrAdvisorId: engagement.clientId || "",
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
      // Get client/advisor name from the selected ID
      let clientName = "Unknown";
      if (userRoleData) {
        if (userRoleData.user_role === 'advisor' && userRoleData.clients) {
          const selectedClient = userRoleData.clients.find(c => c.id === values.clientOrAdvisorId);
          clientName = selectedClient?.name || "Unknown Client";
        } else if (userRoleData.advisors) {
          const selectedAdvisor = userRoleData.advisors.find(a => a.id === values.clientOrAdvisorId);
          clientName = selectedAdvisor?.name || "Unknown Advisor";
        }
      }

      if (isEditMode && engagement) {
        // Edit mode - update existing engagement
        await dispatch(updateEngagement({
          id: engagement.id,
          updates: {
            businessName: values.businessName,
            title: values.engagementName,
            description: values.description,
            industryName: values.industryName,
            clientId: values.clientOrAdvisorId,
            clientName: clientName,
          }
        })).unwrap();
      } else {
        // Create mode - create new engagement
        await dispatch(createEngagement({
          clientId: values.clientOrAdvisorId,
          clientName: clientName,
          businessName: values.businessName,
          title: values.engagementName,
          description: values.description,
          industryName: values.industryName,
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
        {/* Two column grid for form fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormField
            control={form.control}
            name="businessName"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Business Name</FormLabel>
                <FormControl>
                  <Input 
                    placeholder="e.g., Acme Corporation" 
                    {...field} 
                  />
                </FormControl>
                <FormDescription>
                  Enter the business name.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="industryName"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Industry Name</FormLabel>
                <FormControl>
                  <Input 
                    placeholder="e.g., Technology, Healthcare" 
                    {...field} 
                  />
                </FormControl>
                <FormDescription>
                  Enter the industry sector.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          {/* Dynamic Client/Advisor Dropdown */}
          {userRoleData && (
            <FormField
              control={form.control}
              name="clientOrAdvisorId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    {userRoleData.user_role === 'advisor' ? 'Select Client' : 'Select Advisor'}
                  </FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder={`Select a ${userRoleData.user_role === 'advisor' ? 'client' : 'advisor'}`} />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {userRoleData.user_role === 'advisor' && userRoleData.clients ? (
                        userRoleData.clients.map((client) => (
                          <SelectItem key={client.id} value={client.id}>
                            {client.name}
                          </SelectItem>
                        ))
                      ) : userRoleData.advisors ? (
                        userRoleData.advisors.map((advisor) => (
                          <SelectItem key={advisor.id} value={advisor.id}>
                            {advisor.name}
                          </SelectItem>
                        ))
                      ) : (
                        <SelectItem value="none" disabled>No options available</SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    {userRoleData.user_role === 'advisor' 
                      ? 'Choose the client.' 
                      : 'Choose the advisor.'}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

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
                  Provide engagement name.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {/* Description field - full width */}
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description</FormLabel>
              <FormControl>
                <Textarea 
                  placeholder="Describe the scope and objectives of this engagement..."
                  className="min-h-[100px]"
                  {...field} 
                />
              </FormControl>
              <FormDescription>
                Provide details about the engagement scope, objectives, and deliverables.
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