import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ArrowRight, ArrowLeft, Check, AlertTriangle, Plus, Sparkles } from 'lucide-react';

interface FieldMapping {
  id: string;
  emrTerm: string;
  targetField: string;
  relation: string;
  targetValue: string;
  patientCount: number;
  mappingType: 'field-value';
}

interface EditFieldMappingModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mapping: FieldMapping;
  onSave: (data: {
    newField: string;
    newRelation: string;
    newValue: string;
    rationale: string;
  }) => void;
}

interface FieldOption {
  value: string;
  label: string;
  system: string;
}

const existingFields: FieldOption[] = [
  { value: 'demographics.age', label: 'Age', system: 'Demographics' },
  { value: 'demographics.gender', label: 'Gender', system: 'Demographics' },
  { value: 'vitals.blood_pressure', label: 'Blood Pressure', system: 'Vitals' },
  { value: 'vitals.heart_rate', label: 'Heart Rate', system: 'Vitals' },
  { value: 'vitals.temperature', label: 'Temperature', system: 'Vitals' },
  { value: 'labs.hemoglobin', label: 'Hemoglobin', system: 'Labs' },
  { value: 'labs.glucose', label: 'Glucose', system: 'Labs' },
  {
    value: 'medical_history.prior_colonoscopy',
    label: 'Prior Colonoscopy',
    system: 'Medical History',
  },
  { value: 'medical_history.smoking_status', label: 'Smoking Status', system: 'Medical History' },
  { value: 'procedures.colonoscopy_date', label: 'Colonoscopy Date', system: 'Procedures' },
];

