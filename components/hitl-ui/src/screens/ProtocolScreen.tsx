import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { GlassButton } from '@/components/ui/glass-button';
import { Card, CardContent } from '@/components/ui/card';
import { ConfidenceChip } from '@/components/common/ConfidenceChip';
import { Badge } from '@/components/ui/badge';
import { CriteriaEditPanel } from '@/features/protocols/components/CriteriaEditPanel';
import { SourceMaterialsPanel } from '@/features/protocols/components/SourceMaterialsPanel';
import { useCriteria } from '@/hooks/useCriteria';
import { useExtractCriteria } from '@/hooks/useExtractCriteria';
import { useSubmitFeedback } from '@/hooks/useSubmitFeedback';
import { useApproveCriterion } from '@/hooks/useApproveCriterion';
import { useUpdateCriterion } from '@/hooks/useUpdateCriterion';
import { useProtocol } from '@/hooks/useProtocol';
import { MappingDisplay } from '@/features/mapping/components/MappingDisplay';
import { EditMappingModal } from '@/features/mapping/components/EditMappingModal';
import {
  Upload,
  FileText,
  CheckCircle2,
  Edit2,
  Sparkles,
  Info,
  FolderOpen,
} from 'lucide-react';
import { LinearProgress } from '@mui/material';
import { Timeline, TimelineConnector, TimelineContent, TimelineDot, TimelineItem, TimelineSeparator } from '@mui/lab';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { toast } from 'sonner';

interface Criterion {
  id: string;
  type: 'inclusion' | 'exclusion';
  text: string;
  confidence: number;
  status: 'ai-suggested' | 'approved' | 'edited' | 'rejected';
  evidenceSnippet?: string;
  snomedCodes?: string[];
  snomedCode?: string | null;
  entity?: string | null;
  umlsConcept?: string | null;
  umlsId?: string | null;
  umlsMappings?: Array<{
    umls_concept?: string | null;
    umls_id?: string | null;
    snomed_code?: string | null;
    confidence?: number;
  }>;
  logicalOperator?: string | null;
  calculatedBy?: string | null;
  relation?: string | null;
  value?: string | null;
  unit?: string | null;
  hitlEntity?: string | null;
  hitlUmlsConcept?: string | null;
  hitlUmlsId?: string | null;
  hitlSnomedCode?: string | null;
  hitlRelation?: string | null;
  hitlValue?: string | null;
  hitlUnit?: string | null;
  fieldMapping?: {
    field: string;
    relation: string;
    value: string;
  } | null;
}

