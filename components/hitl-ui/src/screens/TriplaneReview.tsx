import { useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { CriteriaItem } from '@/features/protocols/components/CriteriaItem';
import { EvidenceSnippet } from '@/features/protocols/components/EvidenceSnippet';
import { CriteriaEditPanel } from '@/features/protocols/components/CriteriaEditPanel';
import { StatusType } from '@/components/common/StatusTag';
import { Button } from '@/components/ui/button';
import { GlassButton } from '@/components/ui/glass-button';
import { ChevronLeft, ChevronRight, CheckCircle2, XCircle } from 'lucide-react';
import { toast } from 'sonner';

interface Criterion {
  id: string;
  type: 'inclusion' | 'exclusion';
  criterion: string;
  status: StatusType;
  aiSummary: string;
  sourceText?: string; // Original protocol text
  evidence: Array<{
    source: string;
    timestamp: string;
    location?: string;
    snippet: string;
    highlighted?: string[];
  }>;
}

const mockCriteria: Criterion[] = [
  {
    id: '1',
    type: 'inclusion',
    criterion: 'Age ≥ 45 and ≤ 75 years at time of screening',
    status: 'matched',
    sourceText:
      'Section 4.1: Eligible participants must be between 45 and 75 years old at the time of screening visit.',
    aiSummary:
      'Patient is 52 years old based on DOB 04/12/1972. Age confirmed in demographics and recent clinic notes.',
    evidence: [
      {
        source: 'Demographics - EHR',
        timestamp: '2024-10-15',
        snippet: 'Date of Birth: 04/12/1972 (52 years old)',
        highlighted: ['52 years old'],
      },
      {
        source: 'Primary Care Visit Note',
        timestamp: '2024-09-20',
        location: 'Clinic A',
        snippet: 'Patient is a 52-year-old female presenting for annual physical examination.',
        highlighted: ['52-year-old'],
      },
    ],
  },
  {
    id: '2',
    type: 'inclusion',
    criterion: 'Average-risk for colorectal cancer (no personal or family history)',
    status: 'likely',
    sourceText:
      'Section 4.1.2: Participants should have average risk with no personal or family history of colorectal cancer or advanced adenomas.',
    aiSummary:
      'No documented personal history of CRC or polyps. Family history section shows "denies" for cancer history in recent notes, though comprehensive family tree not available.',
    evidence: [
      {
        source: 'Problem List',
        timestamp: '2024-10-01',
        snippet:
          'Active problems: Hypertension, Type 2 Diabetes. No history of colorectal cancer or polyps documented.',
        highlighted: ['No history of colorectal cancer'],
      },
      {
        source: 'Annual Physical Note',
        timestamp: '2024-09-20',
        snippet:
          'Family history: Patient denies family history of cancer. Mother alive, father deceased (CVA).',
        highlighted: ['denies family history of cancer'],
      },
    ],
  },
  {
    id: '3',
    type: 'inclusion',
    criterion: 'No colonoscopy in past 10 years',
    status: 'needs-review',
    sourceText:
      'Section 4.1.3: Must not have undergone colonoscopy within the last 10 years prior to enrollment.',
    aiSummary:
      'HIDDEN NOTE FOUND: Procedure note from 2019 mentions "colonoscopy" but context suggests it was a discussion/referral, not completed. No procedure report found in system. Recommend manual verification.',
    evidence: [
      {
        source: 'Gastroenterology Consult',
        timestamp: '2019-03-15',
        location: 'GI Clinic',
        snippet:
          'Discussed colonoscopy screening with patient. Patient declined at this time due to work schedule. Provided educational materials and will follow up in 6 months.',
        highlighted: ['colonoscopy', 'declined'],
      },
      {
        source: 'Procedure History Query',
        timestamp: '2024-10-20',
        snippet:
          'Search results: No colonoscopy procedures found in past 10 years across hospital system.',
        highlighted: ['No colonoscopy procedures'],
      },
    ],
  },
  {
    id: '1',
    type: 'exclusion',
    criterion: "History of inflammatory bowel disease (Crohn's or ulcerative colitis)",
    status: 'matched',
    sourceText:
      "Section 4.2.1: Exclude patients with inflammatory bowel disease including Crohn's disease or ulcerative colitis.",
    aiSummary:
      'No IBD diagnosis in problem list. No relevant medications (immunosuppressants, biologics). No GI specialty visits for IBD management.',
    evidence: [
      {
        source: 'Problem List',
        timestamp: '2024-10-01',
        snippet:
          'Active problems: Hypertension, Type 2 Diabetes. No inflammatory bowel disease documented.',
        highlighted: ['No inflammatory bowel disease'],
      },
    ],
  },
  {
    id: '2',
    type: 'exclusion',
    criterion: 'Current diagnosis of any cancer',
    status: 'matched',
    sourceText:
      'Section 4.2.3: Active cancer diagnosis is an exclusion criterion for study participation.',
    aiSummary:
      'No active cancer diagnoses. No oncology visits. No chemotherapy or radiation therapy in medication/procedure history.',
    evidence: [
      {
        source: 'Problem List',
        timestamp: '2024-10-01',
        snippet: 'Active problems: Hypertension, Type 2 Diabetes. No cancer diagnoses.',
        highlighted: ['No cancer'],
      },
    ],
  },
  {
    id: '3',
    type: 'exclusion',
    criterion: 'Blood pressure >160/100 mmHg despite treatment',
    status: 'ai-suggested',
    sourceText:
      'Section 4.2.5: Patients with uncontrolled hypertension (blood pressure >160/100 mmHg despite antihypertensive therapy) should be excluded.',
    aiSummary:
      'MAPPING CONFLICT: Recent vitals show BP 158/98 (2024-10-20) and 162/102 (2024-09-15). Patient on antihypertensive therapy (Lisinopril 20mg). Requires clinical judgment on "despite treatment" - may need dose adjustment vs. exclusion.',
    evidence: [
      {
        source: 'Vital Signs',
        timestamp: '2024-10-20',
        location: 'Primary Care',
        snippet: 'BP: 158/98 mmHg, HR: 72 bpm, Temp: 98.6°F',
        highlighted: ['158/98 mmHg'],
      },
      {
        source: 'Vital Signs',
        timestamp: '2024-09-15',
        location: 'Primary Care',
        snippet: 'BP: 162/102 mmHg, HR: 76 bpm',
        highlighted: ['162/102 mmHg'],
      },
      {
        source: 'Medication List',
        timestamp: '2024-10-01',
        snippet: 'Lisinopril 20mg PO daily for hypertension. Metformin 1000mg PO BID for diabetes.',
        highlighted: ['Lisinopril 20mg', 'hypertension'],
      },
    ],
  },
];

interface TriplaneReviewProps {
  patientId?: string;
  onApprove?: () => void;
  onReject?: () => void;
  onBack?: () => void;
  onViewChart?: (patientId: string) => void;
}

export function TriplaneReview({
  patientId = 'PT-2024-0042',
  onApprove,
  onReject,
  onBack,
  onViewChart: _onViewChart,
}: TriplaneReviewProps) {
  const [selectedCriterion, setSelectedCriterion] = useState<Criterion>(mockCriteria[2]);
  const [criteria, setCriteria] = useState(mockCriteria);
  const [editPanelOpen, setEditPanelOpen] = useState(false);
  const [criterionToEdit, setCriterionToEdit] = useState<Criterion | null>(null);

  const handleCorrection =
    (criterionId: string, type: 'inclusion' | 'exclusion') =>
    (correctedStatus: StatusType, _rationale: string) => {
      setCriteria(prev =>
        prev.map(c =>
          c.id === criterionId && c.type === type ? { ...c, status: correctedStatus } : c
        )
      );
      // TODO: Submit correction to backend
    };

  const handleOpenEditPanel = (criterion: Criterion) => {
    setCriterionToEdit(criterion);
    setEditPanelOpen(true);
  };

  const handleSaveEditPanel = (updates: { text: string; type: string; rationale?: string }) => {
    if (criterionToEdit) {
      setCriteria(prev =>
        prev.map(c =>
          c.id === criterionToEdit.id && c.type === criterionToEdit.type
            ? {
                ...c,
                criterion: updates.text,
                type: updates.type === 'not-applicable' ? c.type : updates.type,
              }
            : c
        )
      );

      // Update selected criterion if it's the one being edited
      if (
        selectedCriterion.id === criterionToEdit.id &&
        selectedCriterion.type === criterionToEdit.type
      ) {
        setSelectedCriterion(prev => ({
          ...prev,
          criterion: updates.text,
          type: updates.type === 'not-applicable' ? prev.type : updates.type,
        }));
      }

      toast.success('Criterion updated', {
        description: `Changes saved: ${updates.rationale}`,
      });
    }
  };

  const handleDeleteCriterion = (rationale: string) => {
    if (criterionToEdit) {
      setCriteria(prev =>
        prev.filter(c => !(c.id === criterionToEdit.id && c.type === criterionToEdit.type))
      );

      // If deleted criterion was selected, select the first one
      if (
        selectedCriterion.id === criterionToEdit.id &&
        selectedCriterion.type === criterionToEdit.type
      ) {
        const remaining = criteria.filter(
          c => !(c.id === criterionToEdit.id && c.type === criterionToEdit.type)
        );
        if (remaining.length > 0) {
          setSelectedCriterion(remaining[0]);
        }
      }

      toast.success('Criterion removed', {
        description: `${criterionToEdit.type === 'inclusion' ? 'I' : 'E'}${criterionToEdit.id} removed: ${rationale}`,
      });
    }
  };

  const inclusionCriteria = criteria.filter(c => c.type === 'inclusion');
  const exclusionCriteria = criteria.filter(c => c.type === 'exclusion');

  const matchedCount = criteria.filter(c => c.status === 'matched').length;
  const needsReviewCount = criteria.filter(
    c => c.status === 'needs-review' || c.status === 'ai-suggested'
  ).length;

  return (
    <div className="flex h-full bg-transparent">
      {/* Left Panel - I/E Checklist */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          {onBack && (
            <Button variant="outline" onClick={onBack} className="mb-3 w-full">
              <ChevronLeft className="w-4 h-4 mr-2" />
              Back to Triage
            </Button>
          )}
          <h2 className="text-gray-900">Inclusion/Exclusion Criteria</h2>
          <p className="text-sm text-gray-600 mt-1">{patientId}</p>
          <div className="flex gap-2 mt-3 text-xs">
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-green-500 rounded-full" />
              <span className="text-gray-600">{matchedCount} matched</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-2 h-2 bg-yellow-500 rounded-full" />
              <span className="text-gray-600">{needsReviewCount} review</span>
            </div>
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-4">
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-900 mb-3">Inclusion Criteria</h3>
              <div className="space-y-2">
                {inclusionCriteria.map(c => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedCriterion(c)}
                    className={`w-full text-left p-2 rounded-lg border transition-all ${
                      selectedCriterion === c
                        ? 'border-teal-500 bg-teal-50'
                        : 'border-gray-200 hover:border-gray-300 bg-white'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
                        I{c.id}
                      </span>
                      <p className="text-xs text-gray-700 flex-1">{c.criterion}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-medium text-gray-900 mb-3">Exclusion Criteria</h3>
              <div className="space-y-2">
                {exclusionCriteria.map(c => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedCriterion(c)}
                    className={`w-full text-left p-2 rounded-lg border transition-all ${
                      selectedCriterion === c
                        ? 'border-teal-500 bg-teal-50'
                        : 'border-gray-200 hover:border-gray-300 bg-white'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-xs px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
                        E{c.id}
                      </span>
                      <p className="text-xs text-gray-700 flex-1">{c.criterion}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </ScrollArea>
      </div>

      {/* Middle Panel - AI Summary */}
      <div className="flex-1 flex flex-col bg-white border-r border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className={`text-xs px-2 py-0.5 rounded ${
                    selectedCriterion.type === 'inclusion'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {selectedCriterion.type === 'inclusion' ? 'I' : 'E'}
                  {selectedCriterion.id}
                </span>
              </div>
              <h2 className="font-medium text-gray-900">{selectedCriterion.criterion}</h2>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleOpenEditPanel(selectedCriterion)}
              className="ml-4 gap-1"
            >
              <ChevronRight className="w-3 h-3" />
              Edit Mapping
            </Button>
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-6">
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-900 mb-3">AI Assessment</h3>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm text-gray-700 leading-relaxed">
                  {selectedCriterion.aiSummary}
                </p>
              </div>
            </div>

            <div>
              <CriteriaItem
                {...selectedCriterion}
                evidence={selectedCriterion.evidence.map(e => e.snippet)}
                onCorrect={handleCorrection(selectedCriterion.id, selectedCriterion.type)}
              />
            </div>
          </div>
        </ScrollArea>
      </div>

      {/* Right Panel - Evidence */}
      <div className="w-96 bg-gray-50 flex flex-col">
        <div className="p-4 bg-white border-b border-gray-200">
          <h2 className="font-semibold text-gray-900">Evidence</h2>
          <p className="text-sm text-gray-600 mt-1">
            {selectedCriterion.evidence.length} source
            {selectedCriterion.evidence.length !== 1 ? 's' : ''}
          </p>
        </div>

        <ScrollArea className="flex-1 p-4">
          <div className="space-y-3">
            {selectedCriterion.evidence.map((ev, idx) => (
              <EvidenceSnippet key={idx} {...ev} />
            ))}
          </div>
        </ScrollArea>

        <div className="p-4 bg-white border-t border-gray-200">
          <div className="flex gap-2">
            <GlassButton variant="primary" onClick={onApprove} className="flex-1">
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Approve Patient
            </GlassButton>
            <Button
              onClick={onReject}
              variant="outline"
              className="flex-1 border-red-300 text-red-700 hover:bg-red-50"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Screen Failed
            </Button>
          </div>
        </div>
      </div>

      {/* Edit Panel */}
      {criterionToEdit && (
        <CriteriaEditPanel
          open={editPanelOpen}
          onOpenChange={setEditPanelOpen}
          criterion={{
            id: criterionToEdit.id,
            type: criterionToEdit.type,
            text: criterionToEdit.criterion,
            status: criterionToEdit.status,
            sourceText: criterionToEdit.sourceText,
          }}
          onSave={handleSaveEditPanel}
          onDelete={handleDeleteCriterion}
        />
      )}
    </div>
  );
}
