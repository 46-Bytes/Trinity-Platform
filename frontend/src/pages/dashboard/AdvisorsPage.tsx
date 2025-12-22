import { useState, useEffect } from 'react';
import { Search, Plus, MoreHorizontal, User, Mail, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchFirm, fetchFirmAdvisors, addAdvisorToFirm, removeAdvisorFromFirm } from '@/store/slices/firmReducer';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';

export default function AdvisorsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [advisorToDelete, setAdvisorToDelete] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    given_name: '',
    family_name: '',
  });
  const { toast } = useToast();
  
  const dispatch = useAppDispatch();
  const { firm, advisors, isLoading, error } = useAppSelector((state) => state.firm);

  useEffect(() => {
    // Fetch firm first to get firm ID
    dispatch(fetchFirm()).then((result) => {
      if (fetchFirm.fulfilled.match(result) && result.payload) {
        dispatch(fetchFirmAdvisors(result.payload.id));
      }
    });
  }, [dispatch]);

  const filteredAdvisors = advisors.filter((advisor) => {
    const matchesSearch = 
      advisor.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      advisor.email.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const handleAddAdvisor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firm) {
      toast({
        title: 'Error',
        description: 'Firm not found',
        variant: 'destructive',
      });
      return;
    }

    setIsSubmitting(true);

    try {
      await dispatch(addAdvisorToFirm({
        firmId: firm.id,
        advisorData: {
          email: formData.email,
          name: formData.name || `${formData.given_name} ${formData.family_name}`.trim(),
        },
      })).unwrap();

      toast({
        title: 'Success',
        description: 'Advisor added successfully',
      });

      // Reset form and close dialog
      setFormData({ email: '', name: '', given_name: '', family_name: '' });
      setIsAddDialogOpen(false);
      
      // Refresh advisors list
      dispatch(fetchFirmAdvisors(firm.id));
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to add advisor',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteClick = (advisorId: string) => {
    setAdvisorToDelete(advisorId);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!firm || !advisorToDelete) return;

    try {
      await dispatch(removeAdvisorFromFirm({
        firmId: firm.id,
        advisorId: advisorToDelete,
      })).unwrap();

      toast({
        title: 'Success',
        description: 'Advisor removed successfully',
      });

      setDeleteDialogOpen(false);
      setAdvisorToDelete(null);
      
      // Refresh advisors list
      dispatch(fetchFirmAdvisors(firm.id));
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to remove advisor',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Advisors</h1>
          <p className="text-muted-foreground mt-1">Manage advisors in your firm</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button className="btn-primary">
              <Plus className="w-4 h-4 mr-2" />
              Add Advisor
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Advisor</DialogTitle>
              <DialogDescription>
                Add a new advisor to your firm. They will be able to manage client engagements.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAddAdvisor} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="advisor@example.com"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="name">Full Name</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Jane Smith"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="given_name">First Name</Label>
                  <Input
                    id="given_name"
                    value={formData.given_name}
                    onChange={(e) => setFormData({ ...formData, given_name: e.target.value })}
                    placeholder="Jane"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="family_name">Last Name</Label>
                  <Input
                    id="family_name"
                    value={formData.family_name}
                    onChange={(e) => setFormData({ ...formData, family_name: e.target.value })}
                    placeholder="Smith"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsAddDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Adding...' : 'Add Advisor'}
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {firm && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="stat-card">
            <p className="text-sm text-muted-foreground">Total Advisors</p>
            <p className="text-2xl font-heading font-bold mt-1">{advisors.length}</p>
          </div>
          <div className="stat-card">
            <p className="text-sm text-muted-foreground">Active Advisors</p>
            <p className="text-2xl font-heading font-bold mt-1">
              {advisors.filter((a) => a.is_active).length}
            </p>
          </div>
          <div className="stat-card">
            <p className="text-sm text-muted-foreground">Seats Used</p>
            <p className="text-2xl font-heading font-bold mt-1">
              {firm.seats_used} / {firm.seat_count}
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="card-trinity p-4 bg-destructive/10 border border-destructive/20">
          <p className="text-destructive">{error}</p>
        </div>
      )}

      <div className="card-trinity p-6">
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search advisors..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-trinity pl-10 w-full"
            />
          </div>
        </div>

        {isLoading ? (
          <div className="text-center py-8 text-muted-foreground">Loading advisors...</div>
        ) : filteredAdvisors.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {advisors.length === 0 ? 'No advisors yet. Add your first advisor to get started.' : 'No advisors match your search.'}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredAdvisors.map((advisor) => (
              <div key={advisor.id} className="card-trinity p-5 hover:shadow-trinity-md group">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                      <User className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-foreground group-hover:text-accent transition-colors">
                        {advisor.name || 'Unknown'}
                      </h3>
                      <p className="text-sm text-muted-foreground">{advisor.email}</p>
                    </div>
                  </div>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="p-1.5 rounded-lg hover:bg-muted transition-colors opacity-0 group-hover:opacity-100">
                        <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem className="cursor-pointer">View Details</DropdownMenuItem>
                      <DropdownMenuItem 
                        className="cursor-pointer text-destructive"
                        onClick={() => handleDeleteClick(advisor.id)}
                      >
                        Remove from Firm
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Mail className="w-4 h-4" />
                    <span>{advisor.email}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                  <div className="flex items-center gap-2">
                    <span className={cn(
                      "status-badge",
                      advisor.is_active ? "status-success" : "status-warning"
                    )}>
                      {advisor.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground capitalize">
                    {advisor.role.replace('_', ' ')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Advisor</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove this advisor from your firm? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-destructive text-destructive-foreground">
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

