import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useEffect, useMemo } from "react";
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

// Base schema fields
const baseSchemaFields = {
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
  // Client must always be selected
  clientId: z.string().min(1, {
    message: "Please select a client.",
  }),
  // Primary advisor is required at runtime for firm admins, but optional in schema
  primaryAdvisorId: z.string().optional(),
  tool: z.enum(['diagnostic', 'kpi_builder'], {
    message: "Please select a tool.",
  }),
};

// Create schema based on user role
const createSchema = (userRole?: string) => {
  if (userRole === 'admin' || userRole === 'super_admin') {
    return z.object({
      ...baseSchemaFields,
      clientId: z.string().min(1, {
        message: "Please select a client.",
      }),
      advisorId: z.string().min(1, {
        message: "Please select an advisor.",
      }),
    });
  } else {
    return z.object({
      ...baseSchemaFields,
      clientOrAdvisorId: z.string().min(1, {
        message: "Please select a client or advisor.",
      }),
    });
  }
};

type EngagementFormValues = z.infer<ReturnType<typeof createSchema>>;

interface EngagementFormProps {
  onSubmit?: (values: EngagementFormValues) => void;
  onSuccess?: () => void;
  engagement?: Engagement | null;
  mode?: 'create' | 'edit';
  refreshUserData?: boolean; // If true, force refresh user role data
}

