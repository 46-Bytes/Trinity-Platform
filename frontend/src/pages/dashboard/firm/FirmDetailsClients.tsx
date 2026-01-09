// Wrapper component that reuses ClientsPage logic but for a specific firm (superadmin view)
import { useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useAppDispatch } from '@/store/hooks';
import { fetchFirmClientsById } from '@/store/slices/firmReducer';
import ClientsPage from '@/pages/dashboard/ClientsPage';

interface FirmDetailsContext {
  firmId: string;
}

export default function FirmDetailsClients() {
  const { firmId } = useOutletContext<FirmDetailsContext>();
  const dispatch = useAppDispatch();

  // Fetch clients for this firm
  useEffect(() => {
    if (firmId) {
      dispatch(fetchFirmClientsById(firmId));
    }
  }, [dispatch, firmId]);
  
  // The ClientsPage will use the firm and clients from Redux state
  return <ClientsPage />;
}

