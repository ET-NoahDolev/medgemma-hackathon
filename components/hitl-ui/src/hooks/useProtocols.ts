import { useQuery } from '@tanstack/react-query';
import { listProtocols } from '@/lib/api';

export function useProtocols(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ['protocols', params?.skip ?? 0, params?.limit ?? 20],
    queryFn: () => listProtocols(params),
  });
}

