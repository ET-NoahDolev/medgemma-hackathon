import { useQuery } from '@tanstack/react-query';
import { listCriteria, type CriteriaListResponse } from '@/lib/api';

/**
 * Hook for fetching criteria for a protocol.
 */
export function useCriteria(protocolId: string | null) {
  return useQuery({
    queryKey: ['criteria', protocolId],
    queryFn: () => listCriteria(protocolId!),
    enabled: !!protocolId,
  });
}

export type { CriteriaListResponse };
