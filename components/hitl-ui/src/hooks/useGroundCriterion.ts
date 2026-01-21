import { useMutation, useQueryClient } from '@tanstack/react-query';
import { groundCriterion } from '@/lib/api';

export function useGroundCriterion(protocolId?: string | null) {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (criterionId: string) => groundCriterion(criterionId),
        onSuccess: () => {
            // Invalidate the criteria list so the new mapping shows up
            // Note: We might need to optimistically update the criteria cache for better UX
            // but invalidation ensures data consistency.
            if (protocolId) {
                queryClient.invalidateQueries({ queryKey: ['criteria', protocolId] });
            } else {
                queryClient.invalidateQueries({ queryKey: ['criteria'] });
            }
        },
    });
}
