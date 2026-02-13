import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useEffect, useMemo, useState } from "react";
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
import { createEngagement, updateEngagement, fetchUserRoleData, fetchEngagements } from "@/store/slices/engagementReducer";
import type { Engagement } from "@/store/slices/engagementReducer";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/hooks/use-toast";
import { useNavigate } from "react-router-dom";

// Base schema fields (common fields for all roles)
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
  description: z.string().optional(),
  tool: z.enum(['diagnostic', 'kpi_builder', 'bba_builder'], {
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
  } else if (userRole === 'firm_admin' || userRole === 'firm_advisor') {
    return z.object({
      ...baseSchemaFields,
      clientId: z.string().min(1, {
        message: "Please select a client.",
      }),
    });
  } else {
    // For advisor/client roles, use clientOrAdvisorId instead of clientId
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
  console.log('Props:', { mode, refreshUserData, hasEngagement: !!engagement });
  
  const dispatch = useAppDispatch();
  const { isLoading, userRoleData } = useAppSelector((state) => state.engagement);
  const { user } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  
  console.log('Redux state:', { isLoading, hasUserRoleData: !!userRoleData });
  
  const isEditMode = mode === 'edit' || !!engagement;
  const userRole = userRoleData?.user_role;
  const isAdmin = userRole === 'admin' || (userRole as string) === 'super_admin';
  const isFirmAdmin = userRole === 'firm_admin';
  const isFirmAdvisor = userRole === 'firm_advisor';
  const isFirmContext = isFirmAdmin || isFirmAdvisor;
  
  // State to track associated advisor for selected client
  const [associatedAdvisorId, setAssociatedAdvisorId] = useState<string | null>(null);
  const [isLoadingAssociation, setIsLoadingAssociation] = useState(false);
  const [associationError, setAssociationError] = useState<string | null>(null);
  
  console.log('User role detection:', { userRole, isAdmin, isFirmAdmin, isFirmAdvisor });
  
  // Create dynamic schema based on user role
  const schema = useMemo(() => createSchema(userRoleData?.user_role), [userRoleData?.user_role]);
  
  const form = useForm<EngagementFormValues>({
    resolver: zodResolver(schema),
    defaultValues: (isAdmin 
      ? {
          businessName: "",
          industryName: "",
          engagementName: "",
          description: "",
          clientId: "",
          advisorId: "",
          tool: "diagnostic" as const,
        }
      : isFirmContext
      ? {
          businessName: "",
          industryName: "",
          engagementName: "",
          description: "",
          clientId: "",
          tool: "diagnostic" as const,
        }
      : {
          businessName: "",
          industryName: "",
          engagementName: "",
          description: "",
          clientOrAdvisorId: "",
          tool: "diagnostic" as const,
        }) as any,
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
          tool: (engagement.tool as 'diagnostic' | 'kpi_builder' | 'bba_builder') || "diagnostic",
        } as any);
      } else if (isFirmContext) {
        form.reset({
          businessName: engagement.businessName || "",
          industryName: engagement.industryName || "",
          engagementName: engagement.title || "",
          description: engagement.description || "",
          clientId: engagement.clientId || "",
          tool: (engagement.tool as 'diagnostic' | 'kpi_builder' | 'bba_builder') || "diagnostic",
        });
      } else {
        form.reset({
          businessName: engagement.businessName || "",
          industryName: engagement.industryName || "",
          engagementName: engagement.title || "",
          description: engagement.description || "",
          clientOrAdvisorId: engagement.clientId || "",
          tool: (engagement.tool as 'diagnostic' | 'kpi_builder' | 'bba_builder') || "diagnostic",
        });
      }
    }
  }, [engagement, isEditMode, form, isAdmin, isFirmContext]);

  // Watch clientId for firm context
  const watchedClientId = form.watch('clientId' as any) as string | undefined;

  // Fetch associated advisor when client is selected in firm context
  useEffect(() => {
    const selectedClientId = watchedClientId;
    if (isFirmContext && selectedClientId && !isEditMode) {
      setIsLoadingAssociation(true);
      setAssociationError(null);
      setAssociatedAdvisorId(null);
      
      const fetchClientAssociation = async () => {
        try {
          const token = localStorage.getItem('auth_token');
          if (!token) {
            throw new Error('No authentication token found');
          }
          
          const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
          const response = await fetch(`${API_BASE_URL}/api/advisor-client?client_id=${selectedClientId}`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });
          
          if (!response.ok) {
            throw new Error('Failed to fetch client associations');
          }
          
          const associations = await response.json();
          if (Array.isArray(associations) && associations.length > 0) {
            // Find active association
            const activeAssociation = associations.find((a: any) => a.status === 'active');
            if (activeAssociation) {
              setAssociatedAdvisorId(activeAssociation.advisor_id);
            } else {
              setAssociationError('Client has no active advisor association');
              toast({
                title: 'Error',
                description: 'Associate advisor to client first',
                variant: 'destructive',
              });
            }
          } else {
            setAssociationError('Client has no associated advisor');
            toast({
              title: 'Error',
              description: 'Associate advisor to client first',
              variant: 'destructive',
            });
          }
        } catch (error) {
          console.error('Error fetching client associations:', error);
          setAssociationError('Failed to fetch advisor association');
          toast({
            title: 'Error',
            description: 'Failed to fetch advisor association',
            variant: 'destructive',
          });
        } finally {
          setIsLoadingAssociation(false);
        }
      };
      
      fetchClientAssociation();
    } else if (!selectedClientId) {
      setAssociatedAdvisorId(null);
      setAssociationError(null);
    }
  }, [watchedClientId, isFirmContext, isEditMode, toast]);

  // Add click handler to button to debug
  const handleButtonClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    console.log('=== BUTTON CLICKED ===');
    console.log('Button type:', e.currentTarget.type);
    console.log('Button disabled:', e.currentTarget.disabled);
    console.log('Is loading:', isLoading);
    console.log('Form state:', {
      isValid: form.formState.isValid,
      errors: form.formState.errors,
      isSubmitting: form.formState.isSubmitting,
      isDirty: form.formState.isDirty,
      touchedFields: Object.keys(form.formState.touchedFields),
    });
    console.log('Form values:', JSON.stringify(form.getValues(), null, 2));
    
    // Check if form has validation errors
    const errors = form.formState.errors;
    if (Object.keys(errors).length > 0) {
      console.error('=== FORM VALIDATION ERRORS DETECTED ===');
      console.error(JSON.stringify(errors, null, 2));
      console.error('These errors will prevent form submission!');
    } else {
      console.log('No validation errors - form should submit');
    }
    
    // Don't prevent default - let the form submit normally
  };

  const handleFormSubmit = async (values: EngagementFormValues) => {
    console.log('=== FORM SUBMISSION STARTED ===');
    console.log('Form submitted with values:', JSON.stringify(values, null, 2));
    console.log('User role data:', JSON.stringify(userRoleData, null, 2));
    console.log('Is admin:', isAdmin, 'Is firm admin:', isFirmAdmin);
    console.log('Is edit mode:', isEditMode);
    console.log('Is loading:', isLoading);
    
    if (onSubmit) {
      console.log('Custom onSubmit handler provided, calling it...');
      onSubmit(values);
      return;
    }

    try {
      console.log('=== PROCESSING FORM VALUES ===');
      let clientId: string;
      let clientName: string = "Unknown";
      let advisorId: string | undefined;
      let advisorName: string | undefined;

      if (isAdmin && 'clientId' in values && 'advisorId' in values) {
        console.log('Processing as ADMIN mode');
        // Admin mode: both client and advisor selected
        clientId = values.clientId;
        advisorId = (values as any).advisorId;
        console.log('Admin - Client ID:', clientId, 'Advisor ID:', advisorId);
        
        if (userRoleData?.clients) {
          const selectedClient = userRoleData.clients.find(c => c.id === values.clientId);
          clientName = selectedClient?.name || "Unknown Client";
          console.log('Selected client:', clientName);
        }
        if (userRoleData?.advisors) {
          const selectedAdvisor = userRoleData.advisors.find(a => a.id === values.advisorId);
          advisorName = selectedAdvisor?.name || "Unknown Advisor";
          console.log('Selected advisor:', advisorName);
        }
      } else if (isFirmContext && 'clientId' in values) {
        console.log('Processing as FIRM_ADMIN/FIRM_ADVISOR mode');
        // Firm Admin/Advisor mode: client selected, advisor comes from association
        clientId = values.clientId;
        
        // Check if client has associated advisor
        if (!associatedAdvisorId) {
          toast({
            title: 'Error',
            description: 'Associate advisor to client first',
            variant: 'destructive',
          });
          throw new Error('Associate advisor to client first');
        }
        
        advisorId = associatedAdvisorId;
        console.log('Firm Context - Client ID:', clientId, 'Associated Advisor ID:', advisorId);
        
        if (userRoleData?.clients) {
          const selectedClient = userRoleData.clients.find(c => c.id === values.clientId);
          clientName = selectedClient?.name || "Unknown Client";
          console.log('Selected client:', clientName);
        } else {
          console.warn('No clients available in userRoleData');
        }
        
        if (advisorId && userRoleData?.advisors) {
          const selectedAdvisor = userRoleData.advisors.find(a => a.id === advisorId);
          advisorName = selectedAdvisor?.name || "Unknown Advisor";
          console.log('Selected advisor:', advisorName);
        } else if (advisorId) {
          console.warn('Advisor ID provided but no advisors in userRoleData');
        }
      } else if ('clientOrAdvisorId' in values) {
        console.log('Processing as NON-ADMIN mode (advisor/client)');
        // Non-admin mode: single selection
        if (userRoleData?.user_role === 'advisor' && userRoleData.clients) {
          // Advisor selecting a client
          const selectedClient = userRoleData.clients.find(c => c.id === values.clientOrAdvisorId);
          clientId = values.clientOrAdvisorId;
          clientName = selectedClient?.name || "Unknown Client";
          // Advisor is the primary advisor (current user)
          advisorId = user?.id;
          advisorName = user?.name || "Unknown Advisor";
          console.log('Advisor mode - Client ID:', clientId, 'Client Name:', clientName, 'Advisor ID:', advisorId);
        } else if (userRoleData?.user_role === 'client' && userRoleData.advisors) {
          // Client selecting an advisor
          const selectedAdvisor = userRoleData.advisors.find(a => a.id === values.clientOrAdvisorId);
          advisorId = values.clientOrAdvisorId;
          advisorName = selectedAdvisor?.name || "Unknown Advisor";
          // Client is the client (current user)
          clientId = user?.id || "";
          clientName = user?.name || "Unknown Client";
          console.log('Client mode - Client ID:', clientId, 'Client Name:', clientName, 'Advisor ID:', advisorId, 'Advisor Name:', advisorName);
        } else {
          clientId = values.clientOrAdvisorId;
          console.log('Fallback - Client/Advisor ID:', clientId);
        }
      } else {
        console.error('Invalid form values - no matching condition');
        console.error('Values keys:', Object.keys(values));
        console.error('Is admin:', isAdmin, 'Is firm admin:', isFirmAdmin);
        throw new Error('Invalid form values');
      }
      
      console.log('=== EXTRACTED VALUES ===');
      console.log('Final Client ID:', clientId);
      console.log('Final Client Name:', clientName);
      console.log('Final Advisor ID:', advisorId);
      console.log('Final Advisor Name:', advisorName);

      if (isEditMode && engagement) {
        console.log('=== UPDATE MODE ===');
        console.log('Engagement ID:', engagement.id);
        console.log('Update payload:', {
          businessName: values.businessName,
          title: values.engagementName,
          description: values.description,
          industryName: values.industryName,
          clientId: clientId,
          clientName: clientName,
        });
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
        console.log('Update successful');
      } else {
        console.log('=== CREATE MODE ===');
        // Create mode - need to call API with both client_id and primary_advisor_id for admin/firm_admin
        const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const token = localStorage.getItem('auth_token');
        
        console.log('API Base URL:', API_BASE_URL);
        console.log('Token exists:', !!token);
        console.log('Token length:', token?.length);
        
        // Get primary advisor ID (for admin or firm_admin/firm_advisor)
        const primaryAdvisorId = advisorId || (isFirmContext ? associatedAdvisorId : undefined);
        
        console.log('=== PRIMARY ADVISOR ID RESOLUTION ===');
        console.log('advisorId from extraction:', advisorId);
        console.log('isFirmContext:', isFirmContext);
        console.log('associatedAdvisorId:', associatedAdvisorId);
        console.log('Final primaryAdvisorId:', primaryAdvisorId);
        
        // For admin or firm_admin/firm_advisor, always use direct API call (firm_id will be auto-set by backend for firm_admin)
        if (isAdmin || isFirmContext) {
          console.log('=== ADMIN/FIRM_CONTEXT PATH ===');
          // Validate that primaryAdvisorId is provided for firm_context
          if (isFirmContext && !primaryAdvisorId) {
            console.error('ERROR: Primary advisor is required for firm context but was not provided');
            console.error('Associated advisor ID:', associatedAdvisorId);
            throw new Error('Associate advisor to client first');
          }
          
          const requestPayload = {
            engagement_name: values.engagementName,
            business_name: values.businessName,
            industry: values.industryName,
            description: values.description,
            tool: values.tool,
            status: 'draft',
            client_id: clientId,
            primary_advisor_id: primaryAdvisorId,
          };
          
          console.log('=== API REQUEST PAYLOAD ===');
          console.log(JSON.stringify(requestPayload, null, 2));
          
          // Validate all required fields
          const missingFields = [];
          if (!requestPayload.engagement_name) missingFields.push('engagement_name');
          if (!requestPayload.business_name) missingFields.push('business_name');
          if (!requestPayload.industry) missingFields.push('industry');
          if (!requestPayload.tool) missingFields.push('tool');
          if (!requestPayload.client_id) missingFields.push('client_id');
          if (!requestPayload.primary_advisor_id) missingFields.push('primary_advisor_id');
          
          if (missingFields.length > 0) {
            console.error('ERROR: Missing required fields:', missingFields);
            throw new Error(`Missing required fields: ${missingFields.join(', ')}`);
          }
          
          console.log('Making API request to:', `${API_BASE_URL}/api/engagements`);
          // Admin or Firm Admin: create with both client_id and primary_advisor_id
          const response = await fetch(`${API_BASE_URL}/api/engagements`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestPayload),
          });

          console.log('=== API RESPONSE ===');
          console.log('Status:', response.status);
          console.log('Status Text:', response.statusText);
          console.log('OK:', response.ok);
          
          if (!response.ok) {
            const errorData = await response.json().catch(async () => {
              const text = await response.text();
              console.error('Failed to parse error response as JSON. Response text:', text);
              return { detail: 'Failed to create engagement' };
            });
            console.error('API Error Response:', JSON.stringify(errorData, null, 2));
            throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create engagement`);
          }
          
          const responseData = await response.json();
          console.log('API Success Response:', JSON.stringify(responseData, null, 2));
          console.log('Engagement created successfully with ID:', responseData.id);
          
          // If BBA Builder is selected, navigate to POC page
          if (values.tool === 'bba_builder') {
            if (onSuccess) {
              onSuccess();
            }
            navigate('/poc/file-upload');
            return;
          }
          
          // Call onSuccess callback to close dialog and refresh list
          if (onSuccess) {
            console.log('Calling onSuccess callback for admin/firm_admin...');
            onSuccess();
          }
          
          // Also refresh engagements list directly
          console.log('Refreshing engagements list...');
          await dispatch(fetchEngagements({}));
          console.log('Engagements list refreshed');
        } else {
          console.log('=== NON-ADMIN PATH (Direct API Call) ===');
          // For clients and advisors, use direct API call with both client_id and primary_advisor_id
          if (!clientId || !advisorId) {
            throw new Error('Both client and advisor are required to create an engagement.');
          }
          
          const requestPayload = {
            engagement_name: values.engagementName,
            business_name: values.businessName,
            industry: values.industryName,
            description: values.description,
            tool: values.tool,
            status: 'draft',
            client_id: clientId,
            primary_advisor_id: advisorId,
          };
          
          console.log('=== API REQUEST PAYLOAD (Non-Admin) ===');
          console.log(JSON.stringify(requestPayload, null, 2));
          
          // Validate all required fields
          const missingFields = [];
          if (!requestPayload.engagement_name) missingFields.push('engagement_name');
          if (!requestPayload.business_name) missingFields.push('business_name');
          if (!requestPayload.industry) missingFields.push('industry');
          if (!requestPayload.tool) missingFields.push('tool');
          if (!requestPayload.client_id) missingFields.push('client_id');
          if (!requestPayload.primary_advisor_id) missingFields.push('primary_advisor_id');
          
          if (missingFields.length > 0) {
            console.error('ERROR: Missing required fields:', missingFields);
            throw new Error(`Missing required fields: ${missingFields.join(', ')}`);
          }
          
          console.log('Making API request to:', `${API_BASE_URL}/api/engagements`);
          const response = await fetch(`${API_BASE_URL}/api/engagements`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestPayload),
          });

          console.log('=== API RESPONSE (Non-Admin) ===');
          console.log('Status:', response.status);
          console.log('Status Text:', response.statusText);
          console.log('OK:', response.ok);
          
          if (!response.ok) {
            const errorData = await response.json().catch(async () => {
              const text = await response.text();
              console.error('Failed to parse error response as JSON. Response text:', text);
              return { detail: 'Failed to create engagement' };
            });
            console.error('API Error Response:', JSON.stringify(errorData, null, 2));
            throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create engagement`);
          }
          
          const responseData = await response.json();
          console.log('API Success Response:', JSON.stringify(responseData, null, 2));
          console.log('Engagement created successfully with ID:', responseData.id);
          
          // If BBA Builder is selected, navigate to POC page
          if (values.tool === 'bba_builder') {
            console.log('BBA Builder selected, navigating to /poc/file-upload');
            if (onSuccess) {
              onSuccess();
            }
            navigate('/poc/file-upload');
            return;
          }
          
          // Call onSuccess callback to close dialog and refresh list
          if (onSuccess) {
            console.log('Calling onSuccess callback (non-admin)...');
            onSuccess();
          }
          
          // Also refresh engagements list directly
          console.log('Refreshing engagements list...');
          await dispatch(fetchEngagements({}));
          console.log('Engagements list refreshed');
        }
      }
      
      console.log('=== SUCCESS HANDLERS ===');
      // onSuccess is already called above for all paths after API call
      // No need to call it again here
      
      if (!isEditMode) {
        console.log('Resetting form...');
        form.reset();
      }
      
      console.log('=== FORM SUBMISSION COMPLETED SUCCESSFULLY ===');
    } catch (error) {
      console.error('=== FORM SUBMISSION ERROR ===');
      console.error('Error type:', error?.constructor?.name);
      console.error('Error message:', error instanceof Error ? error.message : String(error));
      console.error('Full error object:', error);
      
      if (error instanceof Error) {
        console.error('Error stack:', error.stack);
      }
      
      const errorMessage = error instanceof Error ? error.message : 'Failed to save engagement';
      console.error('Showing error alert to user:', errorMessage);
      
      // Show error to user - using alert for now, but could use toast notification
      alert(errorMessage);
      
      // Re-throw to prevent form from closing on error
      throw error;
    }
  };

  // Log form state changes to catch validation issues
  useEffect(() => {
    const formState = form.formState;
    if (Object.keys(formState.errors).length > 0) {
      console.log('=== FORM VALIDATION ERRORS DETECTED ===');
      console.log('Errors:', JSON.stringify(formState.errors, null, 2));
      console.log('Form values:', form.getValues());
    }
  }, [form.formState.errors, form]);

  return (
    <Form {...form}>
      <form 
        onSubmit={(e) => {  
          // Call the form's handleSubmit
          form.handleSubmit(handleFormSubmit)(e);
        }} 
        className="space-y-6"
      >
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

          {/* Admin or Firm Admin: Show Client dropdown */}
          {(isAdmin || isFirmContext) && userRoleData && (
            <>
              <FormField
                control={form.control}
                name="clientId"
                render={({ field }) => (
                  <FormItem className="md:col-span-2">
                    <FormLabel>Select Client</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
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

              {/* Only show advisor dropdown for super_admin/admin, not firm_admin */}
              {isAdmin && (
                <FormField
                  control={form.control}
                  name={"advisorId" as any}
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Select Advisor</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
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
              )}
            </>
          )}

          {/* Non-admin and non-firm-admin: Show single dropdown (for advisor/client roles) */}
          {!isAdmin && !isFirmAdmin && userRoleData && (
            <FormField
              control={form.control}
              name="clientOrAdvisorId"
              render={({ field }) => {
                // For advisors: show clients dropdown
                // For clients: show advisors dropdown
                const isClientRole = userRoleData.user_role === 'client';
                const items = isClientRole ? (userRoleData.advisors || []) : (userRoleData.clients || []);
                const label = isClientRole ? 'Select Advisor' : 'Select Client';
                const placeholder = isClientRole ? 'Select an advisor' : 'Select a client';
                const description = isClientRole 
                  ? 'Choose the advisor for this engagement.' 
                  : 'Choose the client for this engagement.';
                
                return (
                  <FormItem>
                    <FormLabel>{label}</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder={placeholder} />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {items.length > 0 ? (
                          items.map((item) => (
                            <SelectItem key={item.id} value={item.id}>
                              {item.name}
                            </SelectItem>
                          ))
                        ) : (
                          <SelectItem value="none" disabled>
                            {isClientRole ? 'No advisors available' : 'No clients available'}
                          </SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      {description}
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                );
              }}
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
                <Select onValueChange={field.onChange} value={field.value}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a tool" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value="diagnostic">Diagnostic</SelectItem>
                    <SelectItem value="bba_builder">BBA Builder</SelectItem>
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

        <div className="flex justify-end gap-2 pt-4">
          <Button 
            type="submit" 
            disabled={isLoading}
            onClick={handleButtonClick}
          >
            {isLoading ? (
              isEditMode ? "Updating..." : "Creating..."
            ) : (
              isEditMode ? "Update Engagement" : "Create Engagement"
            )}
          </Button>
        </div>
      </form>
    </Form>
  );
}
