import { useState, useMemo, useCallback } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Plus,
  Save,
  X,
  Highlighter,
  FileText,
  Link2,
  Trash2,
  Maximize2,
  Minimize2,
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { FieldMappingPopup } from '@/features/mapping/components/FieldMappingPopup';
import { useSuggestFieldMapping } from '@/hooks/useFieldMapping';

interface FieldMapping {
  targetField: string;
  relation: string;
  targetValue: string;
  targetValueMin?: string;
  targetValueMax?: string;
  targetValueUnit?: string;
  isNewField: boolean;
  isNewValue: boolean;
  sourceText: string;
}

interface SourceDocument {
  id: string;
  name: string;
  content: string;
  type?: 'protocol' | 'ecrf' | 'other';
}

interface AddCriteriaPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  sourceDocuments?: SourceDocument[];
  onSave: (criterion: {
    text: string;
    type: 'inclusion' | 'exclusion';
    sourceText: string;
    sourceDocumentId: string;
    fieldMappings?: FieldMapping[];
  }) => void;
}

// Mock default documents if none provided
const defaultDocuments: SourceDocument[] = [
  {
    id: 'doc-1',
    name: 'CRC-Study-Protocol-v2.3.pdf',
    type: 'protocol',
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
    content: `ELECTRONIC CASE REPORT FORM (eCRF)
Study: CRC-Screening-2024

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
];

export function AddCriteriaPanel({
  open,
  onOpenChange,
  sourceDocuments = defaultDocuments,
  onSave,
}: AddCriteriaPanelProps) {
  const [criterionType, setCriterionType] = useState<'inclusion' | 'exclusion'>('inclusion');
  const [criterionText, setCriterionText] = useState('');
  const [selectedText, setSelectedText] = useState('');
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>(
    sourceDocuments[0]?.id || ''
  );
  const [highlightedRanges, setHighlightedRanges] = useState<
    Array<{ start: number; end: number; text: string }>
  >([]);
  const [fieldMappings, setFieldMappings] = useState<FieldMapping[]>([]);
  const [showMappingPopup, setShowMappingPopup] = useState(false);
  const [currentHighlightText, setCurrentHighlightText] = useState('');
  const [suggestedField, setSuggestedField] = useState<string>('');
  const [suggestedValue, setSuggestedValue] = useState<string>('');
  const [isPopout, setIsPopout] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const suggestFieldMapping = useSuggestFieldMapping();

  const currentDocument =
    sourceDocuments.find(doc => doc.id === selectedDocumentId) || sourceDocuments[0];

const handleClose = (isOpen: boolean) => {
    if (!isOpen) {
      // Reset form when closing
      setCriterionText('');
      setSelectedText('');
      setHighlightedRanges([]);
      setFieldMappings([]);
      setCriterionType('inclusion');
      setShowMappingPopup(false);
      setCurrentHighlightText('');
      setSuggestedField('');
      setSuggestedValue('');
    }
    onOpenChange(isOpen);
  };

  // Generate AI suggestions using backend API
  const generateAISuggestions = async (text: string): Promise<{ field: string; value: string }> => {
    try {
      const suggestions = await suggestFieldMapping.mutateAsync(text);
      if (suggestions.length > 0) {
        const first = suggestions[0];
        return {
          field: first.field,
          value: first.value,
        };
      }
    } catch (error) {
      console.error('Failed to get field mapping suggestions:', error);
      // Fallback to default if API fails
    }
    // Default fallback
    return { field: 'demographics.age', value: '45' };
  };

  const handleTextSelection = useCallback(async () => {
    const selection = window.getSelection();
    if (selection && selection.toString().trim()) {
      const text = selection.toString().trim();
      setSelectedText(text);
      setCurrentHighlightText(text);

      // In a real implementation, we'd calculate the actual ranges
      setHighlightedRanges(prev => [
        ...prev,
        {
          start: 0,
          end: text.length,
          text,
        },
      ]);

      // Generate AI suggestions using backend API
      const suggestions = await generateAISuggestions(text);
      setSuggestedField(suggestions.field);
      setSuggestedValue(suggestions.value);

      // Show the field mapping popup
      setShowMappingPopup(true);
    }
  }, [suggestFieldMapping]);

  const handleUseHighlightedText = useCallback(() => {
    if (selectedText) {
      setCriterionText(selectedText);
      toast.success('Text applied to criterion');
    }
  }, [selectedText]);

  const handleClearHighlights = useCallback(() => {
    setHighlightedRanges([]);
    setSelectedText('');
    setFieldMappings([]);
    setSuggestedField('');
    setSuggestedValue('');
  }, []);

  const handleSaveMapping = useCallback((mapping: {
    targetField: string;
    relation: string;
    targetValue: string;
    targetValueMin?: string;
    targetValueMax?: string;
    targetValueUnit?: string;
    isNewField: boolean;
    isNewValue: boolean;
  }) => {
    const newMapping: FieldMapping = {
      ...mapping,
      sourceText: currentHighlightText,
    };

    setFieldMappings(prev => [...prev, newMapping]);

    toast.success('Field mapping added', {
      description: `Mapped to ${mapping.targetField}`,
    });
  }, [currentHighlightText]);

  const handleRemoveMapping = useCallback((index: number) => {
    setFieldMappings(prev => prev.filter((_, i) => i !== index));
    toast.success('Mapping removed');
  }, []);

  const handleSave = () => {
    if (!criterionText.trim()) {
      toast.error('Please enter criterion text');
      return;
    }

    if (!selectedText) {
      toast.error('Please highlight source text first');
      return;
    }

    onSave({
      text: criterionText,
      type: criterionType,
      sourceText: selectedText,
      sourceDocumentId: selectedDocumentId,
      fieldMappings: fieldMappings.length > 0 ? fieldMappings : undefined,
    });

    // Reset form
    setCriterionText('');
    setSelectedText('');
    setHighlightedRanges([]);
    setFieldMappings([]);
    setCriterionType('inclusion');
    setSuggestedField('');
    setSuggestedValue('');

    toast.success('Criterion added successfully', {
      description:
        fieldMappings.length > 0 ? `With ${fieldMappings.length} field mapping(s)` : undefined,
    });
    onOpenChange(false);
  };

  // Shared content component - memoized to avoid creating component during render
  const panelContent = useMemo(
    () => (
    <>
      <ScrollArea
        className="flex-1"
        style={{
          maxHeight: isPopout
            ? isFullscreen
              ? 'calc(100vh - 180px)'
              : 'calc(90vh - 180px)'
            : 'calc(100vh - 220px)',
        }}
      >
        <div className="p-6 space-y-6" style={{ fontSize: '14px' }}>
          {/* Source Document Selection */}
          <div className="space-y-3">
            <Label style={{ fontSize: '14px' }}>Source Document</Label>
            {sourceDocuments.length > 1 ? (
              <Select value={selectedDocumentId} onValueChange={setSelectedDocumentId}>
                <SelectTrigger className="w-full" style={{ fontSize: '14px' }}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {sourceDocuments.map(doc => (
                    <SelectItem key={doc.id} value={doc.id} style={{ fontSize: '14px' }}>
                      <div className="flex items-center gap-2">
                        <FileText className="w-3 h-3" />
                        {doc.name}
                        {doc.type && (
                          <Badge variant="outline" className="ml-2" style={{ fontSize: '11px' }}>
                            {doc.type}
                          </Badge>
                        )}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <div className="flex items-center gap-2 p-3 bg-gray-50 border rounded-lg">
                <FileText className="w-4 h-4 text-gray-600" />
                <span className="text-gray-900" style={{ fontSize: '14px' }}>
                  {currentDocument?.name}
                </span>
                {currentDocument?.type && (
                  <Badge variant="outline" className="ml-auto" style={{ fontSize: '11px' }}>
                    {currentDocument.type}
                  </Badge>
                )}
              </div>
            )}
          </div>

          {/* Source Document Viewer */}
          <div className="space-y-3">
            <Label style={{ fontSize: '14px' }}>Protocol Content - Select Text to Map</Label>

            <div
              className="p-4 bg-blue-50 border-2 border-blue-200 rounded-lg min-h-[240px] relative cursor-text select-text"
              onMouseUp={handleTextSelection}
            >
              <div className="prose prose-sm max-w-none">
                {currentDocument ? (
                  <p
                    className="text-gray-900 leading-relaxed whitespace-pre-wrap select-text"
                    style={{ fontSize: '14px' }}
                  >
                    {currentDocument.content}
                  </p>
                ) : (
                  <p className="text-gray-500 italic" style={{ fontSize: '14px' }}>
                    No source document loaded. Upload a protocol document from the main screen to
                    enable text selection.
                  </p>
                )}
              </div>

              {highlightedRanges.length > 0 && (
                <div className="absolute top-2 right-2 flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleUseHighlightedText}
                    className="gap-1 bg-white shadow-sm"
                    style={{ fontSize: '12px' }}
                  >
                    <Highlighter className="w-3 h-3" />
                    Use Highlighted
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleClearHighlights}
                    className="gap-1 bg-white shadow-sm"
                    style={{ fontSize: '12px' }}
                  >
                    <X className="w-3 h-3" />
                    Clear
                  </Button>
                </div>
              )}
            </div>

            <div className="p-3 bg-teal-50 border border-teal-200 rounded-lg">
              <p className="text-teal-900 flex items-start gap-2" style={{ fontSize: '14px' }}>
                <Highlighter className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>
                  <strong>Select text</strong> from the document above to capture source evidence. A
                  popup will appear to let you map the text to EDC fields for automated validation.
                </span>
              </p>
            </div>
          </div>

          {/* Highlighted Text Preview */}
          {selectedText && (
            <>
              <Separator />
              <div className="space-y-3">
                <Label style={{ fontSize: '14px' }}>Highlighted Source Text</Label>
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-gray-900 italic" style={{ fontSize: '14px' }}>
                    &quot;{selectedText}&quot;
                  </p>
                </div>
              </div>
            </>
          )}

          {/* Field Mappings */}
          {fieldMappings.length > 0 && (
            <>
              <Separator />
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="flex items-center gap-2" style={{ fontSize: '14px' }}>
                    <Link2 className="w-4 h-4" />
                    Field Mappings ({fieldMappings.length})
                  </Label>
                  <Badge
                    variant="outline"
                    className="bg-teal-50 text-teal-700 border-teal-300"
                    style={{ fontSize: '11px' }}
                  >
                    Will be created on save
                  </Badge>
                </div>
                <div className="space-y-2">
                  {fieldMappings.map((mapping, index) => (
                    <div
                      key={index}
                      className="p-3 bg-white border border-gray-200 rounded-lg space-y-2"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-2">
                            <span
                              className="font-medium text-gray-900"
                              style={{ fontSize: '14px' }}
                            >
                              {mapping.targetField}
                            </span>
                            {mapping.isNewField && (
                              <Badge
                                className="bg-blue-100 text-blue-700 border-blue-300"
                                style={{ fontSize: '11px' }}
                              >
                                New Field
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-gray-600" style={{ fontSize: '14px' }}>
                              Condition:
                            </span>
                            <code
                              className="font-mono text-teal-700 bg-teal-50 px-2 py-0.5 rounded"
                              style={{ fontSize: '13px' }}
                            >
                              {mapping.targetField} {mapping.relation || '='} {mapping.targetValue}
                            </code>
                            {mapping.isNewValue && (
                              <Badge variant="outline" style={{ fontSize: '11px' }}>
                                New Value
                              </Badge>
                            )}
                          </div>
                          <div className="text-gray-600 italic" style={{ fontSize: '12px' }}>
                            From: &quot;{mapping.sourceText}&quot;
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleRemoveMapping(index)}
                          className="ml-2"
                        >
                          <Trash2 className="w-3 h-3 text-red-600" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="flex items-start gap-2" style={{ fontSize: '12px' }}>
                  <Link2 className="w-3 h-3 mt-0.5 flex-shrink-0 text-gray-500" />
                  <span className="text-gray-500">
                    These mappings will be used to automatically extract and validate this criterion
                    from patient data
                  </span>
                </p>
              </div>
            </>
          )}

          <Separator />

          {/* Criterion Type */}
          <div className="space-y-3">
            <Label style={{ fontSize: '14px' }}>Criterion Type</Label>
            <RadioGroup
              value={criterionType}
              onValueChange={value => setCriterionType(value as 'inclusion' | 'exclusion')}
            >
              <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                <RadioGroupItem value="inclusion" id="inclusion" />
                <Label htmlFor="inclusion" className="flex-1 cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Badge
                      className="bg-green-100 text-green-700 border-green-300"
                      style={{ fontSize: '12px' }}
                    >
                      Inclusion
                    </Badge>
                    <span className="text-gray-600" style={{ fontSize: '14px' }}>
                      Patient must meet this criterion
                    </span>
                  </div>
                </Label>
              </div>
              <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                <RadioGroupItem value="exclusion" id="exclusion" />
                <Label htmlFor="exclusion" className="flex-1 cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Badge
                      className="bg-red-100 text-red-700 border-red-300"
                      style={{ fontSize: '12px' }}
                    >
                      Exclusion
                    </Badge>
                    <span className="text-gray-600" style={{ fontSize: '14px' }}>
                      Patient must NOT meet this criterion
                    </span>
                  </div>
                </Label>
              </div>
            </RadioGroup>
          </div>

          {/* Criterion Text */}
          <div className="space-y-3">
            <Label htmlFor="criterionText" style={{ fontSize: '14px' }}>
              Structured Criterion Text
            </Label>
            <Textarea
              id="criterionText"
              value={criterionText}
              onChange={e => setCriterionText(e.target.value)}
              placeholder="Enter the structured criterion text (e.g., 'Age ≥ 45 and ≤ 75 years at time of screening')"
              className="min-h-[120px] resize-none"
              style={{ fontSize: '14px' }}
            />
            <p className="text-gray-500" style={{ fontSize: '12px' }}>
              This is the structured, machine-readable version of the criterion that will be used
              for patient screening
            </p>
          </div>
        </div>
      </ScrollArea>
    </>
    ),
    [
      isPopout,
      isFullscreen,
      sourceDocuments,
      selectedDocumentId,
      currentDocument,
      handleTextSelection,
      handleUseHighlightedText,
      handleClearHighlights,
      selectedText,
      highlightedRanges,
      fieldMappings,
      handleRemoveMapping,
      criterionType,
      setCriterionType,
      criterionText,
      setCriterionText,
    ]
  );

  return (
    <>
      {isPopout ? (
        <Dialog open={open} onOpenChange={handleClose}>
          <DialogContent
            className={`p-0 flex flex-col ${isFullscreen ? '!fixed !inset-0 !w-screen !h-screen !max-w-none !translate-x-0 !translate-y-0 !m-0 !rounded-none' : 'max-w-[95vw] w-[1400px] h-[90vh]'}`}
            style={isFullscreen ? { gap: 0 } : { gap: 0 }}
          >
            <DialogHeader className="px-6 py-4 border-b flex-shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <DialogTitle className="flex items-center gap-2" style={{ fontSize: '18px' }}>
                    <Plus className="w-5 h-5" />
                    Add New Criterion
                  </DialogTitle>
                  <DialogDescription style={{ fontSize: '14px' }}>
                    Highlight text from the protocol document and create a new inclusion or
                    exclusion criterion
                  </DialogDescription>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsFullscreen(!isFullscreen)}
                    className="gap-2"
                    style={{ fontSize: '14px' }}
                  >
                    {isFullscreen ? (
                      <>
                        <Minimize2 className="w-4 h-4" />
                        Exit Fullscreen
                      </>
                    ) : (
                      <>
                        <Maximize2 className="w-4 h-4" />
                        Fullscreen
                      </>
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setIsPopout(false);
                      setIsFullscreen(false);
                    }}
                    className="gap-2"
                    style={{ fontSize: '14px' }}
                  >
                    <Minimize2 className="w-4 h-4" />
                    Return to Panel
                  </Button>
                </div>
              </div>
            </DialogHeader>

            {panelContent}

            {/* Footer Actions */}
            <div className="px-6 py-4 border-t bg-gray-50 flex gap-3 justify-end">
              <Button
                variant="outline"
                onClick={() => handleClose(false)}
                style={{ fontSize: '14px' }}
              >
                Cancel
              </Button>
              <Button onClick={handleSave} className="gap-2" style={{ fontSize: '14px' }}>
                <Save className="w-4 h-4" />
                Add Criterion
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      ) : (
        <Sheet open={open} onOpenChange={handleClose}>
          <SheetContent side="right" className="w-full sm:max-w-2xl p-0 flex flex-col gap-0">
            <SheetHeader className="px-6 py-4 border-b">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <SheetTitle className="flex items-center gap-2" style={{ fontSize: '18px' }}>
                    <Plus className="w-5 h-5" />
                    Add New Criterion
                  </SheetTitle>
                  <SheetDescription style={{ fontSize: '14px' }}>
                    Highlight text from the protocol document and create a new inclusion or
                    exclusion criterion
                  </SheetDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsPopout(true)}
                  className="gap-2"
                  style={{ fontSize: '14px' }}
                >
                  <Maximize2 className="w-4 h-4" />
                  Pop Out
                </Button>
              </div>
            </SheetHeader>

            {panelContent}

            {/* Footer Actions */}
            <div className="px-6 py-4 border-t bg-gray-50 flex gap-3 justify-end">
              <Button
                variant="outline"
                onClick={() => handleClose(false)}
                style={{ fontSize: '14px' }}
              >
                Cancel
              </Button>
              <Button onClick={handleSave} className="gap-2" style={{ fontSize: '14px' }}>
                <Save className="w-4 h-4" />
                Add Criterion
              </Button>
            </div>
          </SheetContent>
        </Sheet>
      )}

      {/* Field Mapping Popup */}
      <FieldMappingPopup
        open={showMappingPopup}
        onOpenChange={setShowMappingPopup}
        selectedText={currentHighlightText}
        onSave={handleSaveMapping}
        suggestedField={suggestedField}
        suggestedValue={suggestedValue}
      />
    </>
  );
}
