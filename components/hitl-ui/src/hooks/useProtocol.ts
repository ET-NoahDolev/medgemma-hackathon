import { useQuery } from '@tanstack/react-query';
import { getProtocol, type ProtocolDetailResponse } from '@/lib/api';

/**
 * Hook for fetching a single protocol by ID.
 */
export function useProtocol(protocolId: string | null) {
  return useQuery<ProtocolDetailResponse>({
    queryKey: ['protocol', protocolId],
    queryFn: () => getProtocol(protocolId!),
    enabled: !!protocolId,
    refetchInterval: query => {
      const status = query.state.data?.processing_status;
      if (!status) return 2000;
      return status === 'extracting' || status === 'grounding' || status === 'pending' ? 2000 : false;
    },
  });
}
