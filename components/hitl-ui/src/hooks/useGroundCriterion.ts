import { useMutation, useQueryClient } from '@tanstack/react-query';
import { groundCriterion } from '@/lib/api';

export function useGroundCriterion() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (criterionId: string) => groundCriterion(criterionId),
        onSuccess: () => {
            // Invalidate the criteria list so the new mapping shows up
            // Note: We might need to optimistically update the criteria cache for better UX
            // but invalidation ensures data consistency.
            // We assume criteria query key is ['criteria', protocolId].
            // Since we don't know protocolId here easily, we can invalidate all 'criteria'.
            queryClient.invalidateQueries({ queryKey: ['criteria'] });
        },
    });
}
