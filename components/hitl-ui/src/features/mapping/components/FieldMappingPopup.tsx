import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Link2, Plus, Check, Sparkles } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface FieldMapping {
  targetField: string;
  relation: string;
  targetValue: string;
  targetValueMin?: string; // For range operations like "within"
  targetValueMax?: string; // For range operations like "within"
  targetValueUnit?: string; // For temporal operations like "not_in_last"
  isNewField: boolean;
  isNewValue: boolean;
}

interface FieldMappingPopupProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedText: string;
  onSave: (mapping: FieldMapping) => void;
  position?: { x: number; y: number };
  suggestedField?: string;
  suggestedValue?: string;
}

// Mock existing fields - in production, these would come from EDC system
const existingFields = [
  { value: 'demographics.age', label: 'Demographics - Age', system: 'EDC' },
  { value: 'demographics.gender', label: 'Demographics - Gender', system: 'EDC' },
  { value: 'demographics.race', label: 'Demographics - Race', system: 'EDC' },
  { value: 'vitals.blood_pressure_systolic', label: 'Vitals - BP Systolic', system: 'EDC' },
  { value: 'vitals.blood_pressure_diastolic', label: 'Vitals - BP Diastolic', system: 'EDC' },
  { value: 'vitals.heart_rate', label: 'Vitals - Heart Rate', system: 'EDC' },
  { value: 'labs.hemoglobin', label: 'Labs - Hemoglobin', system: 'EDC' },
  { value: 'labs.creatinine', label: 'Labs - Creatinine', system: 'EDC' },
  { value: 'medical_history.cancer', label: 'Medical History - Cancer', system: 'EDC' },
  { value: 'medical_history.ibd', label: 'Medical History - IBD', system: 'EDC' },
  { value: 'procedures.colonoscopy_date', label: 'Procedures - Last Colonoscopy', system: 'EDC' },
  { value: 'eligibility.inclusion_01', label: 'Eligibility - Inclusion 01', system: 'EDC' },
  { value: 'eligibility.exclusion_01', label: 'Eligibility - Exclusion 01', system: 'EDC' },
];

// Mock value suggestions based on field type
const getValueSuggestions = (field: string): string[] => {
  if (field.includes('age')) return ['45', '50', '55', '60', '65', '70', '75'];
  if (field.includes('gender')) return ['Male', 'Female', 'Other'];
  if (field.includes('blood_pressure')) return ['120', '130', '140', '150', '160'];
  if (field.includes('cancer') || field.includes('ibd')) return ['Yes', 'No', 'Unknown'];
  return [];
};