export function ProtocolScreen() {
  const { protocolId } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [activeProtocolId, setActiveProtocolId] = useState<string | null>(protocolId ?? null);
  const [activeProtocolTitle, setActiveProtocolTitle] = useState<string>('Protocol');
  const [uploaded, setUploaded] = useState(!!protocolId);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [editPanelOpen, setEditPanelOpen] = useState(false);
  const [selectedCriterion, setSelectedCriterion] = useState<Criterion | null>(null);
  const [sourceMaterialsPanelOpen, setSourceMaterialsPanelOpen] = useState(false);

  const {
    data: protocolData,
    isLoading: isProtocolLoading,
    error: protocolError,
  } = useProtocol(activeProtocolId);

  const status = protocolData?.processing_status ?? 'pending';
  const shouldPollCriteria =
    status === 'pending' || status === 'extracting' || status === 'grounding';

  const { data: criteriaData, isLoading, error, refetch } = useCriteria(activeProtocolId, {
    pollIntervalMs: shouldPollCriteria ? 1500 : false,
  });
  const extractCriteria = useExtractCriteria();
  const submitFeedback = useSubmitFeedback();
  const approveCriterion = useApproveCriterion();
  const updateCriterion = useUpdateCriterion();

  const sourceDocuments = useMemo(() => {
    if (!protocolData?.document_text) return [];
    return [
      {
        id: protocolData.protocol_id,
        name: protocolData.title || activeProtocolTitle,
        content: protocolData.document_text,
        type: 'protocol' as const,
      },
    ];
  }, [activeProtocolTitle, protocolData]);

  const apiMappedCriteria: Criterion[] = useMemo(() => {
    const apiCriteria = criteriaData?.criteria ?? [];
    return apiCriteria.map(c => ({
      id: c.id,
      type: (c.criteria_type as 'inclusion' | 'exclusion') ?? 'inclusion',
      text: c.text_snippet,
      confidence: c.confidence,
      status:
        c.hitl_status === 'approved'
          ? 'approved'
          : c.hitl_status === 'edited'
            ? 'edited'
            : c.hitl_status === 'rejected'
              ? 'rejected'
              : 'ai-suggested',
      evidenceSnippet: undefined,
      snomedCodes: c.snomed_codes ?? [],
      snomedCode: c.snomed_code ?? null,
      entity: c.entity ?? null,
      umlsConcept: c.umls_concept ?? null,
      umlsId: c.umls_id ?? null,
      umlsMappings: c.umls_mappings ?? [],
      logicalOperator: c.logical_operator ?? null,
      calculatedBy: c.calculated_by ?? null,
      relation: c.relation ?? null,
      value: c.value ?? null,
      unit: c.unit ?? null,
      hitlEntity: c.hitl_entity ?? null,
      hitlUmlsConcept: c.hitl_umls_concept ?? null,
      hitlUmlsId: c.hitl_umls_id ?? null,
      hitlSnomedCode: c.hitl_snomed_code ?? null,
      hitlRelation: c.hitl_relation ?? null,
      hitlValue: c.hitl_value ?? null,
      hitlUnit: c.hitl_unit ?? null,
      fieldMapping: c.entity
        ? {
            field: c.entity,
            relation: c.relation ?? '',
            value: c.value ?? '',
          }
        : null,
    }));
  }, [criteriaData]);

  useEffect(() => {
    if (protocolData?.title) {
      // eslint-disable-next-line
      setActiveProtocolTitle(protocolData.title);
    }
  }, [protocolData?.title]);

  useEffect(() => {
    setActiveProtocolId(protocolId ?? null);
    setUploaded(!!protocolId);
    setCriteria([]);
    setSelectedCriterion(null);
  }, [protocolId]);

  // Keep existing local edits/statuses, but refresh text from API.
  useEffect(() => {
    if (!uploaded) return;
    if (!activeProtocolId) return;

    // eslint-disable-next-line
    setCriteria(prev => {
      const prevById = new Map(prev.map(c => [c.id, c]));
      return apiMappedCriteria.map(c => {
        const prior = prevById.get(c.id);
        if (!prior) return c;
        return {
          ...c,
          status: prior.status,
          evidenceSnippet: prior.evidenceSnippet,
        };
      });
    });
  }, [activeProtocolId, apiMappedCriteria, uploaded]);

  // Criteria polling is handled by React Query via useCriteria(refetchInterval).

  const handleApprove = (id: string) => {
    approveCriterion.mutate({ criterionId: id, payload: { user: 'reviewer' } });
    setCriteria(prev => prev.map(c => (c.id === id ? { ...c, status: 'approved' as const } : c)));
  };

  const handleOpenEditPanel = (criterion: Criterion) => {
    setSelectedCriterion(criterion);
    setEditPanelOpen(true);
  };

  const handleSaveEditPanel = (updates: { text: string; type: string; rationale?: string }) => {
    if (selectedCriterion) {
      const nextType =
        updates.type === 'not-applicable' ? selectedCriterion.type : (updates.type as Criterion['type']);

      updateCriterion.mutate({
        criterionId: selectedCriterion.id,
        updates: {
          text: updates.text,
          criterion_type: nextType,
        },
      });

      setCriteria(prev =>
        prev.map(c =>
          c.id === selectedCriterion.id
            ? { ...c, text: updates.text, type: nextType, status: 'edited' as const }
            : c
        )
      );

      // Log to audit trail
      toast.success('Criterion updated', {
        description: `Changes saved: ${updates.rationale}`,
      });
    }
  };

  const approvedCount = criteria.filter(c => c.status === 'approved').length;
  const needsReviewCount = criteria.filter(c => c.status === 'ai-suggested').length;

  const handleSelectFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleRunExtraction = () => {
    if (!activeProtocolId) return;
    // Non-blocking: use mutate instead of mutateAsync
    extractCriteria.mutate(activeProtocolId, {
      onSuccess: () => {
        setCriteria([]);
        toast.success('Extraction started. Criteria will appear as they are processed.');
      },
      onError: () => {
        toast.error('Failed to start extraction');
      },
    });
  };

  // State for mapping modal
  const [mappingModalOpen, setMappingModalOpen] = useState(false);

  const handleOpenMappingModal = (criterion: Criterion) => {
    setSelectedCriterion(criterion);
    setMappingModalOpen(true);
  };

  const handleSaveMapping = () => {
    // Refresh to show new mappings
    refetch();
  };

  if (!uploaded) {
    return (
      <div className="flex flex-col h-full items-center justify-center text-center p-8">
        <FileText className="w-10 h-10 text-teal-600 mb-3" />
        <h2 className="text-gray-900 mb-1">No protocol selected</h2>
        <p className="text-sm text-gray-600 mb-4">Go back to the protocol list to upload or select one.</p>
        <Button onClick={() => navigate('/')}>Back to Protocols</Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Link to="/">
                <Button variant="ghost" size="sm" className="gap-1 -ml-2" style={{ fontSize: '14px' }}>
                  Back to Protocols
                </Button>
              </Link>
              <FileText className="w-6 h-6 text-teal-600" />
              <h1 className="font-semibold text-gray-900">
                {activeProtocolTitle}
              </h1>
            </div>
            <p className="text-sm text-gray-600">
              Extracted {criteria.length} criteria
            </p>
            <div className="flex gap-4 mt-3 text-sm">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                <span className="text-gray-600">{approvedCount} approved</span>
              </div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-orange-600" />
                <span className="text-gray-600">{needsReviewCount} AI suggested</span>
              </div>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => setSourceMaterialsPanelOpen(true)}
              disabled={sourceDocuments.length === 0 || isProtocolLoading}
            >
              <FolderOpen className="w-4 h-4 mr-2" />
              Source Materials
            </Button>
            <Button
              variant="outline"
              onClick={handleRunExtraction}
              disabled={!activeProtocolId || extractCriteria.isPending}
            >
              <Sparkles className="w-4 h-4 mr-2" />
              {extractCriteria.isPending ? 'Starting…' : 'Re-run extraction'}
            </Button>
            <GlassButton variant="primary">Finalize & Deploy</GlassButton>
          </div>
        </div>

        <Alert className="mt-4 border-blue-300 bg-blue-50">
          <Info className="h-4 w-4 text-blue-600" />
          <AlertDescription className="text-blue-800">
            AI has extracted {criteria.length} criteria from your protocol. Review each criterion
            and approve or edit as needed. Glass-box tooltips show evidence and confidence scores.
          </AlertDescription>
        </Alert>

        {protocolData && (
          <div className="mt-4">
            <div className="flex items-center justify-between text-sm text-gray-600">
              <span>
                Status:{' '}
                <span className="font-medium text-gray-900">
                  {protocolData.processing_status ?? 'pending'}
                </span>
              </span>
              <span>
                Extracted{' '}
                <span className="font-medium text-gray-900">{protocolData.processed_count ?? 0}</span>{' '}
                criteria
              </span>
            </div>
            {(protocolData as any).progress_message && (
              <div className="mt-2 text-sm text-gray-600">{(protocolData as any).progress_message}</div>
            )}

            <div className="mt-2">
              {protocolData.total_estimated && protocolData.total_estimated > 0 ? (
                <LinearProgress
                  variant="determinate"
                  value={Math.min(
                    100,
                    (100 * (protocolData.processed_count ?? 0)) / protocolData.total_estimated
                  )}
                />
              ) : (
                <LinearProgress variant="indeterminate" />
              )}
            </div>

            <div className="mt-4">
              <Timeline sx={{ p: 0, m: 0 }}>
                <TimelineItem sx={{ '&:before': { flex: 0, padding: 0 } }}>
                  <TimelineSeparator>
                    <TimelineDot color="success" />
                    <TimelineConnector />
                  </TimelineSeparator>
                  <TimelineContent sx={{ py: 0.5 }}>
                    <span className="text-sm text-gray-900">Upload</span>
                  </TimelineContent>
                </TimelineItem>

                <TimelineItem sx={{ '&:before': { flex: 0, padding: 0 } }}>
                  <TimelineSeparator>
                    <TimelineDot
                      color={
                        protocolData.processing_status === 'failed'
                          ? 'error'
                          : protocolData.processing_status === 'completed'
                            ? 'success'
                            : protocolData.processing_status === 'extracting'
                              ? 'primary'
                              : 'grey'
                      }
                    />
                    <TimelineConnector />
                  </TimelineSeparator>
                  <TimelineContent sx={{ py: 0.5 }}>
                    <span className="text-sm text-gray-900">Extraction</span>
                  </TimelineContent>
                </TimelineItem>

                <TimelineItem sx={{ '&:before': { flex: 0, padding: 0 } }}>
                  <TimelineSeparator>
                    <TimelineDot color={protocolData.processing_status === 'completed' ? 'primary' : 'grey'} />
                  </TimelineSeparator>
                  <TimelineContent sx={{ py: 0.5 }}>
                    <span className="text-sm text-gray-900">Review</span>
                  </TimelineContent>
                </TimelineItem>
              </Timeline>
            </div>
          </div>
        )}

        {(error || protocolError) && (
          <Alert className="mt-4 border-red-300 bg-red-50">
            <Info className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-800">
              Error loading data: {error?.message ?? protocolError?.message}
            </AlertDescription>
          </Alert>
        )}
      </div>

      {/* Criteria List */}
      <div className="flex-1 min-h-0 overflow-y-auto bg-transparent">
        <div className="p-6 max-w-5xl mx-auto">
          {/* Extraction / Loading State */}
          {((isLoading && criteria.length === 0) || (uploaded && criteria.length === 0)) && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600 mb-4"></div>
              <h3 className="text-lg font-medium text-gray-900">Extracting criteria...</h3>
              <p className="text-gray-500 mt-2 max-w-sm">
                Our AI is analyzing the protocol document to identify inclusion and exclusion criteria.
                This usually takes 10-20 seconds.
              </p>
            </div>
          )}

          {/* Helper to render list */}
          {[
            { type: 'inclusion', label: 'Inclusion Criteria', badgeClass: 'bg-green-50 text-green-700 border-green-200', numClass: 'bg-green-100 text-green-700' },
            { type: 'exclusion', label: 'Exclusion Criteria', badgeClass: 'bg-red-50 text-red-700 border-red-200', numClass: 'bg-red-100 text-red-700' }
          ].map(section => (
            <div key={section.type} className="mb-8 last:mb-0">
              <div className="flex items-center gap-2 mb-4">
                <h2 className="font-semibold text-gray-900">{section.label}</h2>
                <Badge variant="outline" className={section.badgeClass}>
                  {criteria.filter(c => c.type === section.type).length} criteria
                </Badge>
              </div>

              <div className="space-y-3">
                {criteria
                  .filter(c => c.type === section.type)
                  .map((criterion, idx) => (
                    <Card
                      key={criterion.id}
                      className={
                        criterion.status === 'ai-suggested'
                          ? 'border-orange-300 bg-orange-50'
                          : criterion.status === 'edited'
                            ? 'border-blue-300 bg-blue-50'
                            : ''
                      }
                    >
                      <CardContent className="pt-4 pb-4">
                        <div className="flex items-start gap-4">
                          <div className="flex-shrink-0">
                            <span className={`inline-flex items-center justify-center w-8 h-8 rounded-md text-sm font-medium ${section.numClass}`}>
                              {idx + 1}
                            </span>
                          </div>

                          <div className="flex-1 min-w-0">
                            <>
                              <p className="text-sm text-gray-900 leading-relaxed">{criterion.text}</p>

                              {(criterion.entity || criterion.relation || criterion.value || criterion.unit) && (
                                <div className="mt-2 text-xs text-gray-600">
                                  <span className="font-medium text-gray-700">Mapping:</span>{' '}
                                  {criterion.entity && <span>{criterion.entity}</span>}
                                  {criterion.relation && <span> {criterion.relation}</span>}
                                  {criterion.value && <span> {criterion.value}</span>}
                                  {criterion.unit && <span> {criterion.unit}</span>}
                                </div>
                              )}

                              {(criterion.umlsMappings && criterion.umlsMappings.length > 0) && (
                                <div className="mt-1 text-xs text-gray-600">
                                  <span className="font-medium text-gray-700">Grounding:</span>
                                  {criterion.logicalOperator && (
                                    <span className="ml-1 font-semibold text-gray-800">
                                      [{criterion.logicalOperator}]
                                    </span>
                                  )}
                                  <div className="mt-1 space-y-1">
                                    {criterion.umlsMappings.map((mapping, idx) => (
                                      <div key={idx} className="pl-2 border-l-2 border-gray-300">
                                        {mapping.umls_concept && <span>{mapping.umls_concept}</span>}
                                        {mapping.umls_id && (
                                          <span className="text-gray-500"> ({mapping.umls_id})</span>
                                        )}
                                        {mapping.snomed_code && (
                                          <span className="text-gray-500"> SNOMED {mapping.snomed_code}</span>
                                        )}
                                        {mapping.confidence !== undefined && (
                                          <span className="text-gray-400 text-[10px] ml-1">
                                            ({Math.round(mapping.confidence * 100)}%)
                                          </span>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                              {/* Fallback to single mapping for backward compatibility */}
                              {(!criterion.umlsMappings || criterion.umlsMappings.length === 0) &&
                                (criterion.umlsConcept || criterion.umlsId || criterion.snomedCode) && (
                                  <div className="mt-1 text-xs text-gray-600">
                                    <span className="font-medium text-gray-700">Grounding:</span>{' '}
                                    {criterion.umlsConcept && <span>{criterion.umlsConcept}</span>}
                                    {criterion.umlsId && <span> ({criterion.umlsId})</span>}
                                    {criterion.snomedCode && <span> SNOMED {criterion.snomedCode}</span>}
                                  </div>
                                )}

                              {criterion.calculatedBy && (
                                <div className="mt-1 text-xs text-gray-600">
                                  <span className="font-medium text-gray-700">Calculated by:</span>{' '}
                                  {criterion.calculatedBy}
                                </div>
                              )}

                              <MappingDisplay
                                snomedCodes={criterion.snomedCodes}
                                fieldMapping={criterion.fieldMapping}
                              />

                              <div className="mt-2 flex items-center gap-4">
                                {criterion.evidenceSnippet && (
                                  <TooltipProvider>
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <div className="text-xs text-gray-600 flex items-center gap-1 cursor-help">
                                          <FileText className="w-3 h-3" />
                                          <span className="underline decoration-dotted">
                                            View source evidence
                                          </span>
                                        </div>
                                      </TooltipTrigger>
                                      <TooltipContent className="max-w-md bg-white border border-gray-200 shadow-lg p-3">
                                        <p className="text-xs text-gray-700">
                                          {criterion.evidenceSnippet}
                                        </p>
                                      </TooltipContent>
                                    </Tooltip>
                                  </TooltipProvider>
                                )}
                                <Button
                                  variant="link"
                                  className="h-auto p-0 text-xs text-teal-600 h-auto"
                                  onClick={() => handleOpenMappingModal(criterion)}
                                >
                                  {criterion.snomedCodes?.length || criterion.fieldMapping ? 'Edit Mapping' : 'Add Mapping'}
                                </Button>
                              </div>
                            </>
                          </div>

                          <div className="flex items-center gap-2">
                            <ConfidenceChip
                              confidence={criterion.confidence}
                              dataSource="Protocol"
                            />

                            {criterion.status === 'ai-suggested' && (
                              <>
                                <Button size="sm" onClick={() => handleApprove(criterion.id)}>
                                  <CheckCircle2 className="w-3 h-3 mr-1" />
                                  Approve
                                </Button>
                              </>
                            )}

                            {criterion.status === 'approved' && (
                              <Badge className="bg-green-100 text-green-700 border-green-300">
                                <CheckCircle2 className="w-3 h-3 mr-1" />
                                Approved
                              </Badge>
                            )}

                            {criterion.status === 'edited' && (
                              <Badge className="bg-blue-100 text-blue-700 border-blue-300">
                                <Edit2 className="w-3 h-3 mr-1" />
                                Edited
                              </Badge>
                            )}

                            {criterion.status === 'rejected' && (
                              <Badge className="bg-red-100 text-red-700 border-red-300">
                                <Edit2 className="w-3 h-3 mr-1" />
                                Rejected
                              </Badge>
                            )}

                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleOpenEditPanel(criterion)}
                            >
                              <Edit2 className="w-3 h-3 mr-1" />
                              Edit
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Edit Panel (Text) */}
      {selectedCriterion && (
        <CriteriaEditPanel
          open={editPanelOpen}
          onOpenChange={setEditPanelOpen}
          criterion={{
            id: selectedCriterion.id,
            type: selectedCriterion.type,
            text: selectedCriterion.text,
            status: selectedCriterion.status,
            confidence: selectedCriterion.confidence,
            sourceText: selectedCriterion.evidenceSnippet,
          }}
          onSave={handleSaveEditPanel}
        />
      )}

      {/* Edit Panel (Mapping) */}
      {selectedCriterion && (
        <EditMappingModal
          open={mappingModalOpen}
          onOpenChange={setMappingModalOpen}
          criterion={{
            id: selectedCriterion.id,
            text: selectedCriterion.text,
            snomedCodes: selectedCriterion.snomedCodes,
            snomedCode: selectedCriterion.snomedCode ?? undefined,
            entity: selectedCriterion.entity ?? undefined,
            umlsConcept: selectedCriterion.umlsConcept ?? undefined,
            umlsId: selectedCriterion.umlsId ?? undefined,
            relation: selectedCriterion.relation ?? undefined,
            value: selectedCriterion.value ?? undefined,
            unit: selectedCriterion.unit ?? undefined,
            hitlEntity: selectedCriterion.hitlEntity ?? undefined,
            hitlUmlsConcept: selectedCriterion.hitlUmlsConcept ?? undefined,
            hitlUmlsId: selectedCriterion.hitlUmlsId ?? undefined,
            hitlSnomedCode: selectedCriterion.hitlSnomedCode ?? undefined,
            hitlRelation: selectedCriterion.hitlRelation ?? undefined,
            hitlValue: selectedCriterion.hitlValue ?? undefined,
            hitlUnit: selectedCriterion.hitlUnit ?? undefined,
            fieldMapping: selectedCriterion.fieldMapping,
          }}
          onSave={handleSaveMapping}
        />
      )}

      {/* Source Materials Panel */}
      <SourceMaterialsPanel
        open={sourceMaterialsPanelOpen}
        onOpenChange={setSourceMaterialsPanelOpen}
        documents={sourceDocuments}
      />
    </div>
  );
}
