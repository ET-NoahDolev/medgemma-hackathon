import { useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  FileText,
  Upload,
  Eye,
  Trash2,
  Download,
  Calendar,
  FileType,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Check,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import { ConfidenceChip } from '@/components/common/ConfidenceChip';

interface SourceDocument {
  id: string;
  name: string;
  type: 'protocol' | 'ecrf' | 'other';
  uploadDate: string;
  size: string;
  status: 'processed' | 'processing' | 'error';
  criteriaExtracted?: number;
  content: string;
}

interface Contradiction {
  id: string;
  severity: 'high' | 'medium' | 'low';
  confidence: number;
  title: string;
  description: string;
  sources: {
    documentId: string;
    documentName: string;
    excerpt: string;
    location: string;
  }[];
  aiReasoning: string;
  status: 'open' | 'resolved' | 'dismissed';
  resolution?: {
    resolvedBy: string;
    resolvedAt: string;
    instructions: string;
  };
}

interface SourceMaterialsPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectDocument?: (document: SourceDocument) => void;
}

const mockContradictions: Contradiction[] = [
  {
    id: 'contra-1',
    severity: 'high',
    confidence: 0.92,
    title: 'IBD Diagnosis Conflicts with Colonoscopy Requirement',
    description:
      "The protocol includes patients with Crohn's disease, but the eCRF excludes those who have undergone a colonoscopy. Crohn's diagnosis typically requires a colonoscopy",
    sources: [
      {
        documentId: 'doc-1',
        documentName: 'CRC-Study-Protocol-v2.3.pdf',
        excerpt:
          "Exclude patients with inflammatory bowel disease including Crohn's disease or ulcerative colitis.",
        location: 'Section 4.2.1',
      },
      {
        documentId: 'doc-2',
        documentName: 'eCRF-Template-v1.5.xlsx',
        excerpt: 'No colonoscopy in past 10 years',
        location: 'Eligibility Checklist',
      },
    ],
    aiReasoning:
      "Crohn's disease diagnosis requires endoscopic confirmation via colonoscopy. If a patient has a documented Crohn's diagnosis, they must have had a colonoscopy. This creates a temporal paradox where excluded patients (Crohn's) would violate an inclusion requirement (no colonoscopy in 10 years).",
    status: 'open',
  },
  {
    id: 'contra-2',
    severity: 'medium',
    confidence: 0.78,
    title: 'Age Range Discrepancy Between Documents',
    description:
      'Protocol specifies age 45-75 years, but the eCRF eligibility checklist only mentions "Age 45-75 years" without clarifying if it\'s inclusive or at time of screening vs. enrollment.',
    sources: [
      {
        documentId: 'doc-1',
        documentName: 'CRC-Study-Protocol-v2.3.pdf',
        excerpt:
          'Eligible participants must be between 45 and 75 years old at the time of screening visit.',
        location: 'Section 4.1',
      },
      {
        documentId: 'doc-2',
        documentName: 'eCRF-Template-v1.5.xlsx',
        excerpt: 'Age 45-75 years',
        location: 'Eligibility Checklist',
      },
    ],
    aiReasoning:
      'The protocol explicitly states "at the time of screening visit," but the eCRF doesn\'t specify the timing reference. This could lead to confusion about whether age should be calculated at screening, consent, or enrollment. Additionally, the protocol uses "between" which could be interpreted as exclusive of endpoints (>45 and <75) vs. inclusive (≥45 and ≤75).',
    status: 'open',
  },
  {
    id: 'contra-3',
    severity: 'low',
    confidence: 0.65,
    title: 'Blood Pressure Threshold Minor Inconsistency',
    description:
      'Protocol uses "uncontrolled hypertension" with specific threshold, eCRF uses "Blood pressure controlled" without defining the threshold.',
    sources: [
      {
        documentId: 'doc-1',
        documentName: 'CRC-Study-Protocol-v2.3.pdf',
        excerpt:
          'Patients with uncontrolled hypertension (blood pressure >160/100 mmHg despite antihypertensive therapy) should be excluded.',
        location: 'Section 4.2.5',
      },
      {
        documentId: 'doc-2',
        documentName: 'eCRF-Template-v1.5.xlsx',
        excerpt: 'Blood pressure controlled',
        location: 'Eligibility Checklist',
      },
    ],
    aiReasoning:
      'The eCRF checklist doesn\'t specify what "controlled" means. While the protocol clearly defines >160/100 mmHg as the exclusion threshold, the eCRF could benefit from this specificity to ensure consistent screening across sites.',
    status: 'open',
  },
];