export function FieldMappingPopup({
  open,
  onOpenChange,
  selectedText,
  onSave,
  position: _position,
  suggestedField = '',
  suggestedValue = '',
}: FieldMappingPopupProps) {
  const [mappingMode, setMappingMode] = useState<'select' | 'create-field' | 'edit-value' | ''>('');
  const [selectedField, setSelectedField] = useState<string>('');
  const [newFieldName, setNewFieldName] = useState('');
  const [newFieldCategory, setNewFieldCategory] = useState('');
  const [selectedRelation, setSelectedRelation] = useState<string>('=');
  const [selectedValue, setSelectedValue] = useState<string>('');
  const [newValue, setNewValue] = useState('');
  const [rangeMin, setRangeMin] = useState('');
  const [rangeMax, setRangeMax] = useState('');
  const [isRangeConfirmed, setIsRangeConfirmed] = useState(false);
  const [durationValue, setDurationValue] = useState('');
  const [durationUnit, setDurationUnit] = useState<string>('months');
  const [isDurationConfirmed, setIsDurationConfirmed] = useState(false);
  const [showValueSection, setShowValueSection] = useState(false);
  const [isUsingSuggestion, setIsUsingSuggestion] = useState(true);

  // Apply suggestions when they change or dialog opens
  useEffect(() => {
    if (open) {
      if (suggestedField && isUsingSuggestion) {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- Apply suggestions when dialog opens
        setSelectedField(suggestedField);
        setShowValueSection(true);
        setMappingMode(''); // Show the selected field
        if (suggestedValue) {
          // Check if it's in the suggestions list
          const valueSuggestions = getValueSuggestions(suggestedField);
          if (valueSuggestions.includes(suggestedValue)) {
            setSelectedValue(suggestedValue);
            setNewValue('');
          } else {
            setSelectedValue('');
            setNewValue(suggestedValue);
          }
        }
      } else {
        // No suggestion, show selector
        setMappingMode('select');
      }
    } else {
      // Reset confirmation flags when dialog closes
      setIsRangeConfirmed(false);
      setIsDurationConfirmed(false);
    }
  }, [open, suggestedField, suggestedValue, isUsingSuggestion]);

  // Clear values when relation type changes
  useEffect(() => {
    // Clear all value fields when switching relation types
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Reset form state when relation changes
    setSelectedValue('');
    setNewValue('');
    setRangeMin('');
    setRangeMax('');
    setIsRangeConfirmed(false);
    setDurationValue('');
    setIsDurationConfirmed(false);
  }, [selectedRelation]);

  const handleFieldSelect = (value: string) => {
    setSelectedField(value);
    setShowValueSection(true);
    setMappingMode(''); // Clear mode to show the field as selected
    setIsUsingSuggestion(false);
  };

  const handleCreateNewField = () => {
    if (!newFieldName.trim() || !newFieldCategory.trim()) {
      return;
    }
    const fieldKey = `${newFieldCategory}.${newFieldName.toLowerCase().replace(/\s+/g, '_')}`;
    setSelectedField(fieldKey);
    setShowValueSection(true);
    setMappingMode(''); // Clear mode to show the field as selected
    setNewFieldName('');
    setNewFieldCategory('');
  };

  const handleSave = () => {
    if (!selectedField) {
      return;
    }

    const isNewField = !existingFields.find(f => f.value === selectedField);
    const valueSuggestions = getValueSuggestions(selectedField);

    let finalValue = selectedValue || newValue;
    let valueMin: string | undefined;
    let valueMax: string | undefined;
    let valueUnit: string | undefined;

    // Handle different value types based on relation
    if (selectedRelation === 'within') {
      finalValue = `${rangeMin} - ${rangeMax}`;
      valueMin = rangeMin;
      valueMax = rangeMax;
    } else if (selectedRelation === 'not_in_last') {
      finalValue = `${durationValue} ${durationUnit}`;
      valueUnit = durationUnit;
    } else {
      finalValue = selectedValue || newValue;
    }

    const isNewValue = selectedValue ? !valueSuggestions.includes(selectedValue) : !!newValue;

    onSave({
      targetField: selectedField,
      relation: selectedRelation,
      targetValue: finalValue,
      targetValueMin: valueMin,
      targetValueMax: valueMax,
      targetValueUnit: valueUnit,
      isNewField,
      isNewValue,
    });

    // Reset form
    handleReset();
    onOpenChange(false);
  };

  const handleReset = () => {
    setMappingMode('');
    setSelectedField('');
    setNewFieldName('');
    setNewFieldCategory('');
    setSelectedRelation('=');
    setSelectedValue('');
    setNewValue('');
    setRangeMin('');
    setRangeMax('');
    setDurationValue('');
    setDurationUnit('months');
    setShowValueSection(false);
    setIsUsingSuggestion(true);
  };

  const valueSuggestions = selectedField ? getValueSuggestions(selectedField) : [];
  const selectedFieldLabel =
    existingFields.find(f => f.value === selectedField)?.label || selectedField;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-lg p-0 !flex flex-col h-[90vh] max-h-[90vh]"
        style={{ gap: 0 }}
      >
        {/* Visually hidden but accessible title and description */}
        <DialogTitle className="sr-only">Map Selected Text to EDC Field</DialogTitle>
        <DialogDescription className="sr-only">
          Create a mapping between the selected protocol text and an EDC target field with its
          value. This enables automated validation of patient eligibility criteria.
        </DialogDescription>

        {/* Header */}
        <div className="px-4 py-3 border-b bg-teal-50 flex-shrink-0">
          <div className="flex items-start" style={{ gap: 'var(--space-3)' }}>
            <div className="p-1.5 bg-teal-100 rounded">
              <Link2 className="w-4 h-4 text-teal-700" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center mb-1" style={{ gap: 'var(--space-2)' }}>
                <h3 className="font-medium text-gray-900" style={{ fontSize: '16px' }}>
                  Map Selected Text to Field
                </h3>
                {suggestedField && (
                  <Badge
                    className="bg-orange-100 text-orange-700 border-orange-300"
                    style={{ fontSize: '11px', gap: 'var(--space-1)' }}
                  >
                    <Sparkles className="w-3 h-3" />
                    AI Suggested
                  </Badge>
                )}
              </div>
              <div className="p-2 bg-white rounded border border-gray-200">
                <p className="text-gray-900 line-clamp-2" style={{ fontSize: '14px' }}>
                  &quot;{selectedText}&quot;
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Scrollable Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ScrollArea className="h-full">
            <div className="p-4 pb-8">
              {/* AI Suggestion Notice */}
              {suggestedField && selectedField === suggestedField && isUsingSuggestion && (
                <div
                  className="p-3 bg-orange-50 border border-orange-200 rounded-lg flex items-start mb-4"
                  style={{ gap: 'var(--space-2)' }}
                >
                  <Sparkles className="w-4 h-4 text-orange-600 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-orange-900" style={{ fontSize: '14px' }}>
                      <strong>AI analyzed the selected text</strong> and suggested a field mapping.
                      You can modify any of these suggestions below.
                    </p>
                  </div>
                </div>
              )}

              {/* Target Field Section */}
              <div className="space-y-3 mb-4">
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
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
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
                  <>
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
                            if (selectedField) {
                              // If we had a selected field, go back to showing it
                              setMappingMode('select');
                            } else {
                              // Otherwise just clear the create mode
                              setMappingMode('select');
                            }
                            setNewFieldName('');
                            setNewFieldCategory('');
                          }}
                          style={{ fontSize: '14px' }}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>

                    {selectedField && (
                      <div
                        className="p-2 bg-blue-50 border border-blue-200 rounded"
                        style={{ fontSize: '12px' }}
                      >
                        <p className="text-blue-900">
                          Creating a new field will replace your current selection:{' '}
                          <strong>{selectedFieldLabel}</strong>
                        </p>
                      </div>
                    )}
                  </>
                )}

                {selectedField && mappingMode === '' && (
                  <button
                    onClick={() => setMappingMode('select')}
                    className="w-full p-3 bg-teal-50 border-2 border-teal-200 rounded-lg hover:border-teal-400 hover:bg-teal-100 transition-colors text-left cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                        <Check className="w-4 h-4 text-teal-600" />
                        <span className="font-medium text-gray-900" style={{ fontSize: '14px' }}>
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
                        {selectedField === suggestedField && isUsingSuggestion && (
                          <Badge
                            className="bg-orange-100 text-orange-700 border-orange-300"
                            style={{ fontSize: '11px', gap: 'var(--space-1)' }}
                          >
                            <Sparkles className="w-2.5 h-2.5" />
                            Suggested
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

              {/* Relation Selector */}
              {showValueSection && mappingMode === '' && (
                <>
                  <Separator className="mb-4" />
                  <div className="space-y-3 mb-4">
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
                        Click to select operator
                      </span>
                    </div>

                    <Select value={selectedRelation} onValueChange={setSelectedRelation}>
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
                            <span className="font-mono">&gt;</span>
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
                            <span className="font-mono">&lt;</span>
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

                    {/* Helper text based on selected relation */}
                    <div
                      className="p-2 bg-blue-50 border border-blue-200 rounded"
                      style={{ fontSize: '12px' }}
                    >
                      <p className="text-blue-900">
                        {selectedRelation === '=' &&
                          '✓ Patient field must exactly match the specified value'}
                        {selectedRelation === '!=' &&
                          '✓ Patient field must not match the specified value'}
                        {selectedRelation === '>' &&
                          '✓ Patient field must be greater than the specified value'}
                        {selectedRelation === '>=' &&
                          '✓ Patient field must be greater than or equal to the specified value'}
                        {selectedRelation === '<' &&
                          '✓ Patient field must be less than the specified value'}
                        {selectedRelation === '<=' &&
                          '✓ Patient field must be less than or equal to the specified value'}
                        {selectedRelation === 'within' &&
                          '✓ Patient field must fall within the specified range (e.g., 18-65)'}
                        {selectedRelation === 'not_in_last' &&
                          '✓ Event must not have occurred in the last N days/months/years'}
                        {selectedRelation === 'contains' &&
                          '✓ Patient field must contain the specified text or value'}
                        {selectedRelation === 'not_contains' &&
                          '✓ Patient field must not contain the specified text or value'}
                      </p>
                    </div>
                  </div>
                </>
              )}

              {/* Target Value Section */}
              {showValueSection && (mappingMode === '' || mappingMode === 'edit-value') && (
                <>
                  <Separator className="mb-4" />
                  <div className="space-y-3 mb-4">
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
                      {((selectedRelation === 'within' && rangeMin && rangeMax) ||
                        (selectedRelation === 'not_in_last' && durationValue) ||
                        (selectedRelation !== 'within' &&
                          selectedRelation !== 'not_in_last' &&
                          selectedValue)) && (
                        <span className="text-blue-600" style={{ fontSize: '12px' }}>
                          Click value to change
                        </span>
                      )}
                    </div>

                    {valueSuggestions.length > 0 &&
                      !selectedValue &&
                      !newValue &&
                      selectedRelation !== 'within' &&
                      selectedRelation !== 'not_in_last' && (
                        <>
                          <div className="space-y-2">
                            <p className="text-gray-600" style={{ fontSize: '12px' }}>
                              Select from common values:
                            </p>
                            <div className="flex flex-wrap" style={{ gap: 'var(--space-2)' }}>
                              {valueSuggestions.map(value => (
                                <Button
                                  key={value}
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setSelectedValue(value)}
                                  style={{ fontSize: '12px' }}
                                >
                                  {value}
                                </Button>
                              ))}
                            </div>
                          </div>

                          <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                            <Separator className="flex-1" />
                            <span className="text-gray-500" style={{ fontSize: '12px' }}>
                              or
                            </span>
                            <Separator className="flex-1" />
                          </div>
                        </>
                      )}

                    {/* Adaptive value input based on relation type */}
                    {selectedRelation === 'within' ? (
                      // Range input for "within"
                      <>
                        {(mappingMode === 'edit-value' || !isRangeConfirmed) && (
                          <div className="space-y-2">
                            <Label style={{ fontSize: '14px' }}>Enter range</Label>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <Input
                                value={rangeMin}
                                onChange={e => setRangeMin(e.target.value)}
                                placeholder="Min (e.g., 18)"
                                style={{ fontSize: '14px' }}
                                className="flex-1"
                              />
                              <span className="text-gray-500" style={{ fontSize: '14px' }}>
                                to
                              </span>
                              <Input
                                value={rangeMax}
                                onChange={e => setRangeMax(e.target.value)}
                                placeholder="Max (e.g., 65)"
                                style={{ fontSize: '14px' }}
                                className="flex-1"
                              />
                            </div>
                            {rangeMin && rangeMax && (
                              <Button
                                size="sm"
                                onClick={() => {
                                  setIsRangeConfirmed(true);
                                  setMappingMode('');
                                }}
                                className="bg-teal-600 hover:bg-teal-700"
                                style={{ fontSize: '14px', gap: 'var(--space-1)' }}
                              >
                                <Check className="w-3 h-3" />
                                Confirm Range
                              </Button>
                            )}
                          </div>
                        )}
                        {rangeMin &&
                          rangeMax &&
                          isRangeConfirmed &&
                          mappingMode !== 'edit-value' && (
                            <button
                              onClick={() => setMappingMode('edit-value')}
                              className="w-full p-3 bg-teal-50 border-2 border-teal-200 rounded-lg hover:border-teal-400 hover:bg-teal-100 transition-colors text-left cursor-pointer"
                            >
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
                                <span className="text-teal-600" style={{ fontSize: '12px' }}>
                                  Click to change
                                </span>
                              </div>
                            </button>
                          )}
                      </>
                    ) : selectedRelation === 'not_in_last' ? (
                      // Duration input for "not_in_last"
                      <>
                        {(mappingMode === 'edit-value' || !isDurationConfirmed) && (
                          <div className="space-y-2">
                            <Label style={{ fontSize: '14px' }}>Enter duration</Label>
                            <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                              <Input
                                value={durationValue}
                                onChange={e => setDurationValue(e.target.value)}
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
                            {durationValue && (
                              <Button
                                size="sm"
                                onClick={() => {
                                  setIsDurationConfirmed(true);
                                  setMappingMode('');
                                }}
                                className="bg-teal-600 hover:bg-teal-700"
                                style={{ fontSize: '14px', gap: 'var(--space-1)' }}
                              >
                                <Check className="w-3 h-3" />
                                Confirm Duration
                              </Button>
                            )}
                          </div>
                        )}
                        {durationValue && isDurationConfirmed && mappingMode !== 'edit-value' && (
                          <button
                            onClick={() => setMappingMode('edit-value')}
                            className="w-full p-3 bg-teal-50 border-2 border-teal-200 rounded-lg hover:border-teal-400 hover:bg-teal-100 transition-colors text-left cursor-pointer"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                                <Check className="w-4 h-4 text-teal-600" />
                                <span
                                  className="font-medium text-gray-900"
                                  style={{ fontSize: '14px' }}
                                >
                                  {durationValue} {durationUnit}
                                </span>
                              </div>
                              <span className="text-teal-600" style={{ fontSize: '12px' }}>
                                Click to change
                              </span>
                            </div>
                          </button>
                        )}
                      </>
                    ) : (
                      // Single value input for all other relations
                      <>
                        {!selectedValue && mappingMode !== 'edit-value' && (
                          <div className="space-y-2">
                            <Label htmlFor="newValue" style={{ fontSize: '14px' }}>
                              {valueSuggestions.length > 0 ? 'Enter custom value' : 'Enter value'}
                            </Label>
                            <Input
                              id="newValue"
                              value={newValue}
                              onChange={e => setNewValue(e.target.value)}
                              placeholder="e.g., Yes, No, or specific value..."
                              style={{ fontSize: '14px' }}
                            />
                          </div>
                        )}

                        {selectedValue && mappingMode !== 'edit-value' && (
                          <button
                            onClick={() => {
                              setMappingMode('edit-value');
                              setNewValue(selectedValue);
                              setSelectedValue('');
                            }}
                            className="w-full p-3 bg-teal-50 border-2 border-teal-200 rounded-lg hover:border-teal-400 hover:bg-teal-100 transition-colors text-left cursor-pointer"
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
                                <Check className="w-4 h-4 text-teal-600" />
                                <span
                                  className="font-medium text-gray-900"
                                  style={{ fontSize: '14px' }}
                                >
                                  {selectedValue}
                                </span>
                                {selectedValue === suggestedValue && isUsingSuggestion && (
                                  <Badge
                                    className="bg-orange-100 text-orange-700 border-orange-300"
                                    style={{ fontSize: '11px', gap: 'var(--space-1)' }}
                                  >
                                    <Sparkles className="w-2.5 h-2.5" />
                                    Suggested
                                  </Badge>
                                )}
                              </div>
                              <span className="text-teal-600" style={{ fontSize: '12px' }}>
                                Click to change
                              </span>
                            </div>
                          </button>
                        )}

                        {mappingMode === 'edit-value' &&
                          selectedRelation !== 'within' &&
                          selectedRelation !== 'not_in_last' && (
                            <div className="space-y-2">
                              {valueSuggestions.length > 0 && (
                                <>
                                  <p className="text-gray-600" style={{ fontSize: '12px' }}>
                                    Select from common values:
                                  </p>
                                  <div className="flex flex-wrap" style={{ gap: 'var(--space-2)' }}>
                                    {valueSuggestions.map(value => (
                                      <Button
                                        key={value}
                                        size="sm"
                                        variant="outline"
                                        onClick={() => {
                                          setSelectedValue(value);
                                          setNewValue('');
                                          setMappingMode('');
                                          setIsUsingSuggestion(false);
                                        }}
                                        style={{ fontSize: '12px' }}
                                      >
                                        {value}
                                      </Button>
                                    ))}
                                  </div>
                                  <div
                                    className="flex items-center"
                                    style={{ gap: 'var(--space-2)' }}
                                  >
                                    <Separator className="flex-1" />
                                    <span className="text-gray-500" style={{ fontSize: '12px' }}>
                                      or
                                    </span>
                                    <Separator className="flex-1" />
                                  </div>
                                </>
                              )}
                              <Label htmlFor="editValue" style={{ fontSize: '14px' }}>
                                {valueSuggestions.length > 0 ? 'Enter custom value' : 'Enter value'}
                              </Label>
                              <Input
                                id="editValue"
                                value={newValue}
                                onChange={e => setNewValue(e.target.value)}
                                placeholder="e.g., Yes, No, or specific value..."
                                style={{ fontSize: '14px' }}
                                autoFocus
                              />
                              <div className="flex" style={{ gap: 'var(--space-2)' }}>
                                <Button
                                  size="sm"
                                  onClick={() => {
                                    if (newValue.trim()) {
                                      setSelectedValue(newValue);
                                      setNewValue('');
                                      setMappingMode('');
                                      setIsUsingSuggestion(false);
                                    }
                                  }}
                                  disabled={!newValue.trim()}
                                  className="bg-teal-600 hover:bg-teal-700"
                                  style={{ fontSize: '14px', gap: 'var(--space-1)' }}
                                >
                                  <Check className="w-3 h-3" />
                                  Apply
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => {
                                    setMappingMode('');
                                    setNewValue('');
                                  }}
                                  style={{ fontSize: '14px' }}
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          )}
                      </>
                    )}
                  </div>
                </>
              )}

              {/* Preview */}
              {selectedField &&
                ((selectedRelation === 'within' && rangeMin && rangeMax) ||
                  (selectedRelation === 'not_in_last' && durationValue) ||
                  (selectedRelation !== 'within' &&
                    selectedRelation !== 'not_in_last' &&
                    (selectedValue || newValue))) &&
                mappingMode === '' && (
                  <>
                    <Separator className="mb-4" />
                    <div className="p-3 bg-gray-50 border border-gray-200 rounded-lg space-y-2 mb-4">
                      <p className="font-medium text-gray-700" style={{ fontSize: '12px' }}>
                        Mapping Preview:
                      </p>
                      <div className="space-y-1" style={{ fontSize: '12px' }}>
                        <div className="flex" style={{ gap: 'var(--space-2)' }}>
                          <span className="text-gray-600 w-24 flex-shrink-0">Source Text:</span>
                          <span className="text-gray-900 font-mono break-words flex-1">
                            &quot;{selectedText}&quot;
                          </span>
                        </div>
                        <div className="flex" style={{ gap: 'var(--space-2)' }}>
                          <span className="text-gray-600 w-24 flex-shrink-0">Maps to Field:</span>
                          <span className="text-gray-900 font-mono break-words flex-1">
                            {selectedFieldLabel}
                          </span>
                        </div>
                        <div className="flex" style={{ gap: 'var(--space-2)' }}>
                          <span className="text-gray-600 w-24 flex-shrink-0">Relation:</span>
                          <span className="text-gray-900 font-mono break-words flex-1">
                            {selectedRelation}
                          </span>
                        </div>
                        <div className="flex" style={{ gap: 'var(--space-2)' }}>
                          <span className="text-gray-600 w-24 flex-shrink-0">Value:</span>
                          <span className="text-gray-900 font-mono break-words flex-1">
                            {selectedRelation === 'within'
                              ? `${rangeMin} - ${rangeMax}`
                              : selectedRelation === 'not_in_last'
                                ? `${durationValue} ${durationUnit}`
                                : selectedValue || newValue}
                          </span>
                        </div>
                        <div className="mt-3 pt-3 border-t border-gray-300">
                          <span className="text-gray-900 font-medium">Validation Rule:</span>
                          <div className="mt-1 p-2 bg-white rounded border border-gray-200">
                            <code
                              className="text-teal-700 break-words block"
                              style={{ fontSize: '11px' }}
                            >
                              {selectedFieldLabel} {selectedRelation}{' '}
                              {selectedRelation === 'within'
                                ? `${rangeMin} - ${rangeMax}`
                                : selectedRelation === 'not_in_last'
                                  ? `${durationValue} ${durationUnit}`
                                  : selectedValue || newValue}
                            </code>
                          </div>
                        </div>
                      </div>
                    </div>
                  </>
                )}
            </div>
          </ScrollArea>
        </div>

        {/* Footer */}
        <div
          className="px-4 py-3 border-t bg-gray-50 flex justify-end flex-shrink-0"
          style={{ gap: 'var(--space-2)' }}
        >
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              handleReset();
              onOpenChange(false);
            }}
            style={{ fontSize: '14px' }}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={
              !selectedField ||
              (selectedRelation === 'within' && (!rangeMin || !rangeMax)) ||
              (selectedRelation === 'not_in_last' && !durationValue) ||
              (selectedRelation !== 'within' &&
                selectedRelation !== 'not_in_last' &&
                !selectedValue &&
                !newValue)
            }
            className="bg-teal-600 hover:bg-teal-700"
            style={{ fontSize: '14px', gap: 'var(--space-1)' }}
          >
            <Check className="w-3 h-3" />
            Save Mapping
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
