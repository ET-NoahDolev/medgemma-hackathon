import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
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
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertCircle,
  Trash2,
  Save,
  X,
  Edit2,
  FileText,
  Info,
  Highlighter,
  Link2,
  RotateCcw,
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

interface CriteriaEditPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  criterion: {
    id: string;
    type: 'inclusion' | 'exclusion';
    text: string;
    status: string;
    confidence?: number;
    sourceText?: string; // Original protocol text
    sourceDocumentId?: string;
  };
  sourceDocuments?: SourceDocument[];
  onSave: (updates: {
    text: string;
    type: 'inclusion' | 'exclusion' | 'not-applicable';
    sourceText: string;
    sourceDocumentId: string;
    fieldMappings?: FieldMapping[];
    rationale: string;
  }) => void;
  onDelete?: (rationale: string) => void;
}

// Default mock source document
const defaultSourceDocuments: SourceDocument[] = [
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
];

export function CriteriaEditPanel({
  open,
  onOpenChange,
  criterion,
  sourceDocuments = defaultSourceDocuments,
  onSave,
  onDelete,
}: CriteriaEditPanelProps) {
  // Store original values for comparison
  const originalText = criterion.text;
  const originalType = criterion.type;
  const originalSourceText = criterion.sourceText || '';

  const [editedType, setEditedType] = useState<'inclusion' | 'exclusion' | 'not-applicable'>(
    criterion.type
  );
  const [rationale, setRationale] = useState('');
  const [selectedText, setSelectedText] = useState(criterion.sourceText || '');
  const [selectedDocumentId, setSelectedDocumentId] = useState<string>(
    criterion.sourceDocumentId || sourceDocuments[0]?.id || ''
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
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteRationale, setDeleteRationale] = useState('');
  const prevCriterionIdRef = useRef(criterion.id);

  const currentDocument =
    sourceDocuments.find(doc => doc.id === selectedDocumentId) || sourceDocuments[0];

  // Reset form when criterion changes
  useEffect(() => {
    // Only reset when criterion.id actually changes
    if (criterion.id !== prevCriterionIdRef.current) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Reset form state when criterion changes
      setEditedType(criterion.type);
      setSelectedText(criterion.sourceText || '');
      setSelectedDocumentId(criterion.sourceDocumentId || sourceDocuments[0]?.id || '');
      setRationale('');
      setShowDeleteConfirm(false);
      setDeleteRationale('');
      setFieldMappings([]);
      setHighlightedRanges([]);
      prevCriterionIdRef.current = criterion.id;
    }
  }, [
    criterion.id,
    criterion.type,
    criterion.sourceText,
    criterion.sourceDocumentId,
    sourceDocuments,
  ]);

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

  const handleClearHighlights = useCallback(() => {
    setHighlightedRanges([]);
    setSelectedText('');
    setSuggestedField('');
    setSuggestedValue('');
  }, []);

  const handleSaveMapping = (mapping: {
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
  };

  const handleRemoveMapping = useCallback((index: number) => {
    setFieldMappings(prev => prev.filter((_, i) => i !== index));
    toast.success('Mapping removed');
  }, []);

  const handleClose = useCallback((isOpen: boolean) => {
    if (!isOpen) {
      // Reset form when closing
      setEditedType(criterion.type);
      setSelectedText(criterion.sourceText || '');
      setRationale('');
      setShowDeleteConfirm(false);
      setDeleteRationale('');
      setFieldMappings([]);
      setHighlightedRanges([]);
      setIsPopout(false);
      setIsFullscreen(false);
    }
    onOpenChange(isOpen);
  }, [criterion.type, criterion.sourceText, onOpenChange]);

  const generateCriterionText = () => {
    if (fieldMappings.length === 0) {
      return originalText; // Fallback to original if no mappings
    }

    // Generate text from mappings
    const mappingTexts = fieldMappings.map(m => {
      const fieldLabel = m.targetField.replace(/_/g, ' ').toLowerCase();
      const relation = m.relation || '=';
      const value =
        m.targetValueMin && m.targetValueMax
          ? `${m.targetValueMin} to ${m.targetValueMax}${m.targetValueUnit || ''}`
          : `${m.targetValue}${m.targetValueUnit || ''}`;

      return `${fieldLabel} ${relation} ${value}`;
    });

    return mappingTexts.join(' AND ');
  };

  const handleSave = () => {
    if (fieldMappings.length === 0) {
      toast.error('Please create at least one field mapping');
      return;
    }

    if (!rationale.trim()) {
      toast.error('Please provide a rationale for changes');
      return;
    }

    const generatedText = generateCriterionText();

    onSave({
      text: generatedText,
      type: editedType,
      sourceText: selectedText,
      sourceDocumentId: selectedDocumentId,
      fieldMappings: fieldMappings.length > 0 ? fieldMappings : undefined,
      rationale,
    });

    toast.success('Criterion updated successfully', {
      description:
        fieldMappings.length > 0 ? `With ${fieldMappings.length} field mapping(s)` : undefined,
    });

    handleClose(false);
  };

  const handleDelete = useCallback(() => {
    if (!deleteRationale.trim() || !onDelete) {
      return;
    }

    onDelete(deleteRationale);
    handleClose(false);
    toast.success('Criterion deleted');
  }, [deleteRationale, onDelete, handleClose]);

  const handleCancel = () => {
    handleClose(false);
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
          {/* Current Status Alert */}
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription style={{ fontSize: '12px' }}>
              Current status:{' '}
              <Badge variant="outline" className="ml-1" style={{ fontSize: '11px' }}>
                {criterion.status}
              </Badge>
              {criterion.confidence && (
                <span className="ml-2">
                  AI Confidence: {Math.round(criterion.confidence * 100)}%
                </span>
              )}
            </AlertDescription>
          </Alert>

          {/* Original Criterion Display */}
          <div className="space-y-3">
            <Label style={{ fontSize: '14px' }}>Original Criterion</Label>
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-2">
              <div className="flex items-start gap-2">
                <Badge
                  variant="outline"
                  className={
                    originalType === 'inclusion'
                      ? 'bg-green-50 text-green-700 border-green-300'
                      : 'bg-red-50 text-red-700 border-red-300'
                  }
                  style={{ fontSize: '11px' }}
                >
                  {originalType === 'inclusion' ? 'Inclusion' : 'Exclusion'} {criterion.id}
                </Badge>
              </div>
              <p className="text-gray-700 leading-relaxed" style={{ fontSize: '14px' }}>
                {originalText}
              </p>
              {originalSourceText && (
                <>
                  <Separator className="my-2" />
                  <div className="space-y-1">
                    <span className="text-gray-500" style={{ fontSize: '12px' }}>
                      Source Evidence:
                    </span>
                    <p className="text-gray-600 italic" style={{ fontSize: '12px' }}>
                      &quot;{originalSourceText}&quot;
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>

          <Separator />

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
            <Label style={{ fontSize: '14px' }}>
              Protocol Content - Select Text to Update Evidence
            </Label>

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
                    variant="ghost"
                    onClick={handleClearHighlights}
                    className="gap-1 bg-white shadow-sm"
                    style={{ fontSize: '12px' }}
                  >
                    <X className="w-3 h-3" />
                    Clear Highlights
                  </Button>
                </div>
              )}
            </div>

            <div className="p-3 bg-teal-50 border border-teal-200 rounded-lg">
              <p className="text-teal-900 flex items-start gap-2" style={{ fontSize: '14px' }}>
                <Highlighter className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>
                  <strong>Select text</strong> from the document above to update source evidence. A
                  popup will appear to let you map the text to EDC fields for automated validation.
                </span>
              </p>
            </div>
          </div>

          {/* Highlighted Text Preview */}
          {selectedText && selectedText !== originalSourceText && (
            <>
              <Separator />
              <div className="space-y-3">
                <Label style={{ fontSize: '14px' }}>Updated Source Text</Label>
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-gray-900 italic" style={{ fontSize: '14px' }}>
                    &quot;{selectedText}&quot;
                  </p>
                </div>
                {originalSourceText && (
                  <p
                    className="text-orange-600 flex items-center gap-1"
                    style={{ fontSize: '12px' }}
                  >
                    <AlertCircle className="w-3 h-3" />
                    Source evidence has been updated
                  </p>
                )}
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
                    Will be updated on save
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
              value={editedType}
              onValueChange={value =>
                setEditedType(value as 'inclusion' | 'exclusion' | 'not-applicable')
              }
            >
              <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                <RadioGroupItem value="inclusion" id="edit-inclusion" />
                <Label htmlFor="edit-inclusion" className="flex-1 cursor-pointer">
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
                <RadioGroupItem value="exclusion" id="edit-exclusion" />
                <Label htmlFor="edit-exclusion" className="flex-1 cursor-pointer">
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
              <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                <RadioGroupItem value="not-applicable" id="edit-not-applicable" />
                <Label htmlFor="edit-not-applicable" className="flex-1 cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Badge
                      className="bg-gray-100 text-gray-700 border-gray-300"
                      style={{ fontSize: '12px' }}
                    >
                      Not Applicable
                    </Badge>
                    <span className="text-gray-600" style={{ fontSize: '14px' }}>
                      Mark as not applicable (will be excluded from screening)
                    </span>
                  </div>
                </Label>
              </div>
            </RadioGroup>
            {editedType === 'not-applicable' && (
              <p className="text-orange-600 flex items-center gap-1" style={{ fontSize: '12px' }}>
                <AlertCircle className="w-3 h-3" />
                This criterion will be marked as not applicable and excluded from screening
              </p>
            )}
            {editedType !== originalType && editedType !== 'not-applicable' && (
              <p className="text-orange-600 flex items-center gap-1" style={{ fontSize: '12px' }}>
                <AlertCircle className="w-3 h-3" />
                Type has been changed from {originalType}
              </p>
            )}
          </div>

          {/* Current Mappings Summary */}
          {fieldMappings.length === 0 && (
            <>
              <div className="p-8 border-2 border-dashed border-gray-200 rounded-lg text-center">
                <Link2 className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-gray-900" style={{ fontSize: '14px', fontWeight: 600 }}>
                  No Field Mappings Defined
                </p>
                <p className="text-gray-500 mt-1" style={{ fontSize: '12px' }}>
                  Select text from the protocol document above to create field mappings that define
                  this criterion
                </p>
                <p className="text-gray-500 mt-2" style={{ fontSize: '12px' }}>
                  Criterion will be validated based on the field mappings you create
                </p>
              </div>
              <Separator />
            </>
          )}

          {fieldMappings.length > 0 && (
            <>
              <Separator />
            </>
          )}

          {/* Rationale */}
          <div className="space-y-3">
            <Label htmlFor="edit-rationale" style={{ fontSize: '14px' }}>
              Change Rationale <span className="text-red-500">*</span>
            </Label>
            <Textarea
              id="edit-rationale"
              value={rationale}
              onChange={e => setRationale(e.target.value)}
              rows={3}
              className="resize-none"
              placeholder="Explain why you are making these changes..."
              style={{ fontSize: '14px' }}
            />
            <p className="text-gray-500" style={{ fontSize: '12px' }}>
              Required for audit trail. Be specific about what changed and why.
            </p>
          </div>

          {/* Delete Section */}
          {onDelete && (
            <>
              <Separator />
              <div className="space-y-3">
                <h3 className="text-red-600" style={{ fontSize: '14px', fontWeight: 600 }}>
                  Danger Zone
                </h3>

                {!showDeleteConfirm ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowDeleteConfirm(true)}
                    className="text-red-600 border-red-200 hover:bg-red-50 gap-2"
                    style={{ fontSize: '14px' }}
                  >
                    <Trash2 className="w-3 h-3" />
                    Remove Criterion Entirely
                  </Button>
                ) : (
                  <div className="p-4 border border-red-200 bg-red-50 rounded-lg space-y-3">
                    <Alert className="border-red-300">
                      <AlertCircle className="h-4 w-4 text-red-600" />
                      <AlertDescription className="text-red-800" style={{ fontSize: '12px' }}>
                        This will permanently remove this criterion from the protocol. This action
                        will be logged to the audit trail.
                      </AlertDescription>
                    </Alert>

                    <div className="space-y-2">
                      <Label htmlFor="delete-rationale" style={{ fontSize: '14px' }}>
                        Deletion Rationale <span className="text-red-500">*</span>
                      </Label>
                      <Textarea
                        id="delete-rationale"
                        value={deleteRationale}
                        onChange={e => setDeleteRationale(e.target.value)}
                        rows={2}
                        className="resize-none"
                        placeholder="Explain why this criterion should be removed..."
                        style={{ fontSize: '14px' }}
                      />
                    </div>

                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        onClick={handleDelete}
                        disabled={!deleteRationale.trim()}
                        className="gap-1"
                        style={{ fontSize: '14px' }}
                      >
                        <Trash2 className="w-3 h-3" />
                        Confirm Deletion
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setShowDeleteConfirm(false);
                          setDeleteRationale('');
                        }}
                        style={{ fontSize: '14px' }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
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
      editedType,
      setEditedType,
      selectedText,
      handleTextSelection,
      handleClearHighlights,
      highlightedRanges,
      fieldMappings,
      handleRemoveMapping,
      rationale,
      setRationale,
      showDeleteConfirm,
      deleteRationale,
      setDeleteRationale,
      handleDelete,
      criterion,
      onDelete,
      originalText,
      originalSourceText,
      originalType,
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
                    <Edit2 className="w-5 h-5" />
                    Edit Criterion {criterion.type === 'inclusion' ? 'I' : 'E'}
                    {criterion.id}
                  </DialogTitle>
                  <DialogDescription style={{ fontSize: '14px' }}>
                    Modify criterion text, type, field mappings, or remove this criterion entirely.
                    All changes are logged to the audit trail.
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
            <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-between gap-3">
              <p className="text-gray-600 flex items-center gap-1" style={{ fontSize: '12px' }}>
                <RotateCcw className="w-3 h-3" />
                Changes will be logged to audit trail
              </p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleCancel} style={{ fontSize: '14px' }}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={!rationale.trim() || fieldMappings.length === 0}
                  className="gap-2 bg-teal-600 hover:bg-teal-700"
                  style={{ fontSize: '14px' }}
                >
                  <Save className="w-4 h-4" />
                  Save Changes
                </Button>
              </div>
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
                    <Edit2 className="w-5 h-5" />
                    Edit Criterion {criterion.type === 'inclusion' ? 'I' : 'E'}
                    {criterion.id}
                  </SheetTitle>
                  <SheetDescription style={{ fontSize: '14px' }}>
                    Modify criterion text, type, field mappings, or remove this criterion entirely.
                    All changes are logged to the audit trail.
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
            <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-between gap-3">
              <p className="text-gray-600 flex items-center gap-1" style={{ fontSize: '12px' }}>
                <RotateCcw className="w-3 h-3" />
                Changes will be logged to audit trail
              </p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleCancel} style={{ fontSize: '14px' }}>
                  Cancel
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={!rationale.trim() || fieldMappings.length === 0}
                  className="gap-2 bg-teal-600 hover:bg-teal-700"
                  style={{ fontSize: '14px' }}
                >
                  <Save className="w-4 h-4" />
                  Save Changes
                </Button>
              </div>
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
