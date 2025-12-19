import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, ArrowRight, FileText, CheckSquare, Calendar, Loader2 } from 'lucide-react';
import { fetchEngagements } from '@/store/slices/engagementReducer';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EngagementForm } from "@/components/engagement/form";
import { toast } from "sonner";

export default function EngagementsPage() {
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { engagements, isLoading, error } = useAppSelector((state) => state.engagement);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Fetch engagements on component mount
  useEffect(() => {
    dispatch(fetchEngagements({
      status: statusFilter !== 'all' ? statusFilter : undefined,
      search: searchQuery || undefined,
    }));
  }, [dispatch]); // Only fetch on mount

  // Refetch when filters change (with debounce for search)
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      dispatch(fetchEngagements({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchQuery || undefined,
      }));
    }, searchQuery ? 500 : 0); // Debounce search by 500ms

    return () => clearTimeout(timeoutId);
  }, [searchQuery, statusFilter, dispatch]);

  // Filter engagements locally (backend already filters, but we can do additional client-side filtering)
  const filteredEngagements = engagements.filter(e => {
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
    }));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Engagements</h1>
          <p className="text-muted-foreground mt-1">Manage client engagement workspaces</p>
        </div>
        <button className="btn-primary" onClick={() => setIsDialogOpen(true)}>
          <Plus className="w-4 h-4" />
          New Engagement
        </button>
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
          <select 
            className="input-trinity w-full sm:w-48"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="draft">Draft</option>
            <option value="on-hold">In Review</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Archived</option>
          </select>
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
                          <span className={cn(
                            "status-badge flex-shrink-0",
                            engagement.status === 'active' && "status-success",
                            engagement.status === 'on-hold' && "status-info",
                            engagement.status === 'completed' && "bg-muted text-muted-foreground",
                            engagement.status === 'draft' && "bg-yellow-100 text-yellow-800"
                          )}>
                            {statusDisplay}
                          </span>
                        </div>
                        
                        <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1.5">
                            <Calendar className="w-4 h-4" />
                            Started {formatDate(engagement.startDate)}
                          </span>
                          {engagement.industryName && (
                            <span>Industry: {engagement.industryName}</span>
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
                          <p className="font-semibold">{engagement.diagnosticsCount || 0}</p>
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
        <DialogContent className="sm:max-w-[800px]">
          <DialogHeader>
            <DialogTitle>Create New Engagement</DialogTitle>
            <DialogDescription>
              Fill in the details to create a new client engagement.
            </DialogDescription>
          </DialogHeader>
          <EngagementForm onSuccess={handleFormSuccess} mode="create" />
        </DialogContent>
      </Dialog>
    </div>
  );
}
