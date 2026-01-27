import { useMutation, useQueryClient } from '@tanstack/react-query';
import { editCriterionMapping, type HitlEditMappingRequest, type CriterionResponse } from '@/lib/api';

export function useEditCriterionMapping() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: { criterionId: string; payload: HitlEditMappingRequest }) =>
      editCriterionMapping(params.criterionId, params.payload),
    onMutate: async ({ criterionId, payload }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['criteria'] });

      // Snapshot previous value
      const previousCriteria = queryClient.getQueryData<{ criteria: CriterionResponse[] }>(['criteria']);

      // Optimistically update cache with HITL edits
      queryClient.setQueryData<{ criteria: CriterionResponse[] }>(['criteria'], (old) => {
        if (!old) return old;
        return {
          ...old,
          criteria: old.criteria.map((c) => {
            if (c.id !== criterionId) return c;
            const updated = { ...c };
            // Apply edits to HITL fields
            for (const [key, value] of Object.entries(payload.edits)) {
              const hitlKey = `hitl_${key}` as keyof CriterionResponse;
              if (hitlKey in updated) {
                (updated as Record<string, unknown>)[hitlKey] = value;
              }
            }
            updated.hitl_status = 'edited';
            return updated;
          }),
        };
      });

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