export function EngagementForm({ 
  onSubmit, 
  onSuccess,
  engagement,
  mode = 'create',
  refreshUserData = false
}: EngagementFormProps) {
  const dispatch = useAppDispatch();
  const { isLoading, userRoleData } = useAppSelector((state) => state.engagement);
  
  const isEditMode = mode === 'edit' || !!engagement;
  const isAdmin = userRoleData?.user_role === 'admin' || userRoleData?.user_role === 'super_admin';
  
  // Create dynamic schema based on user role
  const schema = useMemo(() => createSchema(userRoleData?.user_role), [userRoleData?.user_role]);
  
  const form = useForm<EngagementFormValues>({
    resolver: zodResolver(schema),
    defaultValues: isAdmin 
      ? {
          businessName: "",
          industryName: "",
          engagementName: "",
          description: "",
          clientId: "",
          advisorId: "",
          tool: "diagnostic" as const,
        }
      : {
          businessName: "",
          industryName: "",
          engagementName: "",
          description: "",
          clientOrAdvisorId: "",
          tool: "diagnostic" as const,
        },
  });

  // Fetch user role data on mount or when refreshUserData is true
  useEffect(() => {
    // Always refetch if refreshUserData is true (e.g., when dialog opens)
    // Otherwise, only fetch if userRoleData doesn't exist
    if (refreshUserData) {
      dispatch(fetchUserRoleData());
    } else if (!userRoleData) {
      dispatch(fetchUserRoleData());
    }
  }, [dispatch, refreshUserData]); // Remove userRoleData from dependencies to allow refetching

  // Pre-fill form when in edit mode
  useEffect(() => {
    if (engagement && isEditMode) {
      if (isAdmin) {
        form.reset({
          businessName: engagement.businessName || "",
          industryName: engagement.industryName || "",
          engagementName: engagement.title || "",
          description: engagement.description || "",
          clientId: engagement.clientId || "",
          advisorId: (engagement as any).primaryAdvisorId || "",
          tool: (engagement.tool as 'diagnostic' | 'kpi_builder') || "diagnostic",
        });
      } else {
        form.reset({
          businessName: engagement.businessName || "",
          industryName: engagement.industryName || "",
          engagementName: engagement.title || "",
          description: engagement.description || "",
          clientOrAdvisorId: engagement.clientId || "",
          tool: (engagement.tool as 'diagnostic' | 'kpi_builder') || "diagnostic",
        });
      }
    }
  }, [engagement, isEditMode, form, isAdmin]);

  const handleFormSubmit = async (values: EngagementFormValues) => {
    if (onSubmit) {
      onSubmit(values);
      return;
    }

    try {
      let clientId: string;
      let clientName: string = "Unknown";
      let advisorId: string | undefined;
      let advisorName: string | undefined;

      if (isAdmin && 'clientId' in values && 'advisorId' in values) {
        // Admin mode: both client and advisor selected
        clientId = values.clientId;
        advisorId = values.advisorId;
        
        if (userRoleData?.clients) {
          const selectedClient = userRoleData.clients.find(c => c.id === values.clientId);
          clientName = selectedClient?.name || "Unknown Client";
        }
        if (userRoleData?.advisors) {
          const selectedAdvisor = userRoleData.advisors.find(a => a.id === values.advisorId);
          advisorName = selectedAdvisor?.name || "Unknown Advisor";
        }
      } else if ('clientOrAdvisorId' in values) {
        // Non-admin mode: single selection
        if (userRoleData?.user_role === 'advisor' && userRoleData.clients) {
          const selectedClient = userRoleData.clients.find(c => c.id === values.clientOrAdvisorId);
          clientId = values.clientOrAdvisorId;
          clientName = selectedClient?.name || "Unknown Client";
        } else if (userRoleData?.advisors) {
          const selectedAdvisor = userRoleData.advisors.find(a => a.id === values.clientOrAdvisorId);
          clientId = values.clientOrAdvisorId; // For client role, this is actually advisor
          clientName = selectedAdvisor?.name || "Unknown Advisor";
        } else {
          clientId = values.clientOrAdvisorId;
        }
      } else {
        throw new Error('Invalid form values');
      }

      if (isEditMode && engagement) {
        await dispatch(updateEngagement({
          id: engagement.id,
          updates: {
            businessName: values.businessName,
            title: values.engagementName,
            description: values.description,
            industryName: values.industryName,
            clientId: clientId,
            clientName: clientName,
          }
        })).unwrap();
      } else {
        // Create mode - need to call API with both client_id and primary_advisor_id for admin
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const token = localStorage.getItem('auth_token');
        
        if (isAdmin && advisorId) {
          // Admin: create with both client_id and primary_advisor_id
          const response = await fetch(`${API_BASE_URL}/api/engagements`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              engagement_name: values.engagementName,
              business_name: values.businessName,
              industry: values.industryName,
              description: values.description,
              tool: values.tool,
              status: 'draft',
              client_id: clientId,
              primary_advisor_id: advisorId,
            }),
          });

          if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create engagement');
          }
        } else {
          // Non-admin: use existing Redux action
          await dispatch(createEngagement({
            clientId: clientId,
            clientName: clientName,
            businessName: values.businessName,
            title: values.engagementName,
            description: values.description,
            industryName: values.industryName,
            tool: values.tool,
            status: 'draft',
          })).unwrap();
        }
      }
      
      if (onSuccess) {
        onSuccess();
      }
      
      if (!isEditMode) {
        form.reset();
      }
    } catch (error) {
      console.error('Failed to save engagement:', error);
    }
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleFormSubmit)} className="space-y-6">
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

          {/* Admin: Show both Client and Advisor dropdowns */}
          {isAdmin && userRoleData && (
            <>
              <FormField
                control={form.control}
                name="clientId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Select Client</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a client" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {userRoleData.clients && userRoleData.clients.length > 0 ? (
                          userRoleData.clients.map((client) => (
                            <SelectItem key={client.id} value={client.id}>
                              {client.name}
                            </SelectItem>
                          ))
                        ) : (
                          <SelectItem value="none" disabled>No clients available</SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Choose the client for this engagement.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="advisorId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Select Advisor</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select an advisor" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {userRoleData.advisors && userRoleData.advisors.length > 0 ? (
                          userRoleData.advisors.map((advisor) => (
                            <SelectItem key={advisor.id} value={advisor.id}>
                              {advisor.name}
                            </SelectItem>
                          ))
                        ) : (
                          <SelectItem value="none" disabled>No advisors available</SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Choose the primary advisor for this engagement.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </>
          )}

          {/* Non-admin: Show single dropdown */}
          {!isAdmin && userRoleData && (
            <FormField
              control={form.control}
              name="clientId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Select Client</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a client" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {userRoleData.clients.map((client) => (
                        <SelectItem key={client.id} value={client.id}>
                          {client.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    Choose the client for this engagement.
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

          {/* Primary Advisor Dropdown - visible for firm/admin roles */}
          {userRoleData && userRoleData.advisors && (
            <FormField
              control={form.control}
              name="primaryAdvisorId"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Select Primary Advisor</FormLabel>
                  <Select onValueChange={field.onChange} defaultValue={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a primary advisor" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {userRoleData.advisors.map((advisor) => (
                        <SelectItem key={advisor.id} value={advisor.id}>
                          {advisor.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormDescription>
                    Choose the primary advisor for this engagement.
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

          <FormField
            control={form.control}
            name="tool"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Tool</FormLabel>
                <Select onValueChange={field.onChange} defaultValue={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a tool" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="diagnostic">Diagnostic</SelectItem>
                    <SelectItem value="kpi_builder">KPI Builder</SelectItem>
                  </SelectContent>
                </Select>
                <FormDescription>
                  Select the tool for this engagement.
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

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
