// Wrapper component that reuses EngagementsPage logic but for a specific firm (superadmin view)
import { useOutletContext } from 'react-router-dom';
import EngagementsPage from '@/pages/dashboard/Engagement/EngagementsPage';

interface FirmDetailsContext {
  firmId: string;
}

export default function FirmDetailsEngagements() {
  const { firmId } = useOutletContext<FirmDetailsContext>();
  
  // The EngagementsPage will use engagements from Redux state
  // Backend filters by user's firm, so for superadmin we need to use firm-specific endpoint
  return <EngagementsPage />;
}

