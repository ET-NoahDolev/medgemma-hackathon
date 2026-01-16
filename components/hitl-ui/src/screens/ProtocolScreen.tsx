import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { GlassButton } from '@/components/ui/glass-button';
import { Card, CardContent } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Textarea } from '@/components/ui/textarea';
import { ConfidenceChip } from '@/components/common/ConfidenceChip';
import { Badge } from '@/components/ui/badge';
import { CriteriaEditPanel } from '@/features/protocols/components/CriteriaEditPanel';
import { AddCriteriaPanel } from '@/features/protocols/components/AddCriteriaPanel';
import { SourceMaterialsPanel } from '@/features/protocols/components/SourceMaterialsPanel';
import {
  Upload,
  FileText,
  CheckCircle2,
  Edit2,
  Sparkles,
  Info,
  Plus,
  FolderOpen,
  ArrowLeft,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { toast } from 'sonner';

interface Criterion {
  id: string;
  type: 'inclusion' | 'exclusion';
  text: string;
  confidence: number;
  status: 'ai-suggested' | 'approved' | 'edited';
  evidenceSnippet?: string;
}

const mockCriteria: Criterion[] = [
  {
    id: 'I1',
    type: 'inclusion',
    text: 'Age ≥ 45 and ≤ 75 years at time of screening',
    confidence: 0.96,
    status: 'approved',
    evidenceSnippet: 'Section 4.1: Eligible participants must be between 45 and 75 years old...',
  },
  {
    id: 'I2',
    type: 'inclusion',
    text: 'Average-risk for colorectal cancer (no personal or family history)',
    confidence: 0.92,
    status: 'approved',
    evidenceSnippet:
      'Section 4.1.2: Participants should have average risk with no family history of CRC...',
  },
  {
    id: 'I3',
    type: 'inclusion',
    text: 'No colonoscopy in past 10 years',
    confidence: 0.89,
    status: 'ai-suggested',
    evidenceSnippet:
      'Section 4.1.3: Must not have undergone colonoscopy within the last 10 years...',
  },
  {
    id: 'E1',
    type: 'exclusion',
    text: "History of inflammatory bowel disease (Crohn's or ulcerative colitis)",
    confidence: 0.95,
    status: 'approved',
    evidenceSnippet:
      "Section 4.2.1: Exclude patients with IBD including Crohn's disease or ulcerative colitis...",
  },
  {
    id: 'E2',
    type: 'exclusion',
    text: 'Current diagnosis of any cancer',
    confidence: 0.98,
    status: 'approved',
    evidenceSnippet: 'Section 4.2.3: Active cancer diagnosis is an exclusion criterion...',
  },
  {
    id: 'E3',
    type: 'exclusion',
    text: 'Blood pressure >160/100 mmHg despite treatment',
    confidence: 0.85,
    status: 'edited',
    evidenceSnippet:
      'Section 4.2.5: Uncontrolled hypertension defined as BP >160/100 on treatment...',
  },
];

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

export function ProtocolScreen({ protocol, onBack }: ProtocolScreenProps) {
  // Check if this is a new protocol (no criteria uploaded yet)
  const isNewProtocol =
    protocol && protocol.criteriaCount?.inclusion === 0 && protocol.criteriaCount?.exclusion === 0;

  const [uploaded, setUploaded] = useState(!isNewProtocol); // New protocols start with no upload
  const [criteria, setCriteria] = useState<Criterion[]>(isNewProtocol ? [] : mockCriteria);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [editPanelOpen, setEditPanelOpen] = useState(false);
  const [selectedCriterion, setSelectedCriterion] = useState<Criterion | null>(null);
  const [addCriteriaPanelOpen, setAddCriteriaPanelOpen] = useState(false);
  const [sourceMaterialsPanelOpen, setSourceMaterialsPanelOpen] = useState(false);
  const [availableSourceDocs, setAvailableSourceDocs] = useState<
    Array<{
      id: string;
      name: string;
      content: string;
      type?: 'protocol' | 'ecrf' | 'other';
    }>
  >([]);

  const handleApprove = (id: string) => {
    setCriteria(prev => prev.map(c => (c.id === id ? { ...c, status: 'approved' as const } : c)));
  };

  const handleSaveEdit = () => {
    if (editingId) {
      setCriteria(prev =>
        prev.map(c =>
          c.id === editingId ? { ...c, text: editText, status: 'edited' as const } : c
        )
      );
      setEditingId(null);
      setEditText('');
    }
  };

  const handleOpenEditPanel = (criterion: Criterion) => {
    setSelectedCriterion(criterion);
    setEditPanelOpen(true);
  };

  const handleSaveEditPanel = (updates: { text: string; type: string; rationale?: string }) => {
    if (selectedCriterion) {
      setCriteria(prev =>
        prev.map(c =>
          c.id === selectedCriterion.id
            ? {
                ...c,
                text: updates.text,
                type: updates.type === 'not-applicable' ? c.type : updates.type,
                status:
                  updates.type === 'not-applicable' ? ('edited' as const) : ('edited' as const),
              }
            : c
        )
      );

      // Log to audit trail
      toast.success('Criterion updated', {
        description: `Changes saved: ${updates.rationale}`,
      });
    }
  };

  const handleDeleteCriterion = (rationale: string) => {
    if (selectedCriterion) {
      setCriteria(prev => prev.filter(c => c.id !== selectedCriterion.id));

      toast.success('Criterion removed', {
        description: `${selectedCriterion.id} removed: ${rationale}`,
      });
    }
  };

  const handleAddCriterion = (newCriterion: {
    text: string;
    type: 'inclusion' | 'exclusion';
    sourceText: string;
    fieldMappings?: Array<{ field: string; value: string }>;
  }) => {
    const existingIds = criteria
      .filter(c => c.type === newCriterion.type)
      .map(c => parseInt(c.id.substring(1)))
      .filter(n => !isNaN(n));

    const nextId = existingIds.length > 0 ? Math.max(...existingIds) + 1 : 1;
    const id = newCriterion.type === 'inclusion' ? `I${nextId}` : `E${nextId}`;

    const criterion: Criterion = {
      id,
      type: newCriterion.type,
      text: newCriterion.text,
      confidence: 0.85, // Manual entry gets reasonable confidence
      status: 'ai-suggested',
      evidenceSnippet: newCriterion.sourceText,
    };

    setCriteria(prev => [...prev, criterion]);

    const mappingInfo =
      newCriterion.fieldMappings && newCriterion.fieldMappings.length > 0
        ? ` with ${newCriterion.fieldMappings.length} field mapping(s)`
        : '';

    toast.success('Criterion added', {
      description: `${id} has been added for review${mappingInfo}`,
    });
  };

  const handleSelectSourceDocument = (doc: { id: string; name: string; type: string }) => {
    // Add the document to available sources if not already there
    setAvailableSourceDocs(prev => {
      const exists = prev.find(d => d.id === doc.id);
      if (exists) return prev;
      return [
        ...prev,
        {
          id: doc.id,
          name: doc.name,
          content: doc.content,
          type: doc.type,
        },
      ];
    });
    setSourceMaterialsPanelOpen(false);
    setAddCriteriaPanelOpen(true);
  };

  const approvedCount = criteria.filter(c => c.status === 'approved').length;
  const needsReviewCount = criteria.filter(c => c.status === 'ai-suggested').length;

  const handleFileUpload = () => {
    // Simulate file upload and AI extraction
    toast.promise(
      new Promise(resolve => {
        setTimeout(() => {
          setUploaded(true);
          // Simulate AI extraction of criteria after upload
          setCriteria(mockCriteria);
          resolve({ name: 'Success' });
        }, 1500);
      }),
      {
        loading: 'Processing protocol document...',
        success: _data => 'Extracted 6 criteria for review',
        error: 'Failed to process document',
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
                <h1 className="text-gray-900">{protocol ? protocol.name : 'New Protocol'}</h1>
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
              <Button onClick={handleFileUpload}>
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
                {protocol ? protocol.name : 'Protocol Ingestion'}
              </h1>
            </div>
            <p className="text-sm text-gray-600">
              {protocol
                ? `Version ${protocol.version} • Extracted ${criteria.length} criteria`
                : `CRC-SCREEN-2024-Protocol-v3.2.pdf • Extracted ${criteria.length} criteria`}
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
            <Button variant="outline" onClick={() => setSourceMaterialsPanelOpen(true)}>
              <FolderOpen className="w-4 h-4 mr-2" />
              Source Materials
            </Button>
            <Button variant="outline" onClick={() => setAddCriteriaPanelOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Add Criterion
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
      </div>

      {/* Criteria List */}
      <ScrollArea className="flex-1 bg-transparent">
        <div className="p-6 max-w-5xl mx-auto">
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
                          {editingId === criterion.id ? (
                            <div className="space-y-3">
                              <Textarea
                                value={editText}
                                onChange={e => setEditText(e.target.value)}
                                rows={3}
                                className="text-sm"
                              />
                              <div className="flex gap-2">
                                <Button size="sm" onClick={handleSaveEdit}>
                                  Save Changes
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    setEditingId(null);
                                    setEditText('');
                                  }}
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <p className="text-sm text-gray-900 leading-relaxed">
                                {criterion.text}
                              </p>

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
                          )}
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
                          {editingId === criterion.id ? (
                            <div className="space-y-3">
                              <Textarea
                                value={editText}
                                onChange={e => setEditText(e.target.value)}
                                rows={3}
                                className="text-sm"
                              />
                              <div className="flex gap-2">
                                <Button size="sm" onClick={handleSaveEdit}>
                                  Save Changes
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    setEditingId(null);
                                    setEditText('');
                                  }}
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <p className="text-sm text-gray-900 leading-relaxed">
                                {criterion.text}
                              </p>

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
                          )}
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
          onDelete={handleDeleteCriterion}
        />
      )}

      {/* Add Criteria Panel */}
      <AddCriteriaPanel
        open={addCriteriaPanelOpen}
        onOpenChange={setAddCriteriaPanelOpen}
        sourceDocuments={availableSourceDocs.length > 0 ? availableSourceDocs : undefined}
        onSave={handleAddCriterion}
      />

      {/* Source Materials Panel */}
      <SourceMaterialsPanel
        open={sourceMaterialsPanelOpen}
        onOpenChange={setSourceMaterialsPanelOpen}
        onSelectDocument={handleSelectSourceDocument}
      />
    </div>
  );
}
