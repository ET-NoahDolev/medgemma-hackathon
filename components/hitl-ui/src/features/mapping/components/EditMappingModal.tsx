import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Search,
  ArrowRight,
  ArrowLeft,
  Check,
  AlertTriangle,
  Database,
  TrendingUp,
  X,
} from 'lucide-react';

interface Mapping {
  id: string;
  emrTerm: string;
  targetCode: string;
  targetSystem: string;
  targetDescription: string;
  patientCount: number;
}

interface EditMappingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mapping: Mapping;
  onSave: (data: {
    newCode: string;
    newSystem: string;
    newDescription: string;
    rationale: string;
    suggestToNetwork: boolean;
  }) => void;
}

interface ConceptResult {
  code: string;
  system: string;
  description: string;
  usageCount: number;
  crossReferences?: {
    umls?: string;
    snomedCT?: string;
    icd10?: string;
    loinc?: string;
  };
}

const mockConcepts: ConceptResult[] = [
  {
    code: '29857009',
    system: 'SNOMED CT',
    description: 'Chest pain',
    usageCount: 1234,
    crossReferences: { umls: 'C0008031', icd10: 'R07.9' },
  },
  {
    code: '426976009',
    system: 'SNOMED CT',
    description: 'Chest discomfort',
    usageCount: 456,
    crossReferences: { umls: 'C0235710', icd10: 'R07.89' },
  },
  {
    code: '279039007',
    system: 'SNOMED CT',
    description: 'Low chest pain',
    usageCount: 89,
    crossReferences: { umls: 'C0008031' },
  },
  {
    code: 'R07.9',
    system: 'ICD-10',
    description: 'Chest pain, unspecified',
    usageCount: 678,
    crossReferences: { umls: 'C0008031', snomedCT: '29857009' },
  },
  {
    code: 'C0008031',
    system: 'UMLS',
    description: 'Chest Pain',
    usageCount: 2345,
    crossReferences: { snomedCT: '29857009', icd10: 'R07.9' },
  },
  {
    code: '8480-6',
    system: 'LOINC',
    description: 'Systolic blood pressure',
    usageCount: 3456,
    crossReferences: { umls: 'C0871470', snomedCT: '271649006' },
  },
  {
    code: '8462-4',
    system: 'LOINC',
    description: 'Diastolic blood pressure',
    usageCount: 3421,
    crossReferences: { umls: 'C0428883', snomedCT: '271650006' },
  },
];

