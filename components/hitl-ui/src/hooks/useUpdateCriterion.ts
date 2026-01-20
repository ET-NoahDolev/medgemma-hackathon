import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateCriterion, type CriterionUpdateRequest } from '@/lib/api';

export function useUpdateCriterion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (args: { criterionId: string; updates: CriterionUpdateRequest }) =>
      updateCriterion(args.criterionId, args.updates),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['criteria'] });
    },
  });
}

