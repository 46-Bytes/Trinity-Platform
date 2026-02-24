import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, ArrowRight, FileText, CheckSquare, Calendar, Loader2, Users, Trash2, UserPlus } from 'lucide-react';
import { fetchEngagements, fetchUserRoleData, deleteEngagement } from '@/store/slices/engagementReducer';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { cn } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { EngagementForm } from "@/components/engagement/form";
import { SecondaryAdvisorDialog } from './SecondaryAdvisorDialog';
import { AddClientsDialog } from '@/components/engagement/AddClientsDialog';
import { DeleteEngagementDialog } from './DeleteEngagementDialog';
import { toast } from "sonner";
import type { Engagement } from '@/store/slices/engagementReducer';
import { Button } from '@/components/ui/button';

interface EngagementsPageProps {
  firmId?: string;
}

export default function EngagementsPage({ firmId }: EngagementsPageProps = {}) {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { engagements, isLoading, error } = useAppSelector((state) => state.engagement);
  const { user } = useAuth();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isSecondaryAdvisorDialogOpen, setIsSecondaryAdvisorDialogOpen] = useState(false);
  const [isAddClientsDialogOpen, setIsAddClientsDialogOpen] = useState(false);
  const [selectedEngagement, setSelectedEngagement] = useState<Engagement | null>(null);
  const [engagementToDelete, setEngagementToDelete] = useState<Engagement | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  
  const isClient = user?.role === 'client';
  const isFirmAdvisor = user?.role === 'firm_advisor';
  const canDeleteEngagements = user && ['super_admin', 'admin', 'firm_admin'].includes(user.role);
  const canManageSecondaryAdvisors = user && ['advisor', 'firm_advisor', 'firm_admin', 'admin', 'super_admin'].includes(user.role);
  const canManageClients = user && ['advisor', 'firm_advisor', 'firm_admin', 'admin', 'super_admin'].includes(user.role);

  // Fetch user role data for firm advisors to get advisors list
  useEffect(() => {
    if (isFirmAdvisor) {
      dispatch(fetchUserRoleData());
    }
  }, [dispatch, isFirmAdvisor]);

  // Fetch engagements on component mount
  useEffect(() => {
    dispatch(fetchEngagements({
      status: statusFilter !== 'all' ? statusFilter : undefined,
      search: searchQuery || undefined,
      firm_id: firmId,
    }));
  }, [dispatch, firmId]); // Only fetch on mount

  // Refetch when filters change (with debounce for search)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      dispatch(fetchEngagements({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchQuery || undefined,
        firm_id: firmId,
      }));
    }, searchQuery ? 500 : 0); // Debounce search by 500ms

    return () => clearTimeout(timeoutId);
  }, [searchQuery, statusFilter, dispatch, firmId]);

  // Filter engagements locally (backend already filters, but we can do additional client-side filtering)
  const filteredEngagements = engagements.filter(e => {
    if (e.is_deleted) return false;
    const matchesSearch = !searchQuery || 
      e.clientName?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.businessName?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = statusFilter === 'all' || 
      e.status.toLowerCase() === statusFilter.toLowerCase() ||
      (statusFilter === 'in-review' && e.status === 'on-hold');
    
    return matchesSearch && matchesStatus;
  });

  // Calculate progress percentage (tasks completed / total tasks)
  const calculateProgress = (engagement: typeof engagements[0]) => {
    const totalTasks = engagement.tasksCount || 0;
    const completedTasks = totalTasks - (engagement.pendingTasksCount || 0);
    if (totalTasks === 0) return 0;
    return Math.round((completedTasks / totalTasks) * 100);
  };

  // Format date for display
  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateString;
    }
  };

  // Format status for display
  const formatStatus = (status: string) => {
    const statusMap: Record<string, string> = {
      'active': 'Active',
      'draft': 'Draft',
      'on-hold': 'In Review',
      'completed': 'Completed',
      'cancelled': 'Archived',
    };
    return statusMap[status.toLowerCase()] || status;
  };

  const handleFormSuccess = () => {
    toast.success("Engagement created successfully!");
    setIsDialogOpen(false);
    // Refetch engagements after creating new one
    dispatch(fetchEngagements({
      status: statusFilter !== 'all' ? statusFilter : undefined,
      search: searchQuery || undefined,
      firm_id: firmId,
    }));
  };

  const handleManageSecondaryAdvisors = (engagement: Engagement, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent navigation to engagement detail
    setSelectedEngagement(engagement);
    setIsSecondaryAdvisorDialogOpen(true);
  };

  const handleSecondaryAdvisorDialogClose = () => {
    setIsSecondaryAdvisorDialogOpen(false);
    setSelectedEngagement(null);
  };

  const handleManageClients = (engagement: Engagement, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent navigation to engagement detail
    setSelectedEngagement(engagement);
    setIsAddClientsDialogOpen(true);
  };

  const handleAddClientsDialogClose = () => {
    setIsAddClientsDialogOpen(false);
    setSelectedEngagement(null);
  };

  const handleDeleteClick = (engagement: Engagement, e: React.MouseEvent) => {
    e.stopPropagation();
    setEngagementToDelete(engagement);
    setIsDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!engagementToDelete) return;

    try {
      setIsDeleting(true);
      await dispatch(deleteEngagement(engagementToDelete.id)).unwrap();
      toast.success('Engagement deleted successfully');
      setIsDeleteDialogOpen(false);
      setEngagementToDelete(null);
    } catch (err: any) {
      toast.error(err?.message || 'Failed to delete engagement');
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Engagements</h1>
          <p className="text-muted-foreground mt-1">Manage client engagement workspaces</p>
        </div>
        {!isClient && (
          <button className="btn-primary" onClick={() => setIsDialogOpen(true)}>
            <Plus className="w-4 h-4" />
            New Engagement
          </button>
        )}
      </div>

      <div className="card-trinity p-6">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search engagements..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-trinity pl-10 w-full"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full sm:w-[180px]">
              <SelectValue placeholder="All Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="on-hold">In Review</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="cancelled">Archived</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
            <span className="ml-2 text-muted-foreground">Loading engagements...</span>
          </div>
        )}

        {error && !isLoading && (
          <div className="text-center py-12">
            <p className="text-destructive mb-2">Error loading engagements</p>
            <p className="text-sm text-muted-foreground">{error}</p>
            <button
              onClick={() => dispatch(fetchEngagements({
                status: statusFilter !== 'all' ? statusFilter : undefined,
                search: searchQuery || undefined,
                firm_id: firmId,
              }))}
              className="btn-primary mt-4"
            >
              Retry
            </button>
          </div>
        )}

        {!isLoading && !error && (
          <>
            <div className="space-y-4">
              {filteredEngagements.map((engagement) => {
                const progress = calculateProgress(engagement);
                const statusDisplay = formatStatus(engagement.status);
                
                return (
                <div 
                    key={engagement.id} 
                    onClick={() => navigate(`/dashboard/engagements/${engagement.id}`)}
                    className="p-5 rounded-xl border border-border hover:border-accent/50 hover:shadow-trinity-md transition-all cursor-pointer group"
                  >
                    <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                      <div className="flex-1">
                      <div className="flex items-start justify-between lg:justify-start gap-3 mb-2">
                        <div>
                            <h3 className="font-semibold text-foreground group-hover:text-accent transition-colors">
                              {engagement.title}
                            </h3>
                            <p className="text-sm text-muted-foreground">
                              {engagement.clientName || engagement.businessName}
                            </p>
                          </div>
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            "status-badge flex-shrink-0",
                            engagement.status === 'active' && "status-success",
                            engagement.status === 'on-hold' && "status-info",
                            engagement.status === 'completed' && "bg-muted text-muted-foreground",
                            engagement.status === 'draft' && "bg-yellow-100 text-yellow-800"
                          )}>
                            {statusDisplay}
                          </span>
                          {canDeleteEngagements && (
                            <button
                              type="button"
                              onClick={(e) => handleDeleteClick(engagement, e)}
                              className="p-1.5 rounded-full hover:bg-destructive/10 text-destructive transition-colors"
                              aria-label="Delete engagement"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                        </div>
                        
                        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1.5">
                            <Calendar className="w-4 h-4" />
                            Started {formatDate(engagement.startDate)}
                          </span>
                          {engagement.clientNames && engagement.clientNames.length > 0 ? (
                            <span>Clients: {engagement.clientNames.join(', ')}</span>
                          ) : engagement.clientName ? (
                            <span>Client: {engagement.clientName}</span>
                          ) : null}
                          {engagement.advisorName && (
                            <span>Advisor: {engagement.advisorName}</span>
                          )}
                          {engagement.industryName && (
                            <span>Industry: {engagement.industryName}</span>
                          )}
                          {canManageSecondaryAdvisors && (
                            <button
                              type="button"
                              onClick={(e) => handleManageSecondaryAdvisors(engagement, e)}
                              className="flex items-center gap-1.5 text-accent hover:text-accent/80 transition-colors"
                              title="Manage secondary advisors"
                            >
                              <Users className="w-4 h-4" />
                              {engagement.assignedUsers?.length || 0} Secondary
                            </button>
                          )}
                          {canManageClients && (
                            <button
                              type="button"
                              onClick={(e) => handleManageClients(engagement, e)}
                              className="flex items-center gap-1.5 text-accent hover:text-accent/80 transition-colors"
                              title="Manage clients"
                            >
                              <UserPlus className="w-4 h-4" />
                              Add Clients
                            </button>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-6 lg:gap-8">
                        <div className="text-center">
                          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                            <CheckSquare className="w-4 h-4" />
                            Tasks
                          </div>
                          <p className="font-semibold">
                            {(engagement.tasksCount || 0) - (engagement.pendingTasksCount || 0)}/{engagement.tasksCount || 0}
                          </p>
                        </div>
                        
                        <div className="text-center">
                          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                            <FileText className="w-4 h-4" />
                            Docs
                          </div>
                          <p className="font-semibold">{engagement.documentsCount || 0}</p>
                        </div>

                        <div className="min-w-[120px]">
                          <div className="flex items-center justify-between text-sm mb-1">
                            <span className="text-muted-foreground">Progress</span>
                            <span className="font-medium">{progress}%</span>
                          </div>
                          <div className="progress-trinity">
                            <div 
                              className="progress-trinity-bar" 
                              style={{ width: `${progress}%` }} 
                            />
                          </div>
                        </div>

                        <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-accent group-hover:translate-x-1 transition-all hidden lg:block" />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {filteredEngagements.length === 0 && !isLoading && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No engagements found</p>
                {searchQuery && (
                  <p className="text-sm text-muted-foreground mt-2">
                    Try adjusting your search or filters
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* New Engagement Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-[800px] max-h-[95vh] flex flex-col">
          <DialogHeader>
            <DialogTitle>Create New Engagement</DialogTitle>
            <DialogDescription>
              Fill in the details to create a new client engagement.
            </DialogDescription>
          </DialogHeader>
          <div className="overflow-y-auto flex-1 pr-2">
            {isDialogOpen && (
              <EngagementForm 
                onSuccess={handleFormSuccess} 
                mode="create" 
                refreshUserData={true}
              />
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Engagement Dialog */}
      <DeleteEngagementDialog
        open={isDeleteDialogOpen}
        title={engagementToDelete?.title}
        isDeleting={isDeleting}
        onCancel={() => {
          if (isDeleting) return;
          setIsDeleteDialogOpen(false);
          setEngagementToDelete(null);
        }}
        onConfirm={handleConfirmDelete}
      />

      {/* Manage Secondary Advisors Dialog */}
      {!isClient && canManageSecondaryAdvisors && (
        <SecondaryAdvisorDialog
          open={isSecondaryAdvisorDialogOpen}
          onOpenChange={handleSecondaryAdvisorDialogClose}
          engagement={selectedEngagement}
          firmId={firmId}
          statusFilter={statusFilter}
          searchQuery={searchQuery}
          onSuccess={() => {
            // Refetch engagements after successful update
            dispatch(fetchEngagements({
              status: statusFilter !== 'all' ? statusFilter : undefined,
              search: searchQuery || undefined,
              firm_id: firmId,
            }));
          }}
        />
      )}

      {/* Manage Clients Dialog */}
      {!isClient && canManageClients && (
        <AddClientsDialog
          open={isAddClientsDialogOpen}
          onOpenChange={handleAddClientsDialogClose}
          engagement={selectedEngagement}
          firmId={firmId}
          statusFilter={statusFilter}
          searchQuery={searchQuery}
          onSuccess={() => {
            // Refetch engagements after successful update
            dispatch(fetchEngagements({
              status: statusFilter !== 'all' ? statusFilter : undefined,
              search: searchQuery || undefined,
              firm_id: firmId,
            }));
          }}
        />
      )}
    </div>
  );
}
