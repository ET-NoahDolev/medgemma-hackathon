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
  });
}
