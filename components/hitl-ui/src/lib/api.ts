const DEFAULT_API_BASE_URL = 'http://localhost:8000';

function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  return (configured ?? DEFAULT_API_BASE_URL).replace(/\/+$/, '');
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${getApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`;
  const resp = await fetch(url, init);
  const contentType = resp.headers.get('content-type') ?? '';

  if (!resp.ok) {
    const detail =
      contentType.includes('application/json')
        ? JSON.stringify(await resp.json()).slice(0, 2000)
        : (await resp.text()).slice(0, 2000);
    throw new Error(`API ${resp.status} ${resp.statusText}: ${detail}`);
  }

  if (resp.status === 204) {
    return undefined as unknown as T;
  }

  if (!contentType.includes('application/json')) {
    throw new Error(`Expected JSON response from ${url}`);
  }

  return (await resp.json()) as T;
}

export type ProtocolListItem = {
  protocol_id: string;
  title: string;
  nct_id?: string | null;
  condition?: string | null;
  phase?: string | null;
  processing_status: string;
  progress_message?: string | null;
  processed_count: number;
  total_estimated: number;
};

export type ProtocolListResponse = {
  protocols: ProtocolListItem[];
  total: number;
  skip: number;
  limit: number;
};

export type ProtocolDetailResponse = {
  protocol_id: string;
  title: string;
  document_text: string;
  nct_id?: string | null;
  condition?: string | null;
  phase?: string | null;
  criteria_count: number;
  processing_status: string;
  progress_message?: string | null;
  processed_count: number;
  total_estimated: number;
};

export type CriterionResponse = {
  id: string;
  text?: string;
  text_snippet: string;
  criterion_type?: string;
  criteria_type: string;
  entity?: string | null;
  umls_concept?: string | null;
  umls_id?: string | null;
  snomed_code?: string | null;
  snomed_codes: string[];
  calculated_by?: string | null;
  relation?: string | null;
  value?: string | null;
  unit?: string | null;
  confidence: number;
  triplet_confidence?: number | null;
  grounding_confidence?: number | null;
  logical_operator?: string | null;
  grounding_terms?: Array<Record<string, unknown>>;
  umls_mappings?: Array<{
    umls_concept?: string | null;
    umls_id?: string | null;
    snomed_code?: string | null;
    confidence?: number;
  }>;
  hitl_status?: string | null;
  hitl_entity?: string | null;
  hitl_umls_concept?: string | null;
  hitl_umls_id?: string | null;
  hitl_snomed_code?: string | null;
  hitl_relation?: string | null;
  hitl_value?: string | null;
  hitl_unit?: string | null;
  hitl_approved_at?: string | null;
  hitl_approved_by?: string | null;
};

export type CriteriaListResponse = {
  protocol_id: string;
  criteria: CriterionResponse[];
};

export type ExtractionResponse = {
  protocol_id: string;
  status: string;
  criteria_count: number;
};

export type CriterionUpdateRequest = {
  text?: string | null;
  criterion_type?: string | null;
};

export type CriterionUpdateResponse = {
  criterion_id: string;
  status: string;
  criterion: CriterionResponse;
};

export type GroundingCandidateResponse = {
  code: string;
  display: string;
  ontology: string;
  confidence: number;
};

export type FieldMappingResponse = {
  field: string;
  relation: string;
  value: string;
  confidence: number;
};

export type GroundingResponse = {
  criterion_id: string;
  candidates: GroundingCandidateResponse[];
  field_mapping: FieldMappingResponse | null;
};

export type HitlFeedbackRequest = {
  criterion_id: string;
  action:
  | 'accept'
  | 'reject'
  | 'edit'
  | 'add_code'
  | 'remove_code'
  | 'add_mapping'
  | 'remove_mapping';
  snomed_code_added?: string | null;
  snomed_code_removed?: string | null;
  field_mapping_added?: string | null;
  field_mapping_removed?: string | null;
  note?: string | null;
};

export type HitlApproveRequest = {
  user: string;
  note?: string | null;
};

export type HitlRejectRequest = {
  user: string;
  reason: string;
};

export type HitlEditMappingRequest = {
  user: string;
  edits: Record<string, unknown>;
  note?: string | null;
};

export type FieldMappingSuggestionResponse = {
  suggestions: FieldMappingResponse[];
};

export async function listProtocols(params?: {
  skip?: number;
  limit?: number;
}): Promise<ProtocolListResponse> {
  const query = new URLSearchParams();
  query.set('skip', String(params?.skip ?? 0));
  query.set('limit', String(params?.limit ?? 20));
  return requestJson<ProtocolListResponse>(`/v1/protocols?${query.toString()}`);
}

export async function getProtocol(protocolId: string): Promise<ProtocolDetailResponse> {
  return requestJson<ProtocolDetailResponse>(`/v1/protocols/${encodeURIComponent(protocolId)}`);
}

export async function listCriteria(protocolId: string): Promise<CriteriaListResponse> {
  return requestJson<CriteriaListResponse>(
    `/v1/protocols/${encodeURIComponent(protocolId)}/criteria`
  );
}

export async function triggerExtraction(protocolId: string): Promise<ExtractionResponse> {
  return requestJson<ExtractionResponse>(`/v1/protocols/${encodeURIComponent(protocolId)}/extract`, {
    method: 'POST',
  });
}

export async function updateCriterion(
  criterionId: string,
  updates: CriterionUpdateRequest
): Promise<CriterionUpdateResponse> {
  return requestJson<CriterionUpdateResponse>(`/v1/criteria/${encodeURIComponent(criterionId)}`, {
    method: 'PATCH',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(updates),
  });
}

export async function groundCriterion(criterionId: string): Promise<GroundingResponse> {
  return requestJson<GroundingResponse>(`/v1/criteria/${encodeURIComponent(criterionId)}/ground`, {
    method: 'POST',
  });
}

export async function submitHitlFeedback(payload: HitlFeedbackRequest): Promise<{ status: string }> {
  return requestJson<{ status: string }>(`/v1/hitl/feedback`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function approveCriterion(
  criterionId: string,
  payload: HitlApproveRequest
): Promise<CriterionResponse> {
  return requestJson<CriterionResponse>(`/v1/criteria/${encodeURIComponent(criterionId)}/approve`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function rejectCriterion(
  criterionId: string,
  payload: HitlRejectRequest
): Promise<CriterionResponse> {
  return requestJson<CriterionResponse>(`/v1/criteria/${encodeURIComponent(criterionId)}/reject`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function editCriterionMapping(
  criterionId: string,
  payload: HitlEditMappingRequest
): Promise<CriterionResponse> {
  return requestJson<CriterionResponse>(`/v1/criteria/${encodeURIComponent(criterionId)}/edit-mapping`, {
    method: 'PATCH',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function suggestFieldMapping(criterionText: string): Promise<FieldMappingSuggestionResponse> {
  return requestJson<FieldMappingSuggestionResponse>(`/v1/criteria/suggest-mapping`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ criterion_text: criterionText }),
  });
}

export async function uploadProtocolPdf(file: File, autoExtract: boolean = true): Promise<{
  protocol_id: string;
  title: string;
}> {
  const form = new FormData();
  form.append('file', file);
  const query = new URLSearchParams();
  query.set('auto_extract', String(autoExtract));
  const url = `${getApiBaseUrl()}/v1/protocols/upload?${query.toString()}`;
  const resp = await fetch(url, { method: 'POST', body: form });
  if (!resp.ok) {
    const text = (await resp.text()).slice(0, 2000);
    throw new Error(`API ${resp.status} ${resp.statusText}: ${text}`);
  }
  return (await resp.json()) as { protocol_id: string; title: string };
}