const mockDocuments: SourceDocument[] = [
  {
    id: 'doc-1',
    name: 'CRC-Study-Protocol-v2.3.pdf',
    type: 'protocol',
    uploadDate: '2024-10-15',
    size: '2.4 MB',
    status: 'processed',
    criteriaExtracted: 12,
    content: `STUDY PROTOCOL

Version 2.3
Date: October 15, 2024

1. STUDY TITLE
Colorectal Cancer Screening Trial: A Multicenter Study

2. OBJECTIVES
Primary: To evaluate the effectiveness of early screening in average-risk populations
Secondary: To assess patient compliance and follow-up rates

3. STUDY POPULATION

3.1 Inclusion Criteria
Participants must meet ALL of the following criteria:

Section 4.1: Eligible participants must be between 45 and 75 years old at the time of screening visit.

Section 4.1.2: Participants should have average risk with no personal or family history of colorectal cancer or advanced adenomas.

Section 4.1.3: Must not have undergone colonoscopy within the last 10 years prior to enrollment.

Section 4.1.4: Willing and able to provide informed consent and comply with study procedures.

3.2 Exclusion Criteria
Participants meeting ANY of the following criteria will be excluded:

Section 4.2.1: Exclude patients with inflammatory bowel disease including Crohn's disease or ulcerative colitis.

Section 4.2.2: History of familial adenomatous polyposis (FAP) or Lynch syndrome.

Section 4.2.3: Active cancer diagnosis is an exclusion criterion for study participation.

Section 4.2.4: Pregnant or breastfeeding women.

Section 4.2.5: Patients with uncontrolled hypertension (blood pressure >160/100 mmHg despite antihypertensive therapy) should be excluded.

Section 4.2.6: History of bleeding disorders or current use of anticoagulation therapy that cannot be safely interrupted.

4. STUDY PROCEDURES
[Additional protocol sections...]`,
  },
  {
    id: 'doc-2',
    name: 'eCRF-Template-v1.5.xlsx',
    type: 'ecrf',
    uploadDate: '2024-10-20',
    size: '456 KB',
    status: 'processed',
    criteriaExtracted: 8,
    content: `ELECTRONIC CASE REPORT FORM (eCRF)
Study: Cauldron Clinical Trial OS

Demographics Section:
- Patient ID: [Auto-generated]
- Date of Birth: [MM/DD/YYYY]
- Age at Screening: [Calculated]
- Gender: [M/F/Other]
- Race/Ethnicity: [Dropdown]

Medical History:
- Personal History of CRC: [Yes/No]
- Family History of CRC: [Yes/No]
- IBD Diagnosis: [Yes/No]
  - If Yes, specify: [Crohn's/UC/Other]
- Prior Colonoscopy: [Yes/No]
  - If Yes, date: [MM/DD/YYYY]

Vital Signs:
- Blood Pressure: [___/___] mmHg
- Heart Rate: [___] bpm
- Temperature: [___] °F

Laboratory Values:
- Hemoglobin: [___] g/dL
- Creatinine: [___] mg/dL

Eligibility Checklist:
□ Age 45-75 years
□ Average risk (no personal/family history)
□ No colonoscopy in past 10 years
□ No IBD diagnosis
□ No active cancer
□ Blood pressure controlled`,
  },
  {
    id: 'doc-3',
    name: 'Amendment-3-Oct-2024.pdf',
    type: 'other',
    uploadDate: '2024-10-25',
    size: '890 KB',
    status: 'processing',
    criteriaExtracted: 0,
    content: '',
  },
];

