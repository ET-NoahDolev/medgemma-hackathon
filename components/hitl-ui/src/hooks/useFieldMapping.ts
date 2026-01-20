import { useMutation } from '@tanstack/react-query';
import { suggestFieldMapping, FieldMappingSuggestion } from '@/lib/api';

/**
 * Hook for suggesting field mappings based on criterion text.
 */
export function useSuggestFieldMapping() {
  return useMutation({
    mutationFn: async (criterionText: string): Promise<FieldMappingSuggestion[]> => {
      const response = await suggestFieldMapping(criterionText);
      return response.suggestions;
    },
  });
}
