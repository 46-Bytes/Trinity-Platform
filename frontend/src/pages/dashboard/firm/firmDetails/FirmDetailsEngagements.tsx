// Wrapper component that reuses EngagementsPage logic but for a specific firm (superadmin view)
import { useOutletContext } from 'react-router-dom';
import EngagementsPage from '@/pages/dashboard/Engagement/EngagementsPage';

interface FirmDetailsContext {
  firmId: string;
}

export default function FirmDetailsEngagements() {
  const { firmId } = useOutletContext<FirmDetailsContext>();
  
  // Pass firmId to EngagementsPage so it can filter engagements for that firm
  return <EngagementsPage firmId={firmId} />;
}