export function EditMappingModal({ open, onOpenChange, mapping, onSave }: EditMappingModalProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedConcept, setSelectedConcept] = useState<ConceptResult | null>(null);
  const [rationale, setRationale] = useState('');
  const [suggestToNetwork, setSuggestToNetwork] = useState(true);
  const [isCreatingCustom, setIsCreatingCustom] = useState(false);
  const [customCode, setCustomCode] = useState('');
  const [customSystem, setCustomSystem] = useState('');
  const [customDescription, setCustomDescription] = useState('');
  const prevOpenRef = useRef(open);

  useEffect(() => {
    // Only reset when transitioning from closed to open
    if (open && !prevOpenRef.current) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Reset state when modal opens
      setStep(1);
      setSearchQuery('');
      setSelectedConcept(null);
      setRationale('');
      setSuggestToNetwork(true);
      setIsCreatingCustom(false);
      setCustomCode('');
      setCustomSystem('');
      setCustomDescription('');
    }
    prevOpenRef.current = open;
  }, [open]);

  const filteredConcepts = mockConcepts.filter(
    concept =>
      concept.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      concept.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleNext = () => {
    if (selectedConcept || isCreatingCustom) {
      setStep(2);
    }
  };

  const handleSave = () => {
    if (!rationale.trim()) return;

    const data = isCreatingCustom
      ? {
          newCode: customCode,
          newSystem: customSystem,
          newDescription: customDescription,
          rationale,
          suggestToNetwork,
        }
      : {
          newCode: selectedConcept!.code,
          newSystem: selectedConcept!.system,
          newDescription: selectedConcept!.description,
          rationale,
          suggestToNetwork,
        };

    onSave(data);
  };

  const canProceed =
    step === 1
      ? selectedConcept || (isCreatingCustom && customCode && customSystem && customDescription)
      : rationale.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl p-0 flex flex-col h-[85vh]" style={{ gap: 0 }}>
        <DialogTitle className="sr-only">Modify Mapping: {mapping.emrTerm}</DialogTitle>
        <DialogDescription className="sr-only">
          Edit the semantic mapping for the EMR term to a new target concept
        </DialogDescription>

        {/* Header */}
        <div className="px-6 py-4 border-b bg-teal-50 flex-shrink-0">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-gray-900 font-semibold" style={{ fontSize: '18px' }}>
              Modify Mapping: <span className="text-teal-700">{mapping.emrTerm}</span>
            </h3>
            <Badge variant="outline" style={{ fontSize: '12px' }}>
              Step {step} of 2
            </Badge>
          </div>

          {/* Current Mapping Reference */}
          <div className="p-3 bg-white border border-gray-200 rounded-lg">
            <p className="text-gray-600 mb-1" style={{ fontSize: '12px' }}>
              Current Mapping:
            </p>
            <div className="flex items-center gap-2">
              <span className="font-mono text-gray-900" style={{ fontSize: '14px' }}>
                {mapping.targetSystem}:{mapping.targetCode}
              </span>
              <span className="text-gray-400">—</span>
              <span className="text-gray-700" style={{ fontSize: '14px' }}>
                {mapping.targetDescription}
              </span>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ScrollArea className="h-full">
            <div className="p-6">
              {step === 1 && (
                <div className="space-y-4">
                  {/* Step 1: Target Concept Selection */}
                  <div className="space-y-3">
                    <Label className="flex items-center gap-2" style={{ fontSize: '14px' }}>
                      Search Target Concept
                      <Badge variant="outline" style={{ fontSize: '11px' }}>
                        Required
                      </Badge>
                    </Label>

                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <Input
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder="Search UMLS, SNOMED CT, LOINC, ICD-10..."
                        className="pl-10"
                        style={{ fontSize: '14px' }}
                      />
                    </div>
                  </div>

                  {searchQuery && (
                    <>
                      <Separator />

                      <div className="space-y-2">
                        <Label style={{ fontSize: '14px' }}>Search Results</Label>
                        <div className="space-y-2">
                          {filteredConcepts.map(concept => (
                            <button
                              key={`${concept.system}-${concept.code}`}
                              onClick={() => {
                                setSelectedConcept(concept);
                                setIsCreatingCustom(false);
                              }}
                              className={`w-full p-3 border rounded-lg text-left transition-all ${
                                selectedConcept?.code === concept.code &&
                                selectedConcept?.system === concept.system
                                  ? 'border-teal-500 bg-teal-50'
                                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <Badge
                                      className="bg-blue-100 text-blue-700 border-blue-300"
                                      style={{ fontSize: '11px' }}
                                    >
                                      {concept.system}
                                    </Badge>
                                    <span
                                      className="font-mono text-gray-900"
                                      style={{ fontSize: '14px' }}
                                    >
                                      {concept.code}
                                    </span>
                                  </div>
                                  <p className="text-gray-700" style={{ fontSize: '14px' }}>
                                    {concept.description}
                                  </p>
                                  {concept.crossReferences &&
                                    Object.keys(concept.crossReferences).length > 0 && (
                                      <div className="flex flex-wrap gap-2 mt-2">
                                        {concept.crossReferences.umls && (
                                          <Badge
                                            variant="outline"
                                            className="font-mono"
                                            style={{ fontSize: '11px' }}
                                          >
                                            UMLS: {concept.crossReferences.umls}
                                          </Badge>
                                        )}
                                        {concept.crossReferences.snomedCT && (
                                          <Badge
                                            variant="outline"
                                            className="font-mono"
                                            style={{ fontSize: '11px' }}
                                          >
                                            SNOMED: {concept.crossReferences.snomedCT}
                                          </Badge>
                                        )}
                                        {concept.crossReferences.icd10 && (
                                          <Badge
                                            variant="outline"
                                            className="font-mono"
                                            style={{ fontSize: '11px' }}
                                          >
                                            ICD-10: {concept.crossReferences.icd10}
                                          </Badge>
                                        )}
                                        {concept.crossReferences.loinc && (
                                          <Badge
                                            variant="outline"
                                            className="font-mono"
                                            style={{ fontSize: '11px' }}
                                          >
                                            LOINC: {concept.crossReferences.loinc}
                                          </Badge>
                                        )}
                                      </div>
                                    )}
                                  <div
                                    className="flex items-center gap-1 mt-2 text-gray-500"
                                    style={{ fontSize: '12px' }}
                                  >
                                    <TrendingUp className="w-3 h-3" />
                                    Used {concept.usageCount} times across network
                                  </div>
                                </div>
                                {selectedConcept?.code === concept.code &&
                                  selectedConcept?.system === concept.system && (
                                    <Check className="w-5 h-5 text-teal-600 flex-shrink-0" />
                                  )}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  )}

                  <Separator />

                  {/* Create Custom Concept */}
                  {!isCreatingCustom ? (
                    <Button
                      variant="outline"
                      className="w-full justify-start border-dashed gap-2"
                      onClick={() => {
                        setIsCreatingCustom(true);
                        setSelectedConcept(null);
                      }}
                      style={{ fontSize: '14px' }}
                    >
                      <Database className="w-4 h-4" />
                      Create custom concept (site-specific)
                    </Button>
                  ) : (
                    <div className="p-4 bg-blue-50 border-2 border-blue-200 rounded-lg space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="flex items-center gap-2" style={{ fontSize: '14px' }}>
                          <Database className="w-4 h-4" />
                          Create Custom Concept
                        </Label>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setIsCreatingCustom(false);
                            setCustomCode('');
                            setCustomSystem('');
                            setCustomDescription('');
                          }}
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>

                      <div className="space-y-3">
                        <div className="space-y-2">
                          <Label htmlFor="customSystem" style={{ fontSize: '12px' }}>
                            System
                          </Label>
                          <Input
                            id="customSystem"
                            value={customSystem}
                            onChange={e => setCustomSystem(e.target.value)}
                            placeholder="e.g., SITE-BOSTON"
                            style={{ fontSize: '14px' }}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="customCode" style={{ fontSize: '12px' }}>
                            Code
                          </Label>
                          <Input
                            id="customCode"
                            value={customCode}
                            onChange={e => setCustomCode(e.target.value)}
                            placeholder="e.g., CP-001"
                            style={{ fontSize: '14px' }}
                          />
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="customDescription" style={{ fontSize: '12px' }}>
                            Description
                          </Label>
                          <Input
                            id="customDescription"
                            value={customDescription}
                            onChange={e => setCustomDescription(e.target.value)}
                            placeholder="e.g., Chest pressure variant"
                            style={{ fontSize: '14px' }}
                          />
                        </div>
                      </div>

                      <div
                        className="p-2 bg-amber-50 border border-amber-200 rounded"
                        style={{ fontSize: '12px' }}
                      >
                        <p className="text-amber-900 flex items-start gap-2">
                          <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                          <span>
                            Custom concepts will be flagged as site-specific and won&apos;t be
                            available to the network
                          </span>
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {step === 2 && (
                <div className="space-y-4">
                  {/* Step 2: Justification & Preview */}
                  <div className="space-y-3">
                    <Label style={{ fontSize: '14px' }}>Mapping Change Preview</Label>

                    <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
                      {/* Current */}
                      <div>
                        <p className="text-gray-600 mb-2" style={{ fontSize: '12px' }}>
                          Current:
                        </p>
                        <div className="flex items-center gap-2">
                          <Badge
                            className="bg-gray-100 text-gray-700 border-gray-300"
                            style={{ fontSize: '11px' }}
                          >
                            {mapping.targetSystem}
                          </Badge>
                          <span className="font-mono text-gray-900" style={{ fontSize: '14px' }}>
                            {mapping.targetCode}
                          </span>
                          <span className="text-gray-400">—</span>
                          <span className="text-gray-700" style={{ fontSize: '14px' }}>
                            {mapping.targetDescription}
                          </span>
                        </div>
                      </div>

                      <ArrowRight className="w-5 h-5 text-gray-400 mx-auto" />

                      {/* New */}
                      <div>
                        <p className="text-gray-600 mb-2" style={{ fontSize: '12px' }}>
                          New:
                        </p>
                        <div className="flex items-center gap-2">
                          <Badge
                            className="bg-teal-100 text-teal-700 border-teal-300"
                            style={{ fontSize: '11px' }}
                          >
                            {isCreatingCustom ? customSystem : selectedConcept?.system}
                          </Badge>
                          <span className="font-mono text-gray-900" style={{ fontSize: '14px' }}>
                            {isCreatingCustom ? customCode : selectedConcept?.code}
                          </span>
                          <span className="text-gray-400">—</span>
                          <span className="text-gray-700" style={{ fontSize: '14px' }}>
                            {isCreatingCustom ? customDescription : selectedConcept?.description}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <Separator />

                  <div className="space-y-3">
                    <Label
                      htmlFor="rationale"
                      className="flex items-center gap-2"
                      style={{ fontSize: '14px' }}
                    >
                      Reason for Change
                      <Badge variant="outline" style={{ fontSize: '11px' }}>
                        Required
                      </Badge>
                    </Label>
                    <Textarea
                      id="rationale"
                      value={rationale}
                      onChange={e => setRationale(e.target.value)}
                      placeholder="Explain why this mapping change is necessary..."
                      rows={4}
                      className="resize-none"
                      style={{ fontSize: '14px' }}
                    />
                    <p className="text-gray-500" style={{ fontSize: '12px' }}>
                      This will be logged to the audit trail
                    </p>
                  </div>

                  <Separator />

                  <div className="flex items-start gap-3">
                    <Checkbox
                      id="suggestNetwork"
                      checked={suggestToNetwork}
                      onCheckedChange={checked => setSuggestToNetwork(checked as boolean)}
                    />
                    <div className="flex-1">
                      <Label
                        htmlFor="suggestNetwork"
                        className="cursor-pointer"
                        style={{ fontSize: '14px' }}
                      >
                        Suggest to network
                      </Label>
                      <p className="text-gray-500 mt-1" style={{ fontSize: '12px' }}>
                        Share this mapping with other sites to improve network-wide validation
                      </p>
                    </div>
                  </div>

                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                    <p
                      className="text-amber-900 flex items-start gap-2"
                      style={{ fontSize: '12px' }}
                    >
                      <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                      <span>
                        <strong>Impact:</strong> Will affect {mapping.patientCount} patients
                        {isCreatingCustom && ' and create a site-specific variant'}
                      </span>
                    </p>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-between flex-shrink-0">
          <div>
            {step === 2 && (
              <Button
                variant="ghost"
                onClick={() => setStep(1)}
                className="gap-2"
                style={{ fontSize: '14px' }}
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
            )}
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              style={{ fontSize: '14px' }}
            >
              Cancel
            </Button>

            {step === 1 ? (
              <Button
                onClick={handleNext}
                disabled={!canProceed}
                className="gap-2 bg-teal-600 hover:bg-teal-700"
                style={{ fontSize: '14px' }}
              >
                Next
                <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSave}
                disabled={!canProceed}
                className="gap-2 bg-teal-600 hover:bg-teal-700"
                style={{ fontSize: '14px' }}
              >
                <Check className="w-4 h-4" />
                Save Validation
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
