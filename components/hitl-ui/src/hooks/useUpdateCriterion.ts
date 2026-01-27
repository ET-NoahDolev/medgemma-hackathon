import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateCriterion, type CriterionUpdateRequest, type CriterionResponse } from '@/lib/api';

export function useUpdateCriterion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (args: { criterionId: string; updates: CriterionUpdateRequest }) =>
      updateCriterion(args.criterionId, args.updates),
    onMutate: async ({ criterionId, updates }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['criteria'] });

      // Snapshot previous value
      const previousCriteria = queryClient.getQueryData<{ criteria: CriterionResponse[] }>(['criteria']);

      // Optimistically update cache
      queryClient.setQueryData<{ criteria: CriterionResponse[] }>(['criteria'], (old) => {
        if (!old) return old;
        return {
          ...old,
          criteria: old.criteria.map((c) =>
            c.id === criterionId
              ? {
                  ...c,
                  ...(updates.text !== undefined && { text_snippet: updates.text, text: updates.text }),
                  ...(updates.criterion_type !== undefined && {
                    criterion_type: updates.criterion_type,
                    criteria_type: updates.criterion_type,
                  }),
                }
              : c
          ),
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

