import { useMutation, useQueryClient } from '@tanstack/react-query';
import { approveCriterion, type HitlApproveRequest, type CriterionResponse } from '@/lib/api';

export function useApproveCriterion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: { criterionId: string; payload: HitlApproveRequest }) =>
      approveCriterion(params.criterionId, params.payload),
    onMutate: async ({ criterionId }) => {
      // Cancel outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['criteria'] });

      // Snapshot previous value for rollback
      const previousCriteria = queryClient.getQueryData<{ criteria: CriterionResponse[] }>(['criteria']);

      // Optimistically update cache
      queryClient.setQueryData<{ criteria: CriterionResponse[] }>(['criteria'], (old) => {
        if (!old) return old;
        return {
          ...old,
          criteria: old.criteria.map((c) =>
            c.id === criterionId
              ? { ...c, hitl_status: 'approved' as const }
              : c
          ),
        };
      });

      // Return context for rollback
      return { previousCriteria };
    },
    onError: (_err, _variables, context) => {
      // Rollback on error
      if (context?.previousCriteria) {
        queryClient.setQueryData(['criteria'], context.previousCriteria);
      }
    },
    onSettled: () => {
      // Sync with server
      void queryClient.invalidateQueries({ queryKey: ['criteria'] });
    },
  });
}
