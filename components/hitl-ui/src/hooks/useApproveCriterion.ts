import { useMutation, useQueryClient } from '@tanstack/react-query';
import { approveCriterion, type HitlApproveRequest } from '@/lib/api';

export function useApproveCriterion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: { criterionId: string; payload: HitlApproveRequest }) =>
      approveCriterion(params.criterionId, params.payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['criteria'] });
    },
  });
}