export function SourceMaterialsPanel({
  open,
  onOpenChange,
  onSelectDocument,
}: SourceMaterialsPanelProps) {
  const [documents, setDocuments] = useState<SourceDocument[]>(mockDocuments);
  const [selectedDoc, setSelectedDoc] = useState<SourceDocument | null>(null);
  const [contradictions, setContradictions] = useState<Contradiction[]>(mockContradictions);
  const [expandedContradiction, setExpandedContradiction] = useState<string | null>(null);
  const [resolutionInstructions, setResolutionInstructions] = useState<Record<string, string>>({});

  const handleUpload = () => {
    toast.info('Upload functionality', {
      description: 'In production, this would open a file picker',
    });
  };

  const handleView = (doc: SourceDocument) => {
    setSelectedDoc(doc);
    if (onSelectDocument) {
      onSelectDocument(doc);
    }
  };

  const handleDelete = (docId: string) => {
    setDocuments(prev => prev.filter(d => d.id !== docId));
    toast.success('Document deleted');
  };

  const handleDownload = (doc: SourceDocument) => {
    toast.success('Downloading document', {
      description: doc.name,
    });
  };

  const handleResolveContradiction = (contradictionId: string) => {
    const instructions = resolutionInstructions[contradictionId];
    if (!instructions || instructions.trim() === '') {
      toast.error('Please provide resolution instructions');
      return;
    }

    setContradictions(prev =>
      prev.map(c =>
        c.id === contradictionId
          ? {
              ...c,
              status: 'resolved',
              resolution: {
                resolvedBy: 'CRC User', // In production, use actual user
                resolvedAt: new Date().toISOString(),
                instructions,
              },
            }
          : c
      )
    );

    setResolutionInstructions(prev => {
      const updated = { ...prev };
      delete updated[contradictionId];
      return updated;
    });

    setExpandedContradiction(null);

    toast.success('Contradiction resolved', {
      description: 'AI will apply your instructions to future extractions',
    });
  };

  const handleDismissContradiction = (contradictionId: string) => {
    setContradictions(prev =>
      prev.map(c => (c.id === contradictionId ? { ...c, status: 'dismissed' } : c))
    );
    setExpandedContradiction(null);
    toast.info('Contradiction dismissed');
  };

  const handleReopenContradiction = (contradictionId: string) => {
    setContradictions(prev =>
      prev.map(c =>
        c.id === contradictionId ? { ...c, status: 'open', resolution: undefined } : c
      )
    );
    toast.info('Contradiction reopened');
  };

  const getDocumentStatusBadge = (status: SourceDocument['status']) => {
    switch (status) {
      case 'processed':
        return (
          <Badge
            className="bg-green-100 text-green-700 border-green-300 gap-1"
            style={{ fontSize: '11px' }}
          >
            <CheckCircle2 className="w-3 h-3" />
            Processed
          </Badge>
        );
      case 'processing':
        return (
          <Badge className="bg-blue-100 text-blue-700 border-blue-300" style={{ fontSize: '11px' }}>
            Processing...
          </Badge>
        );
      case 'error':
        return (
          <Badge className="bg-red-100 text-red-700 border-red-300" style={{ fontSize: '11px' }}>
            Error
          </Badge>
        );
    }
  };

  const getTypeBadge = (type: SourceDocument['type']) => {
    switch (type) {
      case 'protocol':
        return (
          <Badge variant="outline" style={{ fontSize: '11px' }}>
            Protocol
          </Badge>
        );
      case 'ecrf':
        return (
          <Badge variant="outline" style={{ fontSize: '11px' }}>
            eCRF
          </Badge>
        );
      case 'other':
        return (
          <Badge variant="outline" style={{ fontSize: '11px' }}>
            Other
          </Badge>
        );
    }
  };

  const getSeverityBadge = (severity: Contradiction['severity']) => {
    switch (severity) {
      case 'high':
        return (
          <Badge className="bg-red-100 text-red-700 border-red-300" style={{ fontSize: '11px' }}>
            High Severity
          </Badge>
        );
      case 'medium':
        return (
          <Badge
            className="bg-orange-100 text-orange-700 border-orange-300"
            style={{ fontSize: '11px' }}
          >
            Medium
          </Badge>
        );
      case 'low':
        return (
          <Badge
            className="bg-yellow-100 text-yellow-700 border-yellow-300"
            style={{ fontSize: '11px' }}
          >
            Low
          </Badge>
        );
    }
  };

  const getStatusBadge = (status: Contradiction['status']) => {
    switch (status) {
      case 'open':
        return (
          <Badge
            className="bg-orange-100 text-orange-700 border-orange-300 gap-1"
            style={{ fontSize: '11px' }}
          >
            <AlertTriangle className="w-3 h-3" />
            Needs Resolution
          </Badge>
        );
      case 'resolved':
        return (
          <Badge
            className="bg-green-100 text-green-700 border-green-300 gap-1"
            style={{ fontSize: '11px' }}
          >
            <Check className="w-3 h-3" />
            Resolved
          </Badge>
        );
      case 'dismissed':
        return (
          <Badge
            className="bg-gray-100 text-gray-700 border-gray-300 gap-1"
            style={{ fontSize: '11px' }}
          >
            <X className="w-3 h-3" />
            Dismissed
          </Badge>
        );
    }
  };

  const openContradictions = contradictions.filter(c => c.status === 'open');

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-3xl p-0 flex flex-col gap-0">
        <SheetHeader className="px-6 py-4 border-b">
          <SheetTitle className="flex items-center gap-2" style={{ fontSize: '18px' }}>
            <FileText className="w-5 h-5" />
            Source Materials
          </SheetTitle>
          <SheetDescription style={{ fontSize: '14px' }}>
            Manage protocol documents, eCRFs, and resolve contradictions detected by AI
          </SheetDescription>
        </SheetHeader>

        <Tabs defaultValue="documents" className="flex-1 flex flex-col gap-0">
          <div className="px-6 pt-6 pb-0">
            <TabsList className="grid w-full grid-cols-3" style={{ fontSize: '14px' }}>
              <TabsTrigger value="documents" style={{ fontSize: '14px' }}>
                Documents ({documents.length})
              </TabsTrigger>
              <TabsTrigger value="contradictions" style={{ fontSize: '14px' }}>
                <div className="flex items-center gap-2">
                  Contradictions
                  {openContradictions.length > 0 && (
                    <Badge className="bg-orange-500 text-white ml-1" style={{ fontSize: '10px' }}>
                      {openContradictions.length}
                    </Badge>
                  )}
                </div>
              </TabsTrigger>
              <TabsTrigger value="viewer" disabled={!selectedDoc} style={{ fontSize: '14px' }}>
                Viewer
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="documents" className="flex-1 mt-0">
            <div className="p-6 space-y-4">
              {/* Upload Button */}
              <Button
                onClick={handleUpload}
                className="w-full gap-2"
                variant="outline"
                style={{ fontSize: '14px' }}
              >
                <Upload className="w-4 h-4" />
                Upload New Document
              </Button>

              <Separator />

              {/* Documents List */}
              <ScrollArea className="h-[calc(100vh-280px)]">
                <div className="space-y-3">
                  {documents.map(doc => (
                    <Card key={doc.id} className="hover:shadow-md transition-shadow">
                      <CardContent className="p-4">
                        <div className="space-y-3">
                          {/* Header */}
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <FileType className="w-4 h-4 text-gray-500 flex-shrink-0" />
                                <h4 className="truncate" style={{ fontSize: '14px' }}>
                                  {doc.name}
                                </h4>
                              </div>
                              <div className="flex items-center gap-2 flex-wrap">
                                {getTypeBadge(doc.type)}
                                {getDocumentStatusBadge(doc.status)}
                              </div>
                            </div>
                          </div>

                          {/* Metadata */}
                          <div
                            className="grid grid-cols-2 gap-2 text-gray-600"
                            style={{ fontSize: '12px' }}
                          >
                            <div className="flex items-center gap-2">
                              <Calendar className="w-3 h-3" />
                              <span>{doc.uploadDate}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <FileText className="w-3 h-3" />
                              <span>{doc.size}</span>
                            </div>
                          </div>

                          {/* Extraction Stats */}
                          {doc.status === 'processed' && doc.criteriaExtracted !== undefined && (
                            <div className="p-2 bg-blue-50 border border-blue-200 rounded">
                              <p className="text-blue-900" style={{ fontSize: '13px' }}>
                                <strong>{doc.criteriaExtracted}</strong> criteria extracted
                              </p>
                            </div>
                          )}

                          {/* Actions */}
                          <div className="flex gap-2 pt-2 border-t">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleView(doc)}
                              disabled={doc.status === 'processing'}
                              className="gap-1"
                              style={{ fontSize: '12px' }}
                            >
                              <Eye className="w-3 h-3" />
                              View
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleDownload(doc)}
                              className="gap-1"
                              style={{ fontSize: '12px' }}
                            >
                              <Download className="w-3 h-3" />
                              Download
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDelete(doc.id)}
                              className="gap-1 ml-auto text-red-600 hover:text-red-700 hover:bg-red-50"
                              style={{ fontSize: '12px' }}
                            >
                              <Trash2 className="w-3 h-3" />
                              Delete
                            </Button>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </TabsContent>

          <TabsContent value="contradictions" className="flex-1 mt-0">
            <ScrollArea className="h-[calc(100vh-220px)]">
              <div className="p-6 space-y-4">
                {/* Header */}
                <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
                  <div className="flex items-start gap-3">
                    <Sparkles className="w-5 h-5 text-orange-600 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="text-orange-900 mb-1" style={{ fontSize: '14px' }}>
                        AI-Detected Contradictions
                      </h4>
                      <p className="text-orange-800" style={{ fontSize: '13px' }}>
                        ElixirAI has identified {contradictions.length} potential conflicts between
                        your source documents. Review and provide resolution instructions to help
                        the AI make better extraction decisions.
                      </p>
                    </div>
                  </div>
                </div>

                {contradictions.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <CheckCircle2 className="w-12 h-12 mb-4 text-green-500" />
                    <p style={{ fontSize: '14px' }}>No contradictions detected</p>
                    <p className="text-gray-400" style={{ fontSize: '12px' }}>
                      All source documents are aligned
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {contradictions.map(contradiction => (
                      <Card
                        key={contradiction.id}
                        className={`transition-all ${
                          contradiction.status === 'open'
                            ? 'border-orange-300 shadow-sm'
                            : contradiction.status === 'resolved'
                              ? 'border-green-300'
                              : 'border-gray-200 opacity-75'
                        }`}
                      >
                        <CardContent className="p-4">
                          <div className="space-y-3">
                            {/* Header */}
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-2 flex-wrap">
                                  {getSeverityBadge(contradiction.severity)}
                                  {getStatusBadge(contradiction.status)}
                                  <ConfidenceChip
                                    confidence={contradiction.confidence}
                                    model="ElixirAI-v2.1"
                                  />
                                </div>
                                <h4 className="text-gray-900 mb-1" style={{ fontSize: '15px' }}>
                                  {contradiction.title}
                                </h4>
                                <p className="text-gray-600" style={{ fontSize: '13px' }}>
                                  {contradiction.description}
                                </p>
                              </div>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  setExpandedContradiction(
                                    expandedContradiction === contradiction.id
                                      ? null
                                      : contradiction.id
                                  )
                                }
                                style={{ fontSize: '12px' }}
                              >
                                {expandedContradiction === contradiction.id ? 'Collapse' : 'Expand'}
                              </Button>
                            </div>

                            {/* Expanded Details */}
                            {expandedContradiction === contradiction.id && (
                              <>
                                <Separator />

                                {/* AI Reasoning */}
                                <div className="space-y-2">
                                  <Label
                                    className="flex items-center gap-2"
                                    style={{ fontSize: '13px' }}
                                  >
                                    <Sparkles className="w-3.5 h-3.5 text-orange-600" />
                                    AI Reasoning
                                  </Label>
                                  <div className="p-3 bg-blue-50 border border-blue-200 rounded">
                                    <p className="text-blue-900" style={{ fontSize: '13px' }}>
                                      {contradiction.aiReasoning}
                                    </p>
                                  </div>
                                </div>

                                {/* Conflicting Sources */}
                                <div className="space-y-2">
                                  <Label style={{ fontSize: '13px' }}>
                                    Conflicting Sources ({contradiction.sources.length})
                                  </Label>
                                  <div className="space-y-2">
                                    {contradiction.sources.map((source, idx) => (
                                      <div
                                        key={idx}
                                        className="p-3 bg-gray-50 border border-gray-200 rounded space-y-1"
                                      >
                                        <div className="flex items-center gap-2">
                                          <FileText className="w-3.5 h-3.5 text-gray-500" />
                                          <span
                                            className="text-gray-900"
                                            style={{ fontSize: '13px' }}
                                          >
                                            {source.documentName}
                                          </span>
                                          <Badge variant="outline" style={{ fontSize: '10px' }}>
                                            {source.location}
                                          </Badge>
                                        </div>
                                        <p
                                          className="text-gray-700 italic pl-5"
                                          style={{ fontSize: '12px' }}
                                        >
                                          &quot;{source.excerpt}&quot;
                                        </p>
                                      </div>
                                    ))}
                                  </div>
                                </div>

                                {/* Resolution Section */}
                                {contradiction.status === 'open' && (
                                  <>
                                    <Separator />
                                    <div className="space-y-3">
                                      <Label
                                        htmlFor={`resolution-${contradiction.id}`}
                                        style={{ fontSize: '13px' }}
                                      >
                                        Resolution Instructions for AI
                                      </Label>
                                      <Textarea
                                        id={`resolution-${contradiction.id}`}
                                        value={resolutionInstructions[contradiction.id] || ''}
                                        onChange={e =>
                                          setResolutionInstructions(prev => ({
                                            ...prev,
                                            [contradiction.id]: e.target.value,
                                          }))
                                        }
                                        placeholder="Explain how the AI should handle this contradiction. For example: 'Exclude patients with IBD diagnosis regardless of colonoscopy timing. The 10-year colonoscopy rule applies only to average-risk screening, not diagnostic procedures.'"
                                        className="min-h-[100px]"
                                        style={{ fontSize: '13px' }}
                                      />
                                      <p className="text-gray-500" style={{ fontSize: '12px' }}>
                                        💡 Provide clear, specific instructions. The AI will use
                                        this to make better decisions when extracting criteria and
                                        screening patients.
                                      </p>
                                      <div className="flex gap-2 pt-2">
                                        <Button
                                          size="sm"
                                          onClick={() =>
                                            handleResolveContradiction(contradiction.id)
                                          }
                                          className="gap-1"
                                          style={{ fontSize: '13px' }}
                                        >
                                          <Check className="w-3.5 h-3.5" />
                                          Resolve with Instructions
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={() =>
                                            handleDismissContradiction(contradiction.id)
                                          }
                                          className="gap-1"
                                          style={{ fontSize: '13px' }}
                                        >
                                          <X className="w-3.5 h-3.5" />
                                          Dismiss (Not a Real Conflict)
                                        </Button>
                                      </div>
                                    </div>
                                  </>
                                )}

                                {/* Show Resolution if Resolved */}
                                {contradiction.status === 'resolved' &&
                                  contradiction.resolution && (
                                    <>
                                      <Separator />
                                      <div className="space-y-2">
                                        <Label
                                          className="flex items-center gap-2"
                                          style={{ fontSize: '13px' }}
                                        >
                                          <Check className="w-3.5 h-3.5 text-green-600" />
                                          Resolution Applied
                                        </Label>
                                        <div className="p-3 bg-green-50 border border-green-200 rounded space-y-2">
                                          <p
                                            className="text-green-900"
                                            style={{ fontSize: '13px' }}
                                          >
                                            {contradiction.resolution.instructions}
                                          </p>
                                          <div
                                            className="flex items-center gap-3 text-green-700"
                                            style={{ fontSize: '11px' }}
                                          >
                                            <span>
                                              Resolved by {contradiction.resolution.resolvedBy}
                                            </span>
                                            <span>•</span>
                                            <span>
                                              {new Date(
                                                contradiction.resolution.resolvedAt
                                              ).toLocaleDateString()}
                                            </span>
                                          </div>
                                        </div>
                                        <Button
                                          size="sm"
                                          variant="ghost"
                                          onClick={() =>
                                            handleReopenContradiction(contradiction.id)
                                          }
                                          className="gap-1"
                                          style={{ fontSize: '12px' }}
                                        >
                                          Reopen
                                        </Button>
                                      </div>
                                    </>
                                  )}
                              </>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="viewer" className="flex-1 mt-0">
            <ScrollArea className="h-[calc(100vh-220px)]">
              <div className="p-6">
                {selectedDoc ? (
                  <div className="space-y-4">
                    {/* Document Header */}
                    <div className="space-y-2">
                      <h3 style={{ fontSize: '16px' }}>{selectedDoc.name}</h3>
                      <div className="flex items-center gap-2">
                        {getTypeBadge(selectedDoc.type)}
                        {getDocumentStatusBadge(selectedDoc.status)}
                      </div>
                    </div>

                    <Separator />

                    {/* Document Content */}
                    <div className="p-4 bg-gray-50 border rounded-lg">
                      <div className="prose prose-sm max-w-none">
                        <pre
                          className="whitespace-pre-wrap text-gray-900 leading-relaxed"
                          style={{ fontSize: '13px' }}
                        >
                          {selectedDoc.content || 'Content not available'}
                        </pre>
                      </div>
                    </div>

                    <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                      <p className="text-blue-900" style={{ fontSize: '13px' }}>
                        💡 <strong>Tip:</strong> Use the &quot;Add New Criterion&quot; panel to highlight and
                        extract specific sections from this document as inclusion/exclusion
                        criteria.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                    <FileText className="w-12 h-12 mb-4" />
                    <p style={{ fontSize: '14px' }}>Select a document to view its contents</p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex justify-end">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            style={{ fontSize: '14px' }}
          >
            Close
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
