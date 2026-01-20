import { useQuery } from '@tanstack/react-query';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Criterion {
  id: string;
  text: string;
  criterion_type: string;
  confidence: number;
  snomed_codes: string[];
}

export interface CriteriaListResponse {
  protocol_id: string;
  criteria: Criterion[];
}

/**
 * Fetch criteria for a protocol.
 */
async function fetchCriteria(protocolId: string): Promise<CriteriaListResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/protocols/${protocolId}/criteria`);

  if (!response.ok) {
    throw new Error(`Failed to fetch criteria: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Hook for fetching criteria for a protocol.
 */
export function useCriteria(protocolId: string | null) {
  return useQuery({
    queryKey: ['criteria', protocolId],
    queryFn: () => fetchCriteria(protocolId!),
    enabled: !!protocolId,
  });
}
