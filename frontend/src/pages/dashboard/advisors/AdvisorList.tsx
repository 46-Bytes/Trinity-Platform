import AdvisorCard from './AdvisorCard';
import type { Advisor } from '@/store/slices/firmReducer';

interface AdvisorListProps {
  advisors: Advisor[];
  filteredAdvisors: Advisor[];
  isLoading: boolean;
  onSuspend: (advisorId: string) => void;
  onReactivate: (advisorId: string) => void;
  onDelete: (advisorId: string) => void;
  onViewDetails?: (advisorId: string) => void;
  onAssociateClients?: (advisorId: string) => void;
}

export default function AdvisorList({
  advisors,
  filteredAdvisors,
  isLoading,
  onSuspend,
  onReactivate,
  onDelete,
  onViewDetails,
  onAssociateClients,
}: AdvisorListProps) {
  if (isLoading) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        Loading advisors...
      </div>
    );
  }

  if (filteredAdvisors.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        {advisors.length === 0 
          ? 'No advisors yet. Add your first advisor to get started.' 
          : 'No advisors match your search.'}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {filteredAdvisors.map((advisor) => (
        <AdvisorCard
          key={advisor.id}
          advisor={advisor}
          onSuspend={onSuspend}
          onReactivate={onReactivate}
          onDelete={onDelete}
          onViewDetails={onViewDetails}
          onAssociateClients={onAssociateClients}
        />
      ))}
    </div>
  );
}

