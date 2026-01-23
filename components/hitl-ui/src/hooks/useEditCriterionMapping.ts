import { useMutation, useQueryClient } from '@tanstack/react-query';
import { editCriterionMapping, type HitlEditMappingRequest } from '@/lib/api';

export function useEditCriterionMapping() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: { criterionId: string; payload: HitlEditMappingRequest }) =>
      editCriterionMapping(params.criterionId, params.payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['criteria'] });
    },
  });
}
