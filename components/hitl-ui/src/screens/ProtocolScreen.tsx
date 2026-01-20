import { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { GlassButton } from '@/components/ui/glass-button';
import { Card, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ConfidenceChip } from '@/components/common/ConfidenceChip';
import { Badge } from '@/components/ui/badge';
import { CriteriaEditPanel } from '@/features/protocols/components/CriteriaEditPanel';
import { SourceMaterialsPanel } from '@/features/protocols/components/SourceMaterialsPanel';
import { useCriteria } from '@/hooks/useCriteria';
import { useSubmitFeedback } from '@/hooks/useSubmitFeedback';
import { useUpdateCriterion } from '@/hooks/useUpdateCriterion';
import { useUploadProtocol } from '@/hooks/useUploadProtocol';
import { useProtocol } from '@/hooks/useProtocol';
import {
  Upload,
  FileText,
  CheckCircle2,
  Edit2,
  Sparkles,
  Info,
  FolderOpen,
  ArrowLeft,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { toast } from 'sonner';

interface ProtocolScreenProps {
  protocol?: {
    id: string;
    name: string;
    version: string;
    criteriaCount?: {
      inclusion: number;
      exclusion: number;
    };
  };
  onBack?: () => void;
}

interface Criterion {
  id: string;
  type: 'inclusion' | 'exclusion';
  text: string;
  confidence: number;
  status: 'ai-suggested' | 'approved' | 'edited';
  evidenceSnippet?: string;
}

export function ProtocolScreen({ protocol, onBack }: ProtocolScreenProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const isNewProtocol =
    !protocol || (protocol.criteriaCount?.inclusion === 0 && protocol.criteriaCount?.exclusion === 0);

  const [activeProtocolId, setActiveProtocolId] = useState<string | null>(protocol?.id ?? null);
  const [activeProtocolTitle, setActiveProtocolTitle] = useState<string>(
    protocol?.name ?? 'New Protocol'
  );
  const [uploaded, setUploaded] = useState(!isNewProtocol);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [editPanelOpen, setEditPanelOpen] = useState(false);
  const [selectedCriterion, setSelectedCriterion] = useState<Criterion | null>(null);
  const [sourceMaterialsPanelOpen, setSourceMaterialsPanelOpen] = useState(false);

  const { data: criteriaData, isLoading, error, refetch } = useCriteria(activeProtocolId);
  const {
    data: protocolData,
    isLoading: isProtocolLoading,
    error: protocolError,
  } = useProtocol(activeProtocolId);
  const uploadProtocol = useUploadProtocol();
  const submitFeedback = useSubmitFeedback();
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
      type: (c.criterion_type as 'inclusion' | 'exclusion') ?? 'inclusion',
      text: c.text,
      confidence: c.confidence,
      status: 'ai-suggested' as const,
      evidenceSnippet: undefined,
    }));
  }, [criteriaData]);

  useEffect(() => {
    if (protocolData?.title) {
      setActiveProtocolTitle(protocolData.title);
    }
  }, [protocolData?.title]);

  // Keep existing local edits/statuses, but refresh text from API.
  useEffect(() => {
    if (!uploaded) return;
    if (!activeProtocolId) return;

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

  // If extraction is still running, poll until criteria appear.
  useEffect(() => {
    if (!uploaded) return;
    if (!activeProtocolId) return;
    if (isLoading) return;
    if (error) return;
    if ((criteriaData?.criteria?.length ?? 0) > 0) return;

    const interval = window.setInterval(() => {
      void refetch();
    }, 1500);

    return () => window.clearInterval(interval);
  }, [activeProtocolId, criteriaData?.criteria?.length, error, isLoading, refetch, uploaded]);

  const handleApprove = (id: string) => {
    submitFeedback.mutate({ criterion_id: id, action: 'accept' });
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

  const handleFileSelected = async (file: File | null) => {
    if (!file) return;

    toast.promise(
      uploadProtocol.mutateAsync({ file, autoExtract: true }).then(resp => {
        setActiveProtocolId(resp.protocol_id);
        setActiveProtocolTitle(resp.title);
        setUploaded(true);
        setCriteria([]);
        setSelectedCriterion(null);
        return resp;
      }),
      {
        loading: 'Uploading and processing protocol PDF...',
        success: _data => 'Upload accepted. Extracting criteria...',
        error: 'Failed to upload protocol',
      }
    );
  };

  if (!uploaded) {
    return (
      <div className="flex flex-col h-full">
        {/* Header for new protocol */}
        <div className="bg-white border-b border-gray-200" style={{ padding: 'var(--space-6)' }}>
          <div className="flex items-start justify-between">
            <div>
              <div
                className="flex items-center"
                style={{ gap: 'var(--space-3)', marginBottom: 'var(--space-2)' }}
              >
                {onBack && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onBack}
                    className="gap-1 -ml-2"
                    style={{ fontSize: '14px' }}
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Protocols
                  </Button>
                )}
                <FileText className="w-6 h-6 text-teal-600" />
                <h1 className="text-gray-900">{activeProtocolTitle}</h1>
              </div>
              <p className="text-gray-600" style={{ fontSize: '14px' }}>
                Upload protocol documents to extract inclusion/exclusion criteria
              </p>
            </div>
          </div>
        </div>

        {/* Upload Area */}
        <div className="flex-1 flex items-center justify-center bg-transparent">
          <Card className="max-w-2xl w-full mx-6">
            <CardContent
              style={{ paddingTop: 'var(--space-12)', paddingBottom: 'var(--space-12)' }}
              className="text-center"
            >
              <div
                className="w-20 h-20 bg-teal-100 rounded-full flex items-center justify-center mx-auto"
                style={{ marginBottom: 'var(--space-6)' }}
              >
                <Upload className="w-10 h-10 text-teal-600" />
              </div>
              <h2 className="text-gray-900" style={{ marginBottom: 'var(--space-2)' }}>
                Upload Protocol Document
              </h2>
              <p
                className="text-gray-600"
                style={{ fontSize: '14px', marginBottom: 'var(--space-8)' }}
              >
                Drag and drop your protocol PDF or eCRF file to extract inclusion/exclusion criteria
                using AI
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={e => void handleFileSelected(e.target.files?.item(0) ?? null)}
              />
              <Button onClick={handleSelectFileClick} disabled={uploadProtocol.isPending}>
                <Upload className="w-4 h-4 mr-2" />
                Select File
              </Button>
              <p
                className="text-gray-500"
                style={{ fontSize: '12px', marginTop: 'var(--space-4)' }}
              >
                Supported formats: PDF, DOCX
              </p>

              <Alert className="mt-8 text-left">
                <Info className="h-4 w-4" />
                <AlertDescription style={{ fontSize: '14px' }}>
                  <strong>What happens next:</strong> Our AI will analyze the document, extract all
                  inclusion and exclusion criteria, and present them for your review with confidence
                  scores and source evidence.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              {onBack && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onBack}
                  className="gap-1 -ml-2"
                  style={{ fontSize: '14px' }}
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back to Protocols
                </Button>
              )}
              <FileText className="w-6 h-6 text-teal-600" />
              <h1 className="font-semibold text-gray-900">
                {protocol?.name ?? activeProtocolTitle}
              </h1>
            </div>
            <p className="text-sm text-gray-600">
              {protocol?.version ? `Version ${protocol.version} • ` : ''}
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
      <ScrollArea className="flex-1 bg-transparent">
        <div className="p-6 max-w-5xl mx-auto">
          {isLoading && criteria.length === 0 && (
            <div className="flex items-center justify-center py-12 text-gray-600">
              Loading criteria...
            </div>
          )}
          {/* Inclusion Criteria */}
          <div className="mb-8">
            <div className="flex items-center gap-2 mb-4">
              <h2 className="font-semibold text-gray-900">Inclusion Criteria</h2>
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                {criteria.filter(c => c.type === 'inclusion').length} criteria
              </Badge>
            </div>

            <div className="space-y-3">
              {criteria
                .filter(c => c.type === 'inclusion')
                .map(criterion => (
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
                          <span className="inline-flex items-center justify-center w-8 h-8 bg-green-100 text-green-700 rounded-md text-sm font-medium">
                            {criterion.id}
                          </span>
                        </div>

                        <div className="flex-1 min-w-0">
                          <>
                            <p className="text-sm text-gray-900 leading-relaxed">{criterion.text}</p>

                            {criterion.evidenceSnippet && (
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <div className="mt-2 text-xs text-gray-600 flex items-center gap-1 cursor-help">
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
                          </>
                        </div>

                        <div className="flex items-center gap-2">
                          <ConfidenceChip
                            confidence={criterion.confidence}
                            dataSource="Protocol PDF Section 4.1"
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

          {/* Exclusion Criteria */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <h2 className="font-semibold text-gray-900">Exclusion Criteria</h2>
              <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                {criteria.filter(c => c.type === 'exclusion').length} criteria
              </Badge>
            </div>

            <div className="space-y-3">
              {criteria
                .filter(c => c.type === 'exclusion')
                .map(criterion => (
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
                          <span className="inline-flex items-center justify-center w-8 h-8 bg-red-100 text-red-700 rounded-md text-sm font-medium">
                            {criterion.id}
                          </span>
                        </div>

                        <div className="flex-1 min-w-0">
                          <>
                            <p className="text-sm text-gray-900 leading-relaxed">{criterion.text}</p>

                            {criterion.evidenceSnippet && (
                              <TooltipProvider>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <div className="mt-2 text-xs text-gray-600 flex items-center gap-1 cursor-help">
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
                          </>
                        </div>

                        <div className="flex items-center gap-2">
                          <ConfidenceChip
                            confidence={criterion.confidence}
                            dataSource="Protocol PDF Section 4.2"
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
        </div>
      </ScrollArea>

      {/* Edit Panel */}
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

      {/* Source Materials Panel */}
      <SourceMaterialsPanel
        open={sourceMaterialsPanelOpen}
        onOpenChange={setSourceMaterialsPanelOpen}
        documents={sourceDocuments}
      />
    </div>
  );
}
