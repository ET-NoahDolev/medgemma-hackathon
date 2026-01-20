import { useMutation, useQueryClient } from '@tanstack/react-query';
import { triggerExtraction } from '@/lib/api';

export function useExtractCriteria() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (protocolId: string) => triggerExtraction(protocolId),
    onSuccess: async (_data, protocolId) => {
      await queryClient.invalidateQueries({ queryKey: ['criteria', protocolId] });
    },
  });
}

