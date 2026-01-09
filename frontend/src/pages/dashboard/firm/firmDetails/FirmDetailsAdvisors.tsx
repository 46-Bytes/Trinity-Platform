// Wrapper component that reuses AdvisorsPage logic but for a specific firm (superadmin view)
import { useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchFirmAdvisors } from '@/store/slices/firmReducer';
import AdvisorsPage from '@/pages/dashboard/AdvisorsPage';

interface FirmDetailsContext {
  firmId: string;
}

export default function FirmDetailsAdvisors() {
  const { firmId } = useOutletContext<FirmDetailsContext>();
  const dispatch = useAppDispatch();
  const { firm } = useAppSelector((state) => state.firm);

  // Ensure advisors are fetched for this firm
  useEffect(() => {
    if (firmId && firm?.id === firmId) {
      dispatch(fetchFirmAdvisors(firmId));
    }
  }, [dispatch, firmId, firm?.id]);

  // The AdvisorsPage will use the firm from Redux state (already set by layout)
  return <AdvisorsPage />;
}

