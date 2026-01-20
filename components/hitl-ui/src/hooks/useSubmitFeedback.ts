import { useMutation, useQueryClient } from '@tanstack/react-query';
import { submitHitlFeedback, type HitlFeedbackRequest } from '@/lib/api';

export function useSubmitFeedback() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: HitlFeedbackRequest) => submitHitlFeedback(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['criteria'] });
    },
  });
}

