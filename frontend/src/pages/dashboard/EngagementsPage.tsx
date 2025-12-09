import { useState } from 'react';
import { Search, Plus, Filter, ArrowRight, FileText, CheckSquare, Calendar } from 'lucide-react';
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

const mockEngagements = [
  { 
    id: '1', 
    client: 'Acme Corporation', 
    title: 'Business Strategy Review', 
    status: 'Active', 
    progress: 75, 
    startDate: 'Oct 15, 2024',
    advisor: 'Emma Thompson',
    tasks: { total: 12, completed: 9 },
    documents: 8
  },
  { 
    id: '2', 
    client: 'TechStart Inc', 
    title: 'Growth Planning', 
    status: 'Active', 
    progress: 45, 
    startDate: 'Nov 1, 2024',
    advisor: 'Emma Thompson',
    tasks: { total: 8, completed: 4 },
    documents: 5
  },
  { 
    id: '3', 
    client: 'Global Solutions', 
    title: 'Operations Optimization', 
    status: 'In Review', 
    progress: 90, 
    startDate: 'Sep 20, 2024',
    advisor: 'James Wilson',
    tasks: { total: 15, completed: 14 },
    documents: 12
  },
  { 
    id: '4', 
    client: 'Innovate Ltd', 
    title: 'Financial Restructuring', 
    status: 'Active', 
    progress: 30, 
    startDate: 'Nov 15, 2024',
    advisor: 'Lisa Anderson',
    tasks: { total: 6, completed: 2 },
    documents: 3
  },
  { 
    id: '5', 
    client: 'Pacific Traders', 
    title: 'Market Expansion Plan', 
    status: 'Completed', 
    progress: 100, 
    startDate: 'Aug 1, 2024',
    advisor: 'Emma Thompson',
    tasks: { total: 10, completed: 10 },
    documents: 15
  },
];

export default function EngagementsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const filteredEngagements = mockEngagements.filter(e => {
    const matchesSearch = e.client.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || e.status.toLowerCase().replace(' ', '-') === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleFormSuccess = () => {
    toast.success("Engagement created successfully!");
    setIsDialogOpen(false);
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
            <option value="in-review">In Review</option>
            <option value="completed">Completed</option>
          </select>
        </div>

        <div className="space-y-4">
          {filteredEngagements.map((engagement) => (
            <div 
              key={engagement.id} 
              className="p-5 rounded-xl border border-border hover:border-accent/50 hover:shadow-trinity-md transition-all cursor-pointer group"
            >
              <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                <div className="flex-1">
                  <div className="flex items-start justify-between lg:justify-start gap-3 mb-2">
                    <div>
                      <h3 className="font-semibold text-foreground group-hover:text-accent transition-colors">
                        {engagement.title}
                      </h3>
                      <p className="text-sm text-muted-foreground">{engagement.client}</p>
                    </div>
                    <span className={cn(
                      "status-badge flex-shrink-0",
                      engagement.status === 'Active' && "status-success",
                      engagement.status === 'In Review' && "status-info",
                      engagement.status === 'Completed' && "bg-muted text-muted-foreground"
                    )}>
                      {engagement.status}
                    </span>
                  </div>
                  
                  <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                      <Calendar className="w-4 h-4" />
                      Started {engagement.startDate}
                    </span>
                    <span>Advisor: {engagement.advisor}</span>
                  </div>
                </div>

                <div className="flex items-center gap-6 lg:gap-8">
                  <div className="text-center">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                      <CheckSquare className="w-4 h-4" />
                      Tasks
                    </div>
                    <p className="font-semibold">
                      {engagement.tasks.completed}/{engagement.tasks.total}
                    </p>
                  </div>
                  
                  <div className="text-center">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                      <FileText className="w-4 h-4" />
                      Docs
                    </div>
                    <p className="font-semibold">{engagement.documents}</p>
                  </div>

                  <div className="min-w-[120px]">
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-muted-foreground">Progress</span>
                      <span className="font-medium">{engagement.progress}%</span>
                    </div>
                    <div className="progress-trinity">
                      <div 
                        className="progress-trinity-bar" 
                        style={{ width: `${engagement.progress}%` }} 
                      />
                    </div>
                  </div>

                  <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-accent group-hover:translate-x-1 transition-all hidden lg:block" />
                </div>
              </div>
            </div>
          ))}
        </div>

        {filteredEngagements.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No engagements found</p>
          </div>
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
