// Wrapper component that reuses TasksPage logic but for a specific firm (superadmin view)
import { useOutletContext } from 'react-router-dom';
import TasksPage from '@/pages/dashboard/TasksPage';

interface FirmDetailsContext {
  firmId: string;
}

export default function FirmDetailsTasks() {
  const { firmId } = useOutletContext<FirmDetailsContext>();
  
  // The TasksPage will use tasks from Redux state
  return <TasksPage />;
}