export function EditFieldMappingModal({
  open,
  onOpenChange,
  mapping,
  onSave,
}: EditFieldMappingModalProps) {
  const [step, setStep] = useState<1 | 2>(1);

  // Field selection state
  const [selectedField, setSelectedField] = useState(mapping.targetField);
  const [mappingMode, setMappingMode] = useState<'' | 'select' | 'create-field'>('');
  const [newFieldName, setNewFieldName] = useState('');
  const [newFieldCategory, setNewFieldCategory] = useState('');

  // Relation state
  const [selectedRelation, setSelectedRelation] = useState(mapping.relation);

  // Value state
  const [selectedValue, setSelectedValue] = useState('');
  const [newValue, setNewValue] = useState('');
  const [rangeMin, setRangeMin] = useState('');
  const [rangeMax, setRangeMax] = useState('');
  const [durationValue, setDurationValue] = useState('');
  const [durationUnit, setDurationUnit] = useState('months');
  const [isRangeConfirmed, setIsRangeConfirmed] = useState(false);
  const [isDurationConfirmed, setIsDurationConfirmed] = useState(false);

  // Rationale state
  const [rationale, setRationale] = useState('');
  const prevOpenRef = useRef(open);

  // Initialize values when modal opens
  useEffect(() => {
    // Only reset when transitioning from closed to open
    if (open && !prevOpenRef.current) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Reset state when modal opens
      setStep(1);
      setSelectedField(mapping.targetField);
      setSelectedRelation(mapping.relation);
      setMappingMode('');
      setNewFieldName('');
      setNewFieldCategory('');

      // Parse the current value based on relation type
      if (mapping.relation === 'within') {
        const parts = mapping.targetValue.split(' - ');
        if (parts.length === 2) {
          setRangeMin(parts[0]);
          setRangeMax(parts[1]);
          setIsRangeConfirmed(true);
        }
        setSelectedValue('');
        setNewValue('');
      } else if (mapping.relation === 'not_in_last') {
        const match = mapping.targetValue.match(/^(\d+)\s+(\w+)$/);
        if (match) {
          setDurationValue(match[1]);
          setDurationUnit(match[2]);
          setIsDurationConfirmed(true);
        }
        setSelectedValue('');
        setNewValue('');
      } else {
        setSelectedValue(mapping.targetValue);
        setNewValue('');
        setRangeMin('');
        setRangeMax('');
        setDurationValue('');
      }

      setRationale('');
    }
    prevOpenRef.current = open;
  }, [open, mapping]);

  const selectedFieldLabel =
    existingFields.find(f => f.value === selectedField)?.label || selectedField;

  const handleFieldSelect = (value: string) => {
    setSelectedField(value);
    setMappingMode('');
  };

  const handleCreateNewField = () => {
    if (newFieldName.trim() && newFieldCategory) {
      const newFieldValue = `${newFieldCategory}.${newFieldName.toLowerCase().replace(/\s+/g, '_')}`;
      setSelectedField(newFieldValue);
      setMappingMode('');
      setNewFieldName('');
      setNewFieldCategory('');
    }
  };

  const canProceedStep1 =
    selectedField &&
    mappingMode === '' &&
    ((selectedRelation === 'within' && rangeMin && rangeMax && isRangeConfirmed) ||
      (selectedRelation === 'not_in_last' && durationValue && isDurationConfirmed) ||
      (selectedRelation !== 'within' &&
        selectedRelation !== 'not_in_last' &&
        (selectedValue || newValue)));

  const canProceedStep2 = rationale.trim().length > 0;

  const handleNext = () => {
    if (canProceedStep1) {
      setStep(2);
    }
  };

  const handleSave = () => {
    if (!canProceedStep2) return;

    let finalValue = '';
    if (selectedRelation === 'within') {
      finalValue = `${rangeMin} - ${rangeMax}`;
    } else if (selectedRelation === 'not_in_last') {
      finalValue = `${durationValue} ${durationUnit}`;
    } else {
      finalValue = selectedValue || newValue;
    }

    onSave({
      newField: selectedField,
      newRelation: selectedRelation,
      newValue: finalValue,
      rationale,
    });
  };

  const getCurrentValue = () => {
    if (selectedRelation === 'within') {
      return `${rangeMin} - ${rangeMax}`;
    } else if (selectedRelation === 'not_in_last') {
      return `${durationValue} ${durationUnit}`;
    } else {
      return selectedValue || newValue;
    }
  };

  const hasChanged =
    selectedField !== mapping.targetField ||
    selectedRelation !== mapping.relation ||
    getCurrentValue() !== mapping.targetValue;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl p-0 flex flex-col h-[85vh]" style={{ gap: 0 }}>
        <DialogTitle className="sr-only">Edit Field Mapping: {mapping.emrTerm}</DialogTitle>
        <DialogDescription className="sr-only">
          Edit the field mapping for the EMR term
        </DialogDescription>

        {/* Header */}
        <div className="px-6 py-4 border-b bg-teal-50 flex-shrink-0">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-gray-900" style={{ fontSize: '18px' }}>
              Edit Field Mapping:{' '}
              <span className="text-teal-700 font-medium">&quot;{mapping.emrTerm}&quot;</span>
            </h3>
            <Badge variant="outline" style={{ fontSize: '12px' }}>
              Step {step} of 2
            </Badge>
          </div>

          {/* Current Mapping Reference */}
          <div className="p-3 bg-white border border-gray-200 rounded-lg">
            <p className="text-gray-600 mb-2" style={{ fontSize: '12px' }}>
              Current Mapping:
            </p>
            <div className="space-y-1" style={{ fontSize: '12px' }}>
              <div className="flex" style={{ gap: 'var(--space-2)' }}>
                <span className="text-gray-600 w-20 flex-shrink-0">Field:</span>
                <span className="text-gray-900 font-medium">{mapping.targetField}</span>
              </div>
              <div className="flex" style={{ gap: 'var(--space-2)' }}>
                <span className="text-gray-600 w-20 flex-shrink-0">Relation:</span>
                <span className="text-gray-900 font-mono">{mapping.relation}</span>
              </div>
              <div className="flex" style={{ gap: 'var(--space-2)' }}>
                <span className="text-gray-600 w-20 flex-shrink-0">Value:</span>
                <span className="text-gray-900">{mapping.targetValue}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ScrollArea className="h-full">
            <div className="p-6">
              {step === 1 && (
                <div className="space-y-4">
                  {/* Target Field Section */}
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Label
                        className="flex items-center"
                        style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                      >
                        Target Field
                        <Badge variant="outline" style={{ fontSize: '11px' }}>
                          Step 1
                        </Badge>
                      </Label>
                      {selectedField && mappingMode === 'select' && (
                        <span className="text-blue-600" style={{ fontSize: '12px' }}>
                          Select a different field or create new
                        </span>
                      )}
                    </div>

                    {mappingMode === 'select' && (
                      <div className="space-y-2">
                        <Select value={selectedField} onValueChange={handleFieldSelect}>
                          <SelectTrigger style={{ fontSize: '14px' }}>
                            <SelectValue placeholder="Select existing field..." />
                          </SelectTrigger>
                          <SelectContent>
                            <div
                              className="px-2 py-1.5 font-medium text-gray-500 sticky top-0 bg-white"
                              style={{ fontSize: '11px' }}
                            >
                              Existing EDC Fields
                            </div>
                            {existingFields.map(field => (
                              <SelectItem
                                key={field.value}
                                value={field.value}
                                style={{ fontSize: '14px' }}
                              >
                                <div
                                  className="flex items-center"
                                  style={{ gap: 'var(--space-2)' }}
                                >
                                  <span>{field.label}</span>
                                  <Badge variant="outline" style={{ fontSize: '11px' }}>
                                    {field.system}
                                  </Badge>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>

                        <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                          <Separator className="flex-1" />
                          <span className="text-gray-500" style={{ fontSize: '12px' }}>
                            or
                          </span>
                          <Separator className="flex-1" />
                        </div>

                        <Button
                          variant="outline"
                          className="w-full justify-start border-dashed"
                          onClick={() => setMappingMode('create-field')}
                          style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                        >
                          <Plus className="w-4 h-4" />
                          Create New Field
                        </Button>
                      </div>
                    )}

                    {mappingMode === 'create-field' && (
                      <div className="space-y-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <div className="space-y-2">
                          <Label htmlFor="fieldCategory" style={{ fontSize: '14px' }}>
                            Field Category
                          </Label>
                          <Select value={newFieldCategory} onValueChange={setNewFieldCategory}>
                            <SelectTrigger id="fieldCategory" style={{ fontSize: '14px' }}>
                              <SelectValue placeholder="Select category..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="demographics" style={{ fontSize: '14px' }}>
                                Demographics
                              </SelectItem>
                              <SelectItem value="vitals" style={{ fontSize: '14px' }}>
                                Vitals
                              </SelectItem>
                              <SelectItem value="labs" style={{ fontSize: '14px' }}>
                                Labs
                              </SelectItem>
                              <SelectItem value="medical_history" style={{ fontSize: '14px' }}>
                                Medical History
                              </SelectItem>
                              <SelectItem value="procedures" style={{ fontSize: '14px' }}>
                                Procedures
                              </SelectItem>
                              <SelectItem value="eligibility" style={{ fontSize: '14px' }}>
                                Eligibility
                              </SelectItem>
                              <SelectItem value="custom" style={{ fontSize: '14px' }}>
                                Custom
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label htmlFor="fieldName" style={{ fontSize: '14px' }}>
                            Field Name
                          </Label>
                          <Input
                            id="fieldName"
                            value={newFieldName}
                            onChange={e => setNewFieldName(e.target.value)}
                            placeholder="e.g., Prior Colonoscopy Status"
                            style={{ fontSize: '14px' }}
                          />
                        </div>

                        <div className="flex" style={{ gap: 'var(--space-2)' }}>
                          <Button
                            size="sm"
                            onClick={handleCreateNewField}
                            disabled={!newFieldName.trim() || !newFieldCategory}
                            className="bg-teal-600 hover:bg-teal-700"
                            style={{ fontSize: '14px', gap: 'var(--space-1)' }}
                          >
                            <Check className="w-3 h-3" />
                            Create
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              setMappingMode('');
                              setNewFieldName('');
                              setNewFieldCategory('');
                            }}
                            style={{ fontSize: '14px' }}
                          >
                            Cancel
                          </Button>
                        </div>
                      </div>
                    )}

                    {selectedField && mappingMode === '' && (
                      <button
                        onClick={() => setMappingMode('select')}
                        className="w-full p-3 bg-teal-50 border-2 border-teal-200 rounded-lg hover:border-teal-400 hover:bg-teal-100 transition-colors text-left cursor-pointer"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                            <Check className="w-4 h-4 text-teal-600" />
                            <span
                              className="font-medium text-gray-900"
                              style={{ fontSize: '14px' }}
                            >
                              {selectedFieldLabel}
                            </span>
                            {!existingFields.find(f => f.value === selectedField) && (
                              <Badge
                                className="bg-blue-100 text-blue-700 border-blue-300"
                                style={{ fontSize: '11px' }}
                              >
                                New Field
                              </Badge>
                            )}
                          </div>
                          <span className="text-teal-600" style={{ fontSize: '12px' }}>
                            Click to change
                          </span>
                        </div>
                      </button>
                    )}
                  </div>

                  <Separator />

                  {/* Relation Selector */}
                  {mappingMode === '' && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label
                          className="flex items-center"
                          style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                        >
                          Relation
                          <Badge variant="outline" style={{ fontSize: '11px' }}>
                            Step 2
                          </Badge>
                        </Label>
                        <span className="text-blue-600" style={{ fontSize: '12px' }}>
                          Select comparison operator
                        </span>
                      </div>

                      <Select
                        value={selectedRelation}
                        onValueChange={value => {
                          setSelectedRelation(value);
                          // Reset value states when relation changes
                          setSelectedValue('');
                          setNewValue('');
                          setRangeMin('');
                          setRangeMax('');
                          setDurationValue('');
                          setIsRangeConfirmed(false);
                          setIsDurationConfirmed(false);
                        }}
                      >
                        <SelectTrigger style={{ fontSize: '14px' }}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <div
                            className="px-2 py-1.5 font-medium text-gray-500 sticky top-0 bg-white"
                            style={{ fontSize: '11px' }}
                          >
                            Select Comparison Operator
                          </div>
                          <SelectItem value="=" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">=</span>
                              <span className="text-gray-600">Equals</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="!=" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">≠</span>
                              <span className="text-gray-600">Not equals</span>
                            </div>
                          </SelectItem>
                          <SelectItem value=">" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">{'>'}</span>
                              <span className="text-gray-600">Greater than</span>
                            </div>
                          </SelectItem>
                          <SelectItem value=">=" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">≥</span>
                              <span className="text-gray-600">Greater than or equal</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="<" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">{'<'}</span>
                              <span className="text-gray-600">Less than</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="<=" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">≤</span>
                              <span className="text-gray-600">Less than or equal</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="within" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">⊂</span>
                              <span className="text-gray-600">Within range</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="not_in_last" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">↻</span>
                              <span className="text-gray-600">Not in the last</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="contains" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">∋</span>
                              <span className="text-gray-600">Contains</span>
                            </div>
                          </SelectItem>
                          <SelectItem value="not_contains" style={{ fontSize: '14px' }}>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <span className="font-mono">∌</span>
                              <span className="text-gray-600">Does not contain</span>
                            </div>
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}

                  <Separator />

                  {/* Target Value Section */}
                  {mappingMode === '' && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label
                          className="flex items-center"
                          style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                        >
                          Target Value
                          <Badge variant="outline" style={{ fontSize: '11px' }}>
                            Step 3
                          </Badge>
                        </Label>
                      </div>

                      {/* Adaptive value input based on relation type */}
                      {selectedRelation === 'within' ? (
                        <div className="space-y-2">
                          <Label style={{ fontSize: '14px' }}>Enter range</Label>
                          <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                            <Input
                              value={rangeMin}
                              onChange={e => {
                                setRangeMin(e.target.value);
                                setIsRangeConfirmed(false);
                              }}
                              placeholder="Min (e.g., 18)"
                              style={{ fontSize: '14px' }}
                              className="flex-1"
                            />
                            <span className="text-gray-500" style={{ fontSize: '14px' }}>
                              to
                            </span>
                            <Input
                              value={rangeMax}
                              onChange={e => {
                                setRangeMax(e.target.value);
                                setIsRangeConfirmed(false);
                              }}
                              placeholder="Max (e.g., 65)"
                              style={{ fontSize: '14px' }}
                              className="flex-1"
                            />
                          </div>
                          {rangeMin && rangeMax && !isRangeConfirmed && (
                            <Button
                              size="sm"
                              onClick={() => setIsRangeConfirmed(true)}
                              className="bg-teal-600 hover:bg-teal-700"
                              style={{ fontSize: '14px', gap: 'var(--space-1)' }}
                            >
                              <Check className="w-3 h-3" />
                              Confirm Range
                            </Button>
                          )}
                          {rangeMin && rangeMax && isRangeConfirmed && (
                            <div className="p-3 bg-teal-50 border-2 border-teal-200 rounded-lg">
                              <div className="flex items-center justify-between">
                                <div
                                  className="flex items-center"
                                  style={{ gap: 'var(--space-2)' }}
                                >
                                  <Check className="w-4 h-4 text-teal-600" />
                                  <span
                                    className="font-medium text-gray-900"
                                    style={{ fontSize: '14px' }}
                                  >
                                    {rangeMin} - {rangeMax}
                                  </span>
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setIsRangeConfirmed(false)}
                                  style={{ fontSize: '12px' }}
                                >
                                  Edit
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : selectedRelation === 'not_in_last' ? (
                        <div className="space-y-2">
                          <Label style={{ fontSize: '14px' }}>Enter duration</Label>
                          <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                            <Input
                              value={durationValue}
                              onChange={e => {
                                setDurationValue(e.target.value);
                                setIsDurationConfirmed(false);
                              }}
                              placeholder="e.g., 6"
                              type="number"
                              style={{ fontSize: '14px' }}
                              className="flex-1"
                            />
                            <Select value={durationUnit} onValueChange={setDurationUnit}>
                              <SelectTrigger className="w-32" style={{ fontSize: '14px' }}>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="days" style={{ fontSize: '14px' }}>
                                  Days
                                </SelectItem>
                                <SelectItem value="weeks" style={{ fontSize: '14px' }}>
                                  Weeks
                                </SelectItem>
                                <SelectItem value="months" style={{ fontSize: '14px' }}>
                                  Months
                                </SelectItem>
                                <SelectItem value="years" style={{ fontSize: '14px' }}>
                                  Years
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          {durationValue && !isDurationConfirmed && (
                            <Button
                              size="sm"
                              onClick={() => setIsDurationConfirmed(true)}
                              className="bg-teal-600 hover:bg-teal-700"
                              style={{ fontSize: '14px', gap: 'var(--space-1)' }}
                            >
                              <Check className="w-3 h-3" />
                              Confirm Duration
                            </Button>
                          )}
                          {durationValue && isDurationConfirmed && (
                            <div className="p-3 bg-teal-50 border-2 border-teal-200 rounded-lg">
                              <div className="flex items-center justify-between">
                                <div
                                  className="flex items-center"
                                  style={{ gap: 'var(--space-2)' }}
                                >
                                  <Check className="w-4 h-4 text-teal-600" />
                                  <span
                                    className="font-medium text-gray-900"
                                    style={{ fontSize: '14px' }}
                                  >
                                    {durationValue} {durationUnit}
                                  </span>
                                </div>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setIsDurationConfirmed(false)}
                                  style={{ fontSize: '12px' }}
                                >
                                  Edit
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <Label htmlFor="targetValue" style={{ fontSize: '14px' }}>
                            Enter value
                          </Label>
                          <Input
                            id="targetValue"
                            value={selectedValue || newValue}
                            onChange={e => {
                              setSelectedValue('');
                              setNewValue(e.target.value);
                            }}
                            placeholder="e.g., Yes, No, or specific value..."
                            style={{ fontSize: '14px' }}
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {step === 2 && (
                <div className="space-y-4">
                  {/* Step 2: Preview & Rationale */}
                  <div className="space-y-3">
                    <Label style={{ fontSize: '14px' }}>Mapping Change Preview</Label>

                    <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-3">
                      {/* Current */}
                      <div>
                        <p className="text-gray-600 mb-2" style={{ fontSize: '12px' }}>
                          Current:
                        </p>
                        <div className="space-y-1" style={{ fontSize: '12px' }}>
                          <div className="flex" style={{ gap: 'var(--space-2)' }}>
                            <span className="text-gray-600 w-20 flex-shrink-0">Field:</span>
                            <span className="text-gray-900 font-medium">{mapping.targetField}</span>
                          </div>
                          <div className="flex" style={{ gap: 'var(--space-2)' }}>
                            <span className="text-gray-600 w-20 flex-shrink-0">Relation:</span>
                            <span className="text-gray-900 font-mono">{mapping.relation}</span>
                          </div>
                          <div className="flex" style={{ gap: 'var(--space-2)' }}>
                            <span className="text-gray-600 w-20 flex-shrink-0">Value:</span>
                            <span className="text-gray-900">{mapping.targetValue}</span>
                          </div>
                        </div>
                      </div>

                      <ArrowRight className="w-5 h-5 text-gray-400 mx-auto" />

                      {/* New */}
                      <div>
                        <p className="text-gray-600 mb-2" style={{ fontSize: '12px' }}>
                          New:
                        </p>
                        <div className="space-y-1" style={{ fontSize: '12px' }}>
                          <div className="flex" style={{ gap: 'var(--space-2)' }}>
                            <span className="text-gray-600 w-20 flex-shrink-0">Field:</span>
                            <span className="text-teal-700 font-medium">{selectedFieldLabel}</span>
                          </div>
                          <div className="flex" style={{ gap: 'var(--space-2)' }}>
                            <span className="text-gray-600 w-20 flex-shrink-0">Relation:</span>
                            <span className="text-teal-700 font-mono">{selectedRelation}</span>
                          </div>
                          <div className="flex" style={{ gap: 'var(--space-2)' }}>
                            <span className="text-gray-600 w-20 flex-shrink-0">Value:</span>
                            <span className="text-teal-700">{getCurrentValue()}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {!hasChanged && (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <p
                          className="text-blue-900 flex items-start"
                          style={{ fontSize: '12px', gap: 'var(--space-2)' }}
                        >
                          <Sparkles className="w-4 h-4 mt-0.5 flex-shrink-0" />
                          <span>No changes detected. The mapping remains the same.</span>
                        </p>
                      </div>
                    )}
                  </div>

                  <Separator />

                  <div className="space-y-3">
                    <Label
                      htmlFor="rationale"
                      className="flex items-center"
                      style={{ fontSize: '14px', gap: 'var(--space-2)' }}
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

                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                    <p
                      className="text-amber-900 flex items-start"
                      style={{ fontSize: '12px', gap: 'var(--space-2)' }}
                    >
                      <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                      <span>
                        <strong>Impact:</strong> Will affect {mapping.patientCount} patients using
                        this EMR term
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
                style={{ fontSize: '14px', gap: 'var(--space-2)' }}
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
            )}
          </div>

          <div className="flex" style={{ gap: 'var(--space-2)' }}>
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
                disabled={!canProceedStep1}
                className="bg-teal-600 hover:bg-teal-700"
                style={{ fontSize: '14px', gap: 'var(--space-2)' }}
              >
                Next
                <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button
                onClick={handleSave}
                disabled={!canProceedStep2}
                className="bg-teal-600 hover:bg-teal-700"
                style={{ fontSize: '14px', gap: 'var(--space-2)' }}
              >
                <Check className="w-4 h-4" />
                Save Changes
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
