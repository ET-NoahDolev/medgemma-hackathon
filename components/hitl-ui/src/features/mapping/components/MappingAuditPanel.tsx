import { useEffect, useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { generateExtendedMockSnippets } from '@/data/mockSemanticSnippets';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  FileText,
  Clock,
  User,
  Sparkles,
  Check,
  TrendingUp,
  Activity,
  Copy,
  ChevronRight,
  Plus,
  Minus,
  Maximize2,
  Minimize2,
  Split,
  X,
  ArrowRight,
  Edit2,
  Search,
  Boxes,
} from 'lucide-react';
import { toast } from 'sonner';
import { FullChartView } from '@/features/patients/components/FullChartView';
import { SemanticExplorerModal } from '@/features/semantic/components/SemanticExplorerModal';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface Mapping {
  id: string;
  emrTerm: string;
  mappingType: 'diagnostic-code' | 'field-value';
  // For diagnostic code mappings
  targetCode?: string;
  targetSystem?: string;
  targetDescription?: string;
  // For field-value mappings
  targetField?: string;
  relation?: string;
  targetValue?: string;
  targetValueMin?: string;
  targetValueMax?: string;
  targetValueUnit?: string;
  // Common fields
  patientCount: number;
}

interface MappingAuditPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mapping: Mapping;
  onAddCustomMapping?: () => void;
}

interface EvidenceSnippet {
  id: string;
  context: string;
  recordType: string;
  timestamp: string;
  frequency: number;
}

interface AuditEvent {
  id: string;
  action: string;
  actor: string;
  site: string;
  timestamp: string;
  details: string;
  correlationId: string;
}

interface Alternative {
  mappingType: 'diagnostic-code' | 'field-value';
  // For diagnostic code alternatives
  code?: string;
  system?: string;
  description?: string;
  // For field-value alternatives
  field?: string;
  relation?: string;
  value?: string;
  // Common fields
  confidence: number;
  usageCount: number;
  reasoning: string;
}

// Field definition with associated terminology IDs
interface FieldDefinition {
  path: string; // e.g., "vitals.blood_pressure.systolic"
  label: string;
  category: string;
  subcategory: string;
  description?: string;
  terminologyIds?: {
    umls?: string;
    snomed?: string;
    loinc?: string;
    rxnorm?: string;
  };
}

const fieldDefinitions: FieldDefinition[] = [
  // Demographics
  {
    path: 'demographics.basic.age',
    label: 'Age',
    category: 'Demographics',
    subcategory: 'Basic Information',
  },
  {
    path: 'demographics.basic.gender',
    label: 'Gender',
    category: 'Demographics',
    subcategory: 'Basic Information',
  },
  {
    path: 'demographics.basic.date_of_birth',
    label: 'Date of Birth',
    category: 'Demographics',
    subcategory: 'Basic Information',
  },

  // Vitals - Blood Pressure
  {
    path: 'vitals.blood_pressure.systolic',
    label: 'Systolic Blood Pressure',
    category: 'Vitals',
    subcategory: 'Blood Pressure',
    description: 'Systolic blood pressure measurement',
    terminologyIds: { loinc: '8480-6', snomed: '271649006', umls: 'C0871470' },
  },
  {
    path: 'vitals.blood_pressure.diastolic',
    label: 'Diastolic Blood Pressure',
    category: 'Vitals',
    subcategory: 'Blood Pressure',
    description: 'Diastolic blood pressure measurement',
    terminologyIds: { loinc: '8462-4', snomed: '271650006', umls: 'C0428883' },
  },
  {
    path: 'vitals.blood_pressure.combined',
    label: 'Blood Pressure (Combined)',
    category: 'Vitals',
    subcategory: 'Blood Pressure',
    description: 'Combined systolic/diastolic BP reading',
    terminologyIds: { loinc: '85354-9', snomed: '75367002' },
  },

  // Vitals - Heart
  {
    path: 'vitals.heart.heart_rate',
    label: 'Heart Rate',
    category: 'Vitals',
    subcategory: 'Heart Measurements',
    description: 'Heart rate in beats per minute',
    terminologyIds: { loinc: '8867-4', snomed: '364075005', umls: 'C0018810' },
  },
  {
    path: 'vitals.heart.pulse',
    label: 'Pulse',
    category: 'Vitals',
    subcategory: 'Heart Measurements',
    description: 'Pulse rate measurement',
    terminologyIds: { loinc: '8893-0', snomed: '78564009' },
  },

  // Vitals - Temperature
  {
    path: 'vitals.temperature.body_temp',
    label: 'Body Temperature',
    category: 'Vitals',
    subcategory: 'Temperature',
    terminologyIds: { loinc: '8310-5', snomed: '276885007', umls: 'C0005903' },
  },
  {
    path: 'vitals.temperature.temp_fahrenheit',
    label: 'Temperature (Fahrenheit)',
    category: 'Vitals',
    subcategory: 'Temperature',
    terminologyIds: { loinc: '8310-5', snomed: '276885007' },
  },
  {
    path: 'vitals.temperature.temp_celsius',
    label: 'Temperature (Celsius)',
    category: 'Vitals',
    subcategory: 'Temperature',
    terminologyIds: { loinc: '8310-5', snomed: '276885007' },
  },

  // Labs - Hematology
  {
    path: 'labs.hematology.hemoglobin',
    label: 'Hemoglobin',
    category: 'Laboratory Results',
    subcategory: 'Hematology',
    terminologyIds: { loinc: '718-7', snomed: '259695003', umls: 'C0019046' },
  },
  {
    path: 'labs.hematology.hematocrit',
    label: 'Hematocrit',
    category: 'Laboratory Results',
    subcategory: 'Hematology',
    terminologyIds: { loinc: '4544-3', snomed: '365616005', umls: 'C0018935' },
  },
  {
    path: 'labs.hematology.wbc',
    label: 'White Blood Cell Count',
    category: 'Laboratory Results',
    subcategory: 'Hematology',
    terminologyIds: { loinc: '6690-2', snomed: '767002', umls: 'C0023508' },
  },

  // Labs - Chemistry
  {
    path: 'labs.chemistry.glucose',
    label: 'Glucose',
    category: 'Laboratory Results',
    subcategory: 'Chemistry',
    terminologyIds: { loinc: '2339-0', snomed: '33747003', umls: 'C0017725' },
  },
  {
    path: 'labs.chemistry.creatinine',
    label: 'Creatinine',
    category: 'Laboratory Results',
    subcategory: 'Chemistry',
    terminologyIds: { loinc: '2160-0', snomed: '70901006', umls: 'C0010294' },
  },
  {
    path: 'labs.chemistry.sodium',
    label: 'Sodium',
    category: 'Laboratory Results',
    subcategory: 'Chemistry',
    terminologyIds: { loinc: '2951-2', snomed: '39972003', umls: 'C0037473' },
  },

  // Medical History
  {
    path: 'medical_history.procedures.prior_colonoscopy',
    label: 'Prior Colonoscopy',
    category: 'Medical History',
    subcategory: 'Procedures',
  },
  {
    path: 'medical_history.procedures.prior_surgery',
    label: 'Prior Surgery',
    category: 'Medical History',
    subcategory: 'Procedures',
  },
  {
    path: 'medical_history.lifestyle.smoking_status',
    label: 'Smoking Status',
    category: 'Medical History',
    subcategory: 'Lifestyle',
    terminologyIds: { loinc: '72166-2', snomed: '365980008' },
  },
  {
    path: 'medical_history.lifestyle.alcohol_use',
    label: 'Alcohol Use',
    category: 'Medical History',
    subcategory: 'Lifestyle',
    terminologyIds: { loinc: '74013-4', snomed: '228273003' },
  },
];

const mockEvidence: EvidenceSnippet[] = [
  {
    id: '1',
    context:
      'Patient presents with chest discomfort and shortness of breath. History of HTN and DM2.',
    recordType: 'Clinical Note',
    timestamp: '2025-10-20 14:23',
    frequency: 45,
  },
  {
    id: '2',
    context: 'Chief complaint: chest discomfort radiating to left arm. No previous cardiac events.',
    recordType: 'Emergency Visit',
    timestamp: '2025-10-18 09:15',
    frequency: 23,
  },
  {
    id: '3',
    context: 'Follow-up for chest discomfort. EKG normal. Stress test scheduled.',
    recordType: 'Cardiology Consult',
    timestamp: '2025-10-15 11:30',
    frequency: 12,
  },
];

const mockAuditTrail: AuditEvent[] = [
  {
    id: '1',
    action: 'Mapping Created',
    actor: 'Dr. Sarah Chen',
    site: 'Boston General Hospital',
    timestamp: '2025-10-15 10:23:45',
    details: 'Initial mapping created via AI suggestion',
    correlationId: 'CORR-20251015-001',
  },
  {
    id: '2',
    action: 'Mapping Validated',
    actor: 'Dr. Michael Patel',
    site: 'Boston General Hospital',
    timestamp: '2025-10-15 14:56:12',
    details: 'Validated mapping accuracy against patient records',
    correlationId: 'CORR-20251015-002',
  },
  {
    id: '3',
    action: 'Applied to Batch',
    actor: 'System',
    site: 'Boston General Hospital',
    timestamp: '2025-10-16 08:00:00',
    details: 'Mapping applied to batch screening process',
    correlationId: 'CORR-20251016-001',
  },
];

const mockAlternatives: Alternative[] = [
  {
    mappingType: 'diagnostic-code',
    code: 'R07.2',
    system: 'ICD-10',
    description: 'Precordial pain',
    confidence: 82,
    usageCount: 234,
    reasoning: 'More specific anatomical location for chest discomfort',
  },
  {
    mappingType: 'diagnostic-code',
    code: 'R07.89',
    system: 'ICD-10',
    description: 'Other chest pain',
    confidence: 75,
    usageCount: 187,
    reasoning: 'Broader categorization, useful when specific location unclear',
  },
  {
    mappingType: 'field-value',
    field: 'vitals.blood_pressure_range',
    relation: 'within',
    value: 'normal',
    confidence: 72,
    usageCount: 156,
    reasoning: 'Categorical representation, less precise but commonly logged',
  },
  {
    mappingType: 'field-value',
    field: 'vitals.bp_systolic',
    relation: '=',
    value: '120',
    confidence: 65,
    usageCount: 89,
    reasoning: 'Separated systolic only, requires additional field for diastolic',
  },
];

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
    code: '38341003',
    system: 'SNOMED CT',
    description: 'Hypertensive disorder',
    usageCount: 2156,
    crossReferences: { umls: 'C0020538', icd10: 'I10' },
  },
  {
    code: '59621000',
    system: 'SNOMED CT',
    description: 'Essential hypertension',
    usageCount: 1892,
    crossReferences: { umls: 'C0085580', icd10: 'I10' },
  },
  {
    code: '44054006',
    system: 'SNOMED CT',
    description: 'Type 2 diabetes mellitus',
    usageCount: 3421,
    crossReferences: { umls: 'C0011860', icd10: 'E11' },
  },
  {
    code: 'I10',
    system: 'ICD-10',
    description: 'Essential (primary) hypertension',
    usageCount: 2789,
    crossReferences: { umls: 'C0085580', snomedCT: '59621000' },
  },
  {
    code: 'C0020538',
    system: 'UMLS',
    description: 'Hypertensive disease',
    usageCount: 4567,
    crossReferences: { snomedCT: '38341003', icd10: 'I10' },
  },
];

export function MappingAuditPanel({
  open,
  onOpenChange,
  mapping,
  onAddCustomMapping,
}: MappingAuditPanelProps) {
  const [activeTab, setActiveTab] = useState('evidence');
  const [fullChartOpen, setFullChartOpen] = useState(false);
  const [selectedSnippet, setSelectedSnippet] = useState<EvidenceSnippet | null>(null);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [snippetToRemove, setSnippetToRemove] = useState<EvidenceSnippet | null>(null);
  const [isFullView, setIsFullView] = useState(false);

  // Edit mode state
  const [editMode, setEditMode] = useState(false);
  const [splitMode, setSplitMode] = useState(false);

  // Unified search state (works for both diagnostic codes and fields)
  const [searchQuery, setSearchQuery] = useState('');

  // Diagnostic code edit state
  const [selectedCode, setSelectedCode] = useState('');
  const [selectedSystem, setSelectedSystem] = useState('');
  const [selectedDescription, setSelectedDescription] = useState('');

  // Field selection state for field 1
  const [selectedField1, setSelectedField1] = useState<FieldDefinition | null>(null);
  const [fieldSearch1, setFieldSearch1] = useState('');

  // Field selection state for field 2 (split mode)
  const [selectedField2, setSelectedField2] = useState<FieldDefinition | null>(null);
  const [fieldSearch2, setFieldSearch2] = useState('');

  // Relation and value state
  const [relation1, setRelation1] = useState(mapping.relation || '=');
  const [value1, setValue1] = useState('');
  const [relation2, setRelation2] = useState('=');
  const [value2, setValue2] = useState('');

  // Value extraction state (split mode)
  const [sourceValue, setSourceValue] = useState('120/80');
  const [delimiter, setDelimiter] = useState('/');
  const [extractedParts, setExtractedParts] = useState<string[]>([]);

  // Rationale
  const [rationale, setRationale] = useState('');

  // Semantic Explorer Modal state
  const [semanticModalOpen, setSemanticModalOpen] = useState(false);
  const [semanticExamples, setSemanticExamples] = useState<unknown[]>([]);

  // Always start "Review" in side-panel mode for consistency.
  // The sheet component can remain mounted between opens, so we reset this on open/close.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Reset view mode when panel opens/closes
    setIsFullView(false);
  }, [open]);

  const handleCopyCorrelationId = (id: string) => {
    navigator.clipboard.writeText(id);
    toast.success('Correlation ID copied');
  };

  const handleApplyAlternative = (alternative: Alternative) => {
    toast.success(`Applied mapping: ${alternative.description}`);
  };

  const handleViewFullContext = (snippet: EvidenceSnippet) => {
    setSelectedSnippet(snippet);
    setFullChartOpen(true);
  };

  const handleAddNonSuggestedMapping = () => {
    if (onAddCustomMapping) {
      onAddCustomMapping();
    } else {
      toast.success('Opening mapping editor for custom mapping');
    }
  };

  const handleRemoveSnippet = (snippet: EvidenceSnippet) => {
    setSnippetToRemove(snippet);
    setRemoveDialogOpen(true);
  };

  const handleExploreSemantics = () => {
    // Generate mock semantic examples for the 3D visualization, including all EMR context snippets
    const examples = generateSemanticExamples(mapping.emrTerm);
    setSemanticExamples(examples);
    setSemanticModalOpen(true);
  };

  const generateSemanticExamples = (term: string) => {
    // Get extended mock snippets (100+ examples)
    const mockSnippets = generateExtendedMockSnippets(term);

    // Include all EMR context snippets as high-confidence examples and merge with mock data
    const emrExamples = mockEvidence.map((snippet, index) => ({
      id: `emr-${snippet.id}`,
      text: snippet.context,
      confidence: 0.95 - index * 0.02, // High confidence for actual EMR snippets
      field: snippet.recordType,
      patientCount: snippet.frequency,
      included: true,
      source: 'emr' as const,
      recordType: snippet.recordType,
      timestamp: snippet.timestamp,
    }));

    // Combine EMR examples with mock snippets
    // Mock snippets already include some EMR examples, so we'll merge intelligently
    return [...emrExamples, ...mockSnippets];
  };

  const handleConfirmRemove = (action: 'apply-different' | 'discard') => {
    if (action === 'apply-different') {
      toast.success('Opening alternative mapping selection');
      // This would open a mapping selector
    } else {
      toast.success(`Removed example: "${snippetToRemove?.context.substring(0, 30)}..."`);
    }
    setRemoveDialogOpen(false);
    setSnippetToRemove(null);
  };

  const handleEnterEditMode = () => {
    setEditMode(true);
    setSplitMode(false);

    if (mapping.mappingType === 'diagnostic-code') {
      // Initialize diagnostic code edit mode
      setSearchQuery('');
      setSelectedCode(mapping.targetCode || '');
      setSelectedSystem(mapping.targetSystem || '');
      setSelectedDescription(mapping.targetDescription || '');
    } else {
      // Initialize field-value edit mode
      setFieldSearch1('');
      if (mapping.targetField) {
        const existingField = fieldDefinitions.find(f => f.path === mapping.targetField);
        setSelectedField1(existingField || null);
      }
      setRelation1(mapping.relation || '=');
      setValue1(mapping.targetValue || '');
    }
    setRationale('');
  };

  const handleCancelEdit = () => {
    setEditMode(false);
    setSplitMode(false);
    setSearchQuery('');
    setSelectedCode('');
    setSelectedSystem('');
    setSelectedDescription('');
    setFieldSearch1('');
    setFieldSearch2('');
    setSelectedField1(null);
    setSelectedField2(null);
    setValue1('');
    setValue2('');
    setRationale('');
  };

  const handleExtractValues = () => {
    if (sourceValue && delimiter) {
      const parts = sourceValue.split(delimiter).map(p => p.trim());
      setExtractedParts(parts);
      if (parts.length >= 1) setValue1(parts[0]);
      if (parts.length >= 2) setValue2(parts[1]);
    }
  };

  const handleSaveEdit = () => {
    if (mapping.mappingType === 'diagnostic-code') {
      // Save diagnostic code mapping
      toast.success(`Mapping updated: ${selectedSystem}:${selectedCode} - ${selectedDescription}`);
    } else if (splitMode) {
      // Save split field-value mapping
      const field1Info = selectedField1 ? `${selectedField1.path} (${selectedField1.label})` : '';
      const field2Info = selectedField2 ? `${selectedField2.path} (${selectedField2.label})` : '';

      toast.success(
        `Split mapping saved:\n1. ${field1Info} ${relation1} ${value1}\n2. ${field2Info} ${relation2} ${value2}`,
        { duration: 5000 }
      );
    } else {
      // Save single field-value mapping
      const fieldInfo = selectedField1 ? `${selectedField1.path} (${selectedField1.label})` : '';
      toast.success(`Mapping updated: ${fieldInfo} ${relation1} ${value1}`);
    }

    setEditMode(false);
    setSplitMode(false);
  };

  // Filter fields based on search query (searches path, label, category, and all terminology IDs)
  const filterFields = (query: string): FieldDefinition[] => {
    if (!query.trim()) return fieldDefinitions;

    const lowerQuery = query.toLowerCase();
    return fieldDefinitions.filter(field => {
      // Search in path, label, category, subcategory
      if (field.path.toLowerCase().includes(lowerQuery)) return true;
      if (field.label.toLowerCase().includes(lowerQuery)) return true;
      if (field.category.toLowerCase().includes(lowerQuery)) return true;
      if (field.subcategory.toLowerCase().includes(lowerQuery)) return true;
      if (field.description?.toLowerCase().includes(lowerQuery)) return true;

      // Search in terminology IDs
      if (field.terminologyIds) {
        if (field.terminologyIds.umls?.toLowerCase().includes(lowerQuery)) return true;
        if (field.terminologyIds.snomed?.toLowerCase().includes(lowerQuery)) return true;
        if (field.terminologyIds.loinc?.toLowerCase().includes(lowerQuery)) return true;
        if (field.terminologyIds.rxnorm?.toLowerCase().includes(lowerQuery)) return true;
      }

      return false;
    });
  };

  const filteredFields1 = filterFields(fieldSearch1);
  const filteredFields2 = filterFields(fieldSearch2);

  const filteredConcepts = mockConcepts.filter(
    concept =>
      concept.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      concept.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      concept.system.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleSelectConcept = (concept: ConceptResult) => {
    setSelectedCode(concept.code);
    setSelectedSystem(concept.system);
    setSelectedDescription(concept.description);
  };

  return (
    <>
      {/* Remove Dialog */}
      <AlertDialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Evidence Example?</AlertDialogTitle>
            <AlertDialogDescription>
              This example will be excluded from this mapping. What would you like to do?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <Button variant="outline" onClick={() => handleConfirmRemove('apply-different')}>
              Apply Different Mapping
            </Button>
            <AlertDialogAction
              onClick={() => handleConfirmRemove('discard')}
              className="bg-red-600 hover:bg-red-700"
            >
              Discard Example
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Full Chart View (opened from "Full Context") */}

      <Sheet
        open={open}
        onOpenChange={nextOpen => {
          onOpenChange(nextOpen);
          if (!nextOpen) {
            // Ensure any nested layers also close.
            setFullChartOpen(false);
            setSelectedSnippet(null);
            setSemanticModalOpen(false);
          }
        }}
      >
        <SheetContent
          side="right"
          className={`mapping-audit-sheet ${isFullView ? 'mapping-audit-sheet--full' : ''} p-0 flex flex-col ${
            isFullView ? '!w-screen md:!w-screen md:!max-w-none !rounded-none !border-0' : ''
          }`}
          style={{
            gap: 0,
            width: isFullView ? '100vw' : 'min(1040px, 90vw)',
            maxWidth: 'none',
          }}
          onEscapeKeyDown={() => onOpenChange(false)}
          onPointerDownOutside={() => onOpenChange(false)}
        >
          <SheetHeader className="mapping-audit-header px-6 py-4 border-b">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <SheetTitle className="flex items-center gap-2 text-lg">
                  <Activity className="w-5 h-5" />
                  Mapping Audit & Evidence
                </SheetTitle>
                <SheetDescription className="text-sm">
                  Detailed evidence, audit trail, and alternatives for{' '}
                  <span className="font-semibold text-foreground">{mapping.emrTerm}</span>
                </SheetDescription>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onOpenChange(false)}
                  className="gap-2 text-[13px]"
                >
                  <X className="w-4 h-4" />
                  Close
                </Button>
                {!editMode && (
                  <Button
                    size="sm"
                    onClick={handleEnterEditMode}
                    className="bg-teal-600 hover:bg-teal-700 gap-2 text-[13px]"
                  >
                    <Edit2 className="w-4 h-4" />
                    Edit mapping
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsFullView(v => !v)}
                  className="gap-2 text-[13px]"
                >
                  {isFullView ? (
                    <Minimize2 className="w-4 h-4" />
                  ) : (
                    <Maximize2 className="w-4 h-4" />
                  )}
                  {isFullView ? 'Exit full view' : 'Open full view'}
                </Button>
              </div>
            </div>

            {/* Current Mapping Summary / Edit Mode */}
            <div className="mt-4 rounded-lg border border-teal-200 bg-teal-50/70 p-4">
              {!editMode ? (
                /* View Mode (compact) */
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      className={`text-[11px] ${
                        mapping.mappingType === 'diagnostic-code'
                          ? 'bg-teal-100 text-teal-700 border-teal-300'
                          : 'bg-blue-100 text-blue-700 border-blue-300'
                      }`}
                    >
                      {mapping.mappingType === 'diagnostic-code'
                        ? 'Diagnostic Code'
                        : 'Field Mapping'}
                    </Badge>
                    {mapping.mappingType === 'diagnostic-code' && (
                      <Badge variant="outline" className="text-[11px]">
                        Current
                      </Badge>
                    )}
                  </div>

                  <div className="mt-3 flex items-start gap-3">
                    <div className="mt-0.5">
                      <Check className="w-4 h-4 text-teal-600" />
                    </div>

                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-foreground">{mapping.emrTerm}</span>
                        <span className="text-muted-foreground">→</span>
                        {mapping.mappingType === 'diagnostic-code' ? (
                          <>
                            {mapping.targetSystem && (
                              <Badge className="bg-teal-100 text-teal-700 border-teal-300 text-[11px]">
                                {mapping.targetSystem}
                              </Badge>
                            )}
                            {mapping.targetCode && (
                              <span className="font-mono text-foreground">
                                {mapping.targetCode}
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="font-mono text-foreground truncate">
                            {mapping.targetField} {mapping.relation} {mapping.targetValue}
                          </span>
                        )}
                      </div>

                      {mapping.mappingType === 'diagnostic-code' && mapping.targetDescription && (
                        <div className="mt-1 text-sm text-muted-foreground">
                          {mapping.targetDescription}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between border-t border-teal-200/70 pt-3 text-xs text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <User className="w-3 h-3" />
                      <span>{mapping.patientCount} patients</span>
                    </div>
                  </div>
                </>
              ) : (
                /* Edit Mode */
                <div
                  className="max-h-[calc(85vh-120px)] overflow-hidden"
                  style={{ height: 'calc(85vh - 120px)' }}
                >
                  <ScrollArea className="h-full">
                    <div className="space-y-4 pr-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2" style={{ gap: 'var(--space-2)' }}>
                          <Badge
                            className="bg-orange-100 text-orange-700 border-orange-300"
                            style={{ fontSize: '11px' }}
                          >
                            Edit Mode
                          </Badge>
                          {splitMode && (
                            <Badge
                              className="bg-purple-100 text-purple-700 border-purple-300"
                              style={{ fontSize: '11px' }}
                            >
                              Split Active
                            </Badge>
                          )}
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={handleCancelEdit}
                          style={{ fontSize: '12px', gap: 'var(--space-1)' }}
                        >
                          <X className="w-3 h-3" />
                          Cancel
                        </Button>
                      </div>

                      {/* Diagnostic Code Edit Mode */}
                      {mapping.mappingType === 'diagnostic-code' ? (
                        <>
                          <div className="space-y-3">
                            <Label
                              className="flex items-center gap-2"
                              style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                            >
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

                          {searchQuery && filteredConcepts.length > 0 && (
                            <div className="space-y-2">
                              <Label style={{ fontSize: '14px' }}>Search Results</Label>
                              <div className="space-y-2">
                                {filteredConcepts.map(concept => (
                                  <button
                                    key={`${concept.system}-${concept.code}`}
                                    onClick={() => handleSelectConcept(concept)}
                                    className={`w-full p-3 border rounded-lg text-left transition-all ${
                                      selectedCode === concept.code &&
                                      selectedSystem === concept.system
                                        ? 'border-teal-500 bg-teal-50'
                                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                    }`}
                                  >
                                    <div className="flex items-start justify-between mb-2">
                                      <div
                                        className="flex items-center gap-2"
                                        style={{ gap: 'var(--space-2)' }}
                                      >
                                        <Badge variant="outline" style={{ fontSize: '11px' }}>
                                          {concept.system}
                                        </Badge>
                                        <span
                                          className="font-mono text-gray-900"
                                          style={{ fontSize: '13px' }}
                                        >
                                          {concept.code}
                                        </span>
                                      </div>
                                      {selectedCode === concept.code &&
                                        selectedSystem === concept.system && (
                                          <Check className="w-4 h-4 text-teal-600 flex-shrink-0" />
                                        )}
                                    </div>
                                    <p className="text-gray-700 mb-1" style={{ fontSize: '14px' }}>
                                      {concept.description}
                                    </p>
                                    <div
                                      className="flex items-center gap-3 text-gray-500"
                                      style={{ fontSize: '12px', gap: 'var(--space-3)' }}
                                    >
                                      <span
                                        className="flex items-center gap-1"
                                        style={{ gap: 'var(--space-1)' }}
                                      >
                                        <TrendingUp className="w-3 h-3" />
                                        Used {concept.usageCount.toLocaleString()} times
                                      </span>
                                      {concept.crossReferences && (
                                        <>
                                          <span>•</span>
                                          <span>
                                            {Object.keys(concept.crossReferences).length} cross-refs
                                          </span>
                                        </>
                                      )}
                                    </div>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {selectedCode && selectedSystem && (
                            <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                              <div
                                className="flex items-center mb-2"
                                style={{ gap: 'var(--space-2)' }}
                              >
                                <Check className="w-4 h-4 text-green-600" />
                                <span
                                  className="font-medium text-green-900"
                                  style={{ fontSize: '14px' }}
                                >
                                  Selected Mapping
                                </span>
                              </div>
                              <div
                                className="flex items-center gap-2 mb-1"
                                style={{ gap: 'var(--space-2)' }}
                              >
                                <Badge
                                  className="bg-teal-100 text-teal-700 border-teal-300"
                                  style={{ fontSize: '11px' }}
                                >
                                  {selectedSystem}
                                </Badge>
                                <span
                                  className="font-mono text-gray-900"
                                  style={{ fontSize: '14px' }}
                                >
                                  {selectedCode}
                                </span>
                              </div>
                              <p className="text-gray-700" style={{ fontSize: '14px' }}>
                                {selectedDescription}
                              </p>
                            </div>
                          )}

                          <div className="space-y-2">
                            <Label htmlFor="rationale" style={{ fontSize: '14px' }}>
                              Rationale <span className="text-gray-500">(Required)</span>
                            </Label>
                            <Textarea
                              id="rationale"
                              value={rationale}
                              onChange={e => setRationale(e.target.value)}
                              placeholder="Explain why this mapping change is necessary..."
                              rows={3}
                              style={{ fontSize: '14px' }}
                            />
                          </div>

                          <div className="flex gap-2 pt-3" style={{ gap: 'var(--space-2)' }}>
                            <Button
                              onClick={handleSaveEdit}
                              disabled={!selectedCode || !rationale.trim()}
                              className="flex-1 bg-teal-600 hover:bg-teal-700"
                              style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                            >
                              <Check className="w-4 h-4" />
                              Save Mapping
                            </Button>
                            <Button
                              variant="outline"
                              onClick={handleCancelEdit}
                              style={{ fontSize: '14px' }}
                            >
                              Cancel
                            </Button>
                          </div>
                        </>
                      ) : (
                        <>
                          {/* Field-Value Edit Mode */}
                          {/* Split Mode Toggle */}
                          {!splitMode && (
                            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div
                                    className="flex items-center mb-1"
                                    style={{ gap: 'var(--space-2)' }}
                                  >
                                    <Split className="w-4 h-4 text-blue-600" />
                                    <span
                                      className="font-medium text-blue-900"
                                      style={{ fontSize: '14px' }}
                                    >
                                      Split into two fields?
                                    </span>
                                  </div>
                                  <p className="text-blue-700" style={{ fontSize: '12px' }}>
                                    Use for compound values like &quot;120/80&quot; → Systolic + Diastolic
                                  </p>
                                </div>
                                <Button
                                  size="sm"
                                  onClick={() => setSplitMode(true)}
                                  className="bg-blue-600 hover:bg-blue-700 ml-4"
                                  style={{ fontSize: '14px', gap: 'var(--space-1)' }}
                                >
                                  <Split className="w-3 h-3" />
                                  Enable
                                </Button>
                              </div>
                            </div>
                          )}

                          {splitMode && (
                            <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                              <div className="flex items-center justify-between mb-3">
                                <div
                                  className="flex items-center"
                                  style={{ gap: 'var(--space-2)' }}
                                >
                                  <Split className="w-4 h-4 text-purple-600" />
                                  <span
                                    className="font-medium text-purple-900"
                                    style={{ fontSize: '14px' }}
                                  >
                                    Value Extraction
                                  </span>
                                </div>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setSplitMode(false)}
                                  className="text-purple-700 hover:text-purple-900"
                                  style={{ fontSize: '12px' }}
                                >
                                  Disable Split
                                </Button>
                              </div>

                              <div className="space-y-3">
                                <div className="grid grid-cols-2 gap-2">
                                  <div>
                                    <Label htmlFor="sourceValue" style={{ fontSize: '12px' }}>
                                      Source Value Example
                                    </Label>
                                    <Input
                                      id="sourceValue"
                                      value={sourceValue}
                                      onChange={e => setSourceValue(e.target.value)}
                                      placeholder="e.g., 120/80"
                                      style={{ fontSize: '14px' }}
                                    />
                                  </div>
                                  <div>
                                    <Label htmlFor="delimiter" style={{ fontSize: '12px' }}>
                                      Delimiter
                                    </Label>
                                    <Input
                                      id="delimiter"
                                      value={delimiter}
                                      onChange={e => setDelimiter(e.target.value)}
                                      placeholder="e.g., /"
                                      style={{ fontSize: '14px' }}
                                    />
                                  </div>
                                </div>

                                <Button
                                  size="sm"
                                  onClick={handleExtractValues}
                                  variant="outline"
                                  className="w-full"
                                  style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                                >
                                  <ArrowRight className="w-3 h-3" />
                                  Extract Parts
                                </Button>

                                {extractedParts.length > 0 && (
                                  <div className="p-2 bg-white border border-purple-200 rounded">
                                    <p className="text-gray-600 mb-2" style={{ fontSize: '12px' }}>
                                      Extracted Parts:
                                    </p>
                                    <div className="flex gap-2">
                                      {extractedParts.map((part, idx) => (
                                        <Badge
                                          key={idx}
                                          variant="outline"
                                          style={{ fontSize: '12px' }}
                                        >
                                          Part {idx + 1}: {part}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )}

                          <Separator />

                          {/* Field 1 Search */}
                          <div className="space-y-3">
                            <Label style={{ fontSize: '14px', gap: 'var(--space-2)' }}>
                              Search Target Field {splitMode && '#1'}
                              {splitMode && extractedParts.length > 0 && (
                                <Badge
                                  className="ml-2 bg-purple-100 text-purple-700 border-purple-300"
                                  style={{ fontSize: '11px' }}
                                >
                                  ← Part 1: {extractedParts[0]}
                                </Badge>
                              )}
                              <Badge variant="outline" style={{ fontSize: '11px' }}>
                                Required
                              </Badge>
                            </Label>

                            <div className="relative">
                              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                              <Input
                                value={fieldSearch1}
                                onChange={e => setFieldSearch1(e.target.value)}
                                placeholder="Search by field name or terminology ID..."
                                className="pl-10"
                                style={{ fontSize: '14px' }}
                              />
                            </div>

                            {fieldSearch1 && filteredFields1.length > 0 && (
                              <div className="space-y-2">
                                <Label style={{ fontSize: '14px' }}>Search Results</Label>
                                <div className="space-y-2 max-h-60 overflow-y-auto">
                                  {filteredFields1.map(field => (
                                    <button
                                      key={field.path}
                                      onClick={() => {
                                        setSelectedField1(field);
                                        setFieldSearch1('');
                                      }}
                                      className={`w-full p-3 border rounded-lg text-left transition-all ${
                                        selectedField1?.path === field.path
                                          ? 'border-teal-500 bg-teal-50'
                                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                      }`}
                                    >
                                      <div className="flex items-start justify-between mb-2">
                                        <div>
                                          <div
                                            className="flex items-center gap-2 mb-1"
                                            style={{ gap: 'var(--space-2)' }}
                                          >
                                            <Badge variant="outline" style={{ fontSize: '11px' }}>
                                              {field.category}
                                            </Badge>
                                            <ChevronRight className="w-3 h-3 text-gray-400" />
                                            <span
                                              className="text-gray-600"
                                              style={{ fontSize: '12px' }}
                                            >
                                              {field.subcategory}
                                            </span>
                                          </div>
                                          <p
                                            className="text-gray-900 mb-1"
                                            style={{ fontSize: '14px' }}
                                          >
                                            {field.label}
                                          </p>
                                          <p
                                            className="font-mono text-gray-500"
                                            style={{ fontSize: '12px' }}
                                          >
                                            {field.path}
                                          </p>
                                        </div>
                                        {selectedField1?.path === field.path && (
                                          <Check className="w-4 h-4 text-teal-600 flex-shrink-0" />
                                        )}
                                      </div>
                                      {field.terminologyIds && (
                                        <div
                                          className="flex flex-wrap gap-2 mt-2"
                                          style={{ gap: 'var(--space-2)' }}
                                        >
                                          {field.terminologyIds.loinc && (
                                            <Badge
                                              variant="outline"
                                              className="bg-blue-50"
                                              style={{ fontSize: '11px' }}
                                            >
                                              LOINC: {field.terminologyIds.loinc}
                                            </Badge>
                                          )}
                                          {field.terminologyIds.snomed && (
                                            <Badge
                                              variant="outline"
                                              className="bg-green-50"
                                              style={{ fontSize: '11px' }}
                                            >
                                              SNOMED: {field.terminologyIds.snomed}
                                            </Badge>
                                          )}
                                          {field.terminologyIds.umls && (
                                            <Badge
                                              variant="outline"
                                              className="bg-purple-50"
                                              style={{ fontSize: '11px' }}
                                            >
                                              UMLS: {field.terminologyIds.umls}
                                            </Badge>
                                          )}
                                          {field.terminologyIds.rxnorm && (
                                            <Badge
                                              variant="outline"
                                              className="bg-orange-50"
                                              style={{ fontSize: '11px' }}
                                            >
                                              RxNorm: {field.terminologyIds.rxnorm}
                                            </Badge>
                                          )}
                                        </div>
                                      )}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}

                            {selectedField1 && (
                              <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                                <div
                                  className="flex items-center mb-2"
                                  style={{ gap: 'var(--space-2)' }}
                                >
                                  <Check className="w-4 h-4 text-green-600" />
                                  <span
                                    className="font-medium text-green-900"
                                    style={{ fontSize: '14px' }}
                                  >
                                    Selected Field
                                  </span>
                                </div>
                                <div
                                  className="flex items-center gap-2 mb-1"
                                  style={{ gap: 'var(--space-2)' }}
                                >
                                  <Badge
                                    className="bg-teal-100 text-teal-700 border-teal-300"
                                    style={{ fontSize: '11px' }}
                                  >
                                    {selectedField1.category}
                                  </Badge>
                                  <span className="text-gray-600" style={{ fontSize: '12px' }}>
                                    {selectedField1.subcategory}
                                  </span>
                                </div>
                                <p className="text-gray-900 mb-1" style={{ fontSize: '14px' }}>
                                  {selectedField1.label}
                                </p>
                                <p className="font-mono text-gray-600" style={{ fontSize: '12px' }}>
                                  {selectedField1.path}
                                </p>
                                {selectedField1.terminologyIds && (
                                  <div
                                    className="flex flex-wrap gap-2 mt-2"
                                    style={{ gap: 'var(--space-2)' }}
                                  >
                                    {selectedField1.terminologyIds.loinc && (
                                      <Badge
                                        variant="outline"
                                        className="bg-blue-50"
                                        style={{ fontSize: '10px' }}
                                      >
                                        LOINC: {selectedField1.terminologyIds.loinc}
                                      </Badge>
                                    )}
                                    {selectedField1.terminologyIds.snomed && (
                                      <Badge
                                        variant="outline"
                                        className="bg-green-50"
                                        style={{ fontSize: '10px' }}
                                      >
                                        SNOMED: {selectedField1.terminologyIds.snomed}
                                      </Badge>
                                    )}
                                    {selectedField1.terminologyIds.umls && (
                                      <Badge
                                        variant="outline"
                                        className="bg-purple-50"
                                        style={{ fontSize: '10px' }}
                                      >
                                        UMLS: {selectedField1.terminologyIds.umls}
                                      </Badge>
                                    )}
                                    {selectedField1.terminologyIds.rxnorm && (
                                      <Badge
                                        variant="outline"
                                        className="bg-orange-50"
                                        style={{ fontSize: '10px' }}
                                      >
                                        RxNorm: {selectedField1.terminologyIds.rxnorm}
                                      </Badge>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>

                          {/* Relation 1 */}
                          <div className="space-y-2">
                            <Label htmlFor="relation1" style={{ fontSize: '14px' }}>
                              Relation {splitMode && '#1'}
                            </Label>
                            <Select value={relation1} onValueChange={setRelation1}>
                              <SelectTrigger id="relation1" style={{ fontSize: '14px' }}>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="=" style={{ fontSize: '14px' }}>
                                  = (Equals)
                                </SelectItem>
                                <SelectItem value="!=" style={{ fontSize: '14px' }}>
                                  ≠ (Not equals)
                                </SelectItem>
                                <SelectItem value=">" style={{ fontSize: '14px' }}>
                                  &gt; (Greater than)
                                </SelectItem>
                                <SelectItem value=">=" style={{ fontSize: '14px' }}>
                                  ≥ (Greater than or equal)
                                </SelectItem>
                                <SelectItem value="<" style={{ fontSize: '14px' }}>
                                  &lt; (Less than)
                                </SelectItem>
                                <SelectItem value="<=" style={{ fontSize: '14px' }}>
                                  ≤ (Less than or equal)
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          {/* Value 1 */}
                          <div className="space-y-2">
                            <Label htmlFor="value1" style={{ fontSize: '14px' }}>
                              Value {splitMode && '#1'}
                            </Label>
                            <Input
                              id="value1"
                              value={value1}
                              onChange={e => setValue1(e.target.value)}
                              placeholder="Enter value..."
                              style={{ fontSize: '14px' }}
                            />
                          </div>

                          {/* Field 2 (Split Mode) */}
                          {splitMode && (
                            <>
                              <Separator />

                              <div className="space-y-3">
                                <Label style={{ fontSize: '14px', gap: 'var(--space-2)' }}>
                                  Search Target Field #2
                                  {extractedParts.length > 1 && (
                                    <Badge
                                      className="ml-2 bg-purple-100 text-purple-700 border-purple-300"
                                      style={{ fontSize: '11px' }}
                                    >
                                      ← Part 2: {extractedParts[1]}
                                    </Badge>
                                  )}
                                  <Badge variant="outline" style={{ fontSize: '11px' }}>
                                    Required
                                  </Badge>
                                </Label>

                                <div className="relative">
                                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                                  <Input
                                    value={fieldSearch2}
                                    onChange={e => setFieldSearch2(e.target.value)}
                                    placeholder="Search by field name or terminology ID..."
                                    className="pl-10"
                                    style={{ fontSize: '14px' }}
                                  />
                                </div>

                                {fieldSearch2 && filteredFields2.length > 0 && (
                                  <div className="space-y-2">
                                    <Label style={{ fontSize: '14px' }}>Search Results</Label>
                                    <div className="space-y-2 max-h-60 overflow-y-auto">
                                      {filteredFields2.map(field => (
                                        <button
                                          key={field.path}
                                          onClick={() => {
                                            setSelectedField2(field);
                                            setFieldSearch2('');
                                          }}
                                          className={`w-full p-3 border rounded-lg text-left transition-all ${
                                            selectedField2?.path === field.path
                                              ? 'border-teal-500 bg-teal-50'
                                              : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                                          }`}
                                        >
                                          <div className="flex items-start justify-between mb-2">
                                            <div>
                                              <div
                                                className="flex items-center gap-2 mb-1"
                                                style={{ gap: 'var(--space-2)' }}
                                              >
                                                <Badge
                                                  variant="outline"
                                                  style={{ fontSize: '11px' }}
                                                >
                                                  {field.category}
                                                </Badge>
                                                <ChevronRight className="w-3 h-3 text-gray-400" />
                                                <span
                                                  className="text-gray-600"
                                                  style={{ fontSize: '12px' }}
                                                >
                                                  {field.subcategory}
                                                </span>
                                              </div>
                                              <p
                                                className="text-gray-900 mb-1"
                                                style={{ fontSize: '14px' }}
                                              >
                                                {field.label}
                                              </p>
                                              <p
                                                className="font-mono text-gray-500"
                                                style={{ fontSize: '12px' }}
                                              >
                                                {field.path}
                                              </p>
                                            </div>
                                            {selectedField2?.path === field.path && (
                                              <Check className="w-4 h-4 text-teal-600 flex-shrink-0" />
                                            )}
                                          </div>
                                          {field.terminologyIds && (
                                            <div
                                              className="flex flex-wrap gap-2 mt-2"
                                              style={{ gap: 'var(--space-2)' }}
                                            >
                                              {field.terminologyIds.loinc && (
                                                <Badge
                                                  variant="outline"
                                                  className="bg-blue-50"
                                                  style={{ fontSize: '11px' }}
                                                >
                                                  LOINC: {field.terminologyIds.loinc}
                                                </Badge>
                                              )}
                                              {field.terminologyIds.snomed && (
                                                <Badge
                                                  variant="outline"
                                                  className="bg-green-50"
                                                  style={{ fontSize: '11px' }}
                                                >
                                                  SNOMED: {field.terminologyIds.snomed}
                                                </Badge>
                                              )}
                                              {field.terminologyIds.umls && (
                                                <Badge
                                                  variant="outline"
                                                  className="bg-purple-50"
                                                  style={{ fontSize: '11px' }}
                                                >
                                                  UMLS: {field.terminologyIds.umls}
                                                </Badge>
                                              )}
                                              {field.terminologyIds.rxnorm && (
                                                <Badge
                                                  variant="outline"
                                                  className="bg-orange-50"
                                                  style={{ fontSize: '11px' }}
                                                >
                                                  RxNorm: {field.terminologyIds.rxnorm}
                                                </Badge>
                                              )}
                                            </div>
                                          )}
                                        </button>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {selectedField2 && (
                                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                                    <div
                                      className="flex items-center mb-2"
                                      style={{ gap: 'var(--space-2)' }}
                                    >
                                      <Check className="w-4 h-4 text-green-600" />
                                      <span
                                        className="font-medium text-green-900"
                                        style={{ fontSize: '14px' }}
                                      >
                                        Selected Field #2
                                      </span>
                                    </div>
                                    <div
                                      className="flex items-center gap-2 mb-1"
                                      style={{ gap: 'var(--space-2)' }}
                                    >
                                      <Badge
                                        className="bg-teal-100 text-teal-700 border-teal-300"
                                        style={{ fontSize: '11px' }}
                                      >
                                        {selectedField2.category}
                                      </Badge>
                                      <span className="text-gray-600" style={{ fontSize: '12px' }}>
                                        {selectedField2.subcategory}
                                      </span>
                                    </div>
                                    <p className="text-gray-900 mb-1" style={{ fontSize: '14px' }}>
                                      {selectedField2.label}
                                    </p>
                                    <p
                                      className="font-mono text-gray-600"
                                      style={{ fontSize: '12px' }}
                                    >
                                      {selectedField2.path}
                                    </p>
                                    {selectedField2.terminologyIds && (
                                      <div
                                        className="flex flex-wrap gap-2 mt-2"
                                        style={{ gap: 'var(--space-2)' }}
                                      >
                                        {selectedField2.terminologyIds.loinc && (
                                          <Badge
                                            variant="outline"
                                            className="bg-blue-50"
                                            style={{ fontSize: '10px' }}
                                          >
                                            LOINC: {selectedField2.terminologyIds.loinc}
                                          </Badge>
                                        )}
                                        {selectedField2.terminologyIds.snomed && (
                                          <Badge
                                            variant="outline"
                                            className="bg-green-50"
                                            style={{ fontSize: '10px' }}
                                          >
                                            SNOMED: {selectedField2.terminologyIds.snomed}
                                          </Badge>
                                        )}
                                        {selectedField2.terminologyIds.umls && (
                                          <Badge
                                            variant="outline"
                                            className="bg-purple-50"
                                            style={{ fontSize: '10px' }}
                                          >
                                            UMLS: {selectedField2.terminologyIds.umls}
                                          </Badge>
                                        )}
                                        {selectedField2.terminologyIds.rxnorm && (
                                          <Badge
                                            variant="outline"
                                            className="bg-orange-50"
                                            style={{ fontSize: '10px' }}
                                          >
                                            RxNorm: {selectedField2.terminologyIds.rxnorm}
                                          </Badge>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>

                              <div className="space-y-2">
                                <Label htmlFor="relation2" style={{ fontSize: '14px' }}>
                                  Relation #2
                                </Label>
                                <Select value={relation2} onValueChange={setRelation2}>
                                  <SelectTrigger id="relation2" style={{ fontSize: '14px' }}>
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="=" style={{ fontSize: '14px' }}>
                                      = (Equals)
                                    </SelectItem>
                                    <SelectItem value="!=" style={{ fontSize: '14px' }}>
                                      ≠ (Not equals)
                                    </SelectItem>
                                    <SelectItem value=">" style={{ fontSize: '14px' }}>
                                      &gt; (Greater than)
                                    </SelectItem>
                                    <SelectItem value=">=" style={{ fontSize: '14px' }}>
                                      ≥ (Greater than or equal)
                                    </SelectItem>
                                    <SelectItem value="<" style={{ fontSize: '14px' }}>
                                      &lt; (Less than)
                                    </SelectItem>
                                    <SelectItem value="<=" style={{ fontSize: '14px' }}>
                                      ≤ (Less than or equal)
                                    </SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>

                              <div className="space-y-2">
                                <Label htmlFor="value2" style={{ fontSize: '14px' }}>
                                  Value #2
                                </Label>
                                <Input
                                  id="value2"
                                  value={value2}
                                  onChange={e => setValue2(e.target.value)}
                                  placeholder="Enter value..."
                                  style={{ fontSize: '14px' }}
                                />
                              </div>
                            </>
                          )}

                          <Separator />

                          {/* Rationale */}
                          <div className="space-y-2">
                            <Label
                              htmlFor="rationale-field"
                              style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                            >
                              Reason for Change
                              <Badge variant="outline" style={{ fontSize: '11px' }}>
                                Required
                              </Badge>
                            </Label>
                            <Textarea
                              id="rationale-field"
                              value={rationale}
                              onChange={e => setRationale(e.target.value)}
                              placeholder={
                                splitMode
                                  ? 'Explain why splitting this mapping is necessary...'
                                  : 'Explain why this mapping change is necessary...'
                              }
                              rows={3}
                              className="resize-none"
                              style={{ fontSize: '14px' }}
                            />
                          </div>

                          {/* Save Button */}
                          <Button
                            onClick={handleSaveEdit}
                            disabled={
                              mapping.mappingType === 'field-value'
                                ? !rationale.trim() ||
                                  !selectedField1 ||
                                  !value1 ||
                                  (splitMode && (!selectedField2 || !value2))
                                : false
                            }
                            className="w-full bg-teal-600 hover:bg-teal-700"
                            style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                          >
                            <Check className="w-4 h-4" />
                            Save Changes
                          </Button>
                        </>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              )}
            </div>
          </SheetHeader>

          {/* Tabs - Only show when not in edit mode */}
          {!editMode && (
            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className="flex-1 flex flex-col overflow-hidden"
            >
              <div className="px-6 pt-4 border-b">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="evidence" style={{ fontSize: '14px', gap: 'var(--space-2)' }}>
                    <FileText className="w-4 h-4" />
                    Evidence
                  </TabsTrigger>
                  <TabsTrigger value="audit" style={{ fontSize: '14px', gap: 'var(--space-2)' }}>
                    <Clock className="w-4 h-4" />
                    Audit Trail
                  </TabsTrigger>
                  <TabsTrigger
                    value="alternatives"
                    style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                  >
                    <Sparkles className="w-4 h-4" />
                    Alternatives
                  </TabsTrigger>
                </TabsList>
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-hidden">
                <ScrollArea className="h-full">
                  <div className="p-6">
                    {/* Evidence Tab */}
                    <TabsContent value="evidence" className="mt-0">
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-gray-900 mb-2" style={{ fontSize: '16px' }}>
                              EMR Context Snippets
                            </h3>
                            <p className="text-gray-600 mb-4" style={{ fontSize: '14px' }}>
                              Examples of how &quot;{mapping.emrTerm}&quot; appears in patient records
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleAddNonSuggestedMapping}
                            style={{ fontSize: '12px', gap: 'var(--space-2)' }}
                          >
                            <Plus className="w-4 h-4" />
                            Add Custom Mapping
                          </Button>
                        </div>

                        {/* 3D Semantic Explorer Button - Above all snippets */}
                        <div className="p-4 bg-gradient-to-r from-teal-50 to-blue-50 border border-teal-200 rounded-lg">
                          <div className="flex flex-col" style={{ gap: 'var(--space-3)' }}>
                            <div>
                              <h4 className="text-gray-900 mb-1" style={{ fontSize: '14px' }}>
                                3D Semantic Space Visualization
                              </h4>
                              <p className="text-gray-600" style={{ fontSize: '12px' }}>
                                Explore all EMR snippets and semantic variations in interactive 3D
                                space using UMAP embeddings
                              </p>
                            </div>
                            <Button
                              onClick={handleExploreSemantics}
                              className="bg-teal-600 hover:bg-teal-700 text-white w-full"
                              style={{ fontSize: '14px', gap: 'var(--space-2)' }}
                            >
                              <Boxes className="w-4 h-4" />
                              Explore 3D Semantic Space
                            </Button>
                          </div>
                        </div>

                        <div className="space-y-3">
                          {mockEvidence.map(snippet => (
                            <div
                              key={snippet.id}
                              className="p-4 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
                            >
                              <div
                                className="flex items-start justify-between gap-3 mb-2"
                                style={{ gap: 'var(--space-3)' }}
                              >
                                <Badge
                                  className="bg-blue-100 text-blue-700 border-blue-300"
                                  style={{ fontSize: '11px' }}
                                >
                                  {snippet.recordType}
                                </Badge>
                                <div
                                  className="flex items-center gap-3 text-gray-500"
                                  style={{ fontSize: '12px', gap: 'var(--space-3)' }}
                                >
                                  <span
                                    className="flex items-center gap-1"
                                    style={{ gap: 'var(--space-1)' }}
                                  >
                                    <TrendingUp className="w-3 h-3" />
                                    {snippet.frequency} occurrences
                                  </span>
                                  <span
                                    className="flex items-center gap-1"
                                    style={{ gap: 'var(--space-1)' }}
                                  >
                                    <Clock className="w-3 h-3" />
                                    {snippet.timestamp}
                                  </span>
                                </div>
                              </div>

                              <p className="text-gray-700 italic mb-3" style={{ fontSize: '14px' }}>
                                &quot;{snippet.context}&quot;
                              </p>

                              <div
                                className="flex gap-2 pt-2 border-t"
                                style={{ gap: 'var(--space-2)' }}
                              >
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleViewFullContext(snippet)}
                                  style={{ fontSize: '12px', gap: 'var(--space-2)' }}
                                >
                                  <Maximize2 className="w-3 h-3" />
                                  Full Context
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRemoveSnippet(snippet)}
                                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                                  style={{ fontSize: '12px', gap: 'var(--space-2)' }}
                                >
                                  <Minus className="w-3 h-3" />
                                  Remove
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>

                        <Separator />

                        <div className="space-y-3">
                          <h3 className="text-gray-900" style={{ fontSize: '16px' }}>
                            Patient Impact Metrics
                          </h3>

                          <div className="grid grid-cols-2 gap-3" style={{ gap: 'var(--space-3)' }}>
                            <div className="p-4 bg-gray-50 rounded-lg">
                              <div className="text-gray-600 mb-1" style={{ fontSize: '12px' }}>
                                Total Patients
                              </div>
                              <div className="text-gray-900" style={{ fontSize: '24px' }}>
                                {mapping.patientCount}
                              </div>
                            </div>

                            <div className="p-4 bg-gray-50 rounded-lg">
                              <div className="text-gray-600 mb-1" style={{ fontSize: '12px' }}>
                                Records Affected
                              </div>
                              <div className="text-gray-900" style={{ fontSize: '24px' }}>
                                156
                              </div>
                            </div>

                            <div className="p-4 bg-gray-50 rounded-lg">
                              <div className="text-gray-600 mb-1" style={{ fontSize: '12px' }}>
                                Frequency (Last 30d)
                              </div>
                              <div className="text-gray-900" style={{ fontSize: '24px' }}>
                                80
                              </div>
                            </div>

                            <div className="p-4 bg-gray-50 rounded-lg">
                              <div className="text-gray-600 mb-1" style={{ fontSize: '12px' }}>
                                Data Quality Score
                              </div>
                              <div className="text-gray-900" style={{ fontSize: '24px' }}>
                                94%
                              </div>
                            </div>
                          </div>
                        </div>

                        <Separator />

                        <div className="space-y-3">
                          <h3 className="text-gray-900" style={{ fontSize: '16px' }}>
                            Frequency Analysis
                          </h3>

                          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                            <div className="space-y-2">
                              <div
                                className="flex items-center justify-between"
                                style={{ fontSize: '14px' }}
                              >
                                <span className="text-gray-700">Emergency Department</span>
                                <span className="text-gray-900">45%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                  className="bg-blue-600 h-2 rounded-full"
                                  style={{ width: '45%' }}
                                ></div>
                              </div>
                            </div>

                            <div className="space-y-2 mt-3">
                              <div
                                className="flex items-center justify-between"
                                style={{ fontSize: '14px' }}
                              >
                                <span className="text-gray-700">Cardiology</span>
                                <span className="text-gray-900">35%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                  className="bg-blue-600 h-2 rounded-full"
                                  style={{ width: '35%' }}
                                ></div>
                              </div>
                            </div>

                            <div className="space-y-2 mt-3">
                              <div
                                className="flex items-center justify-between"
                                style={{ fontSize: '14px' }}
                              >
                                <span className="text-gray-700">Primary Care</span>
                                <span className="text-gray-900">20%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                  className="bg-blue-600 h-2 rounded-full"
                                  style={{ width: '20%' }}
                                ></div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </TabsContent>

                    {/* Audit Trail Tab */}
                    <TabsContent value="audit" className="mt-0">
                      <div className="space-y-4">
                        <div>
                          <h3 className="text-gray-900 mb-2" style={{ fontSize: '16px' }}>
                            Complete Action History
                          </h3>
                          <p className="text-gray-600 mb-4" style={{ fontSize: '14px' }}>
                            Full audit trail with timestamps and provenance
                          </p>
                        </div>

                        <div className="space-y-3">
                          {mockAuditTrail.map((event, index) => (
                            <div key={event.id} className="relative">
                              {index < mockAuditTrail.length - 1 && (
                                <div className="absolute left-5 top-12 bottom-0 w-0.5 bg-gray-200"></div>
                              )}

                              <div className="flex gap-4" style={{ gap: 'var(--space-4)' }}>
                                <div className="flex-shrink-0 w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center">
                                  <Check className="w-5 h-5 text-teal-600" />
                                </div>

                                <div className="flex-1 pb-6">
                                  <div
                                    className="flex items-start justify-between gap-3 mb-2"
                                    style={{ gap: 'var(--space-3)' }}
                                  >
                                    <div>
                                      <h4 className="text-gray-900" style={{ fontSize: '14px' }}>
                                        {event.action}
                                      </h4>
                                      <div
                                        className="flex items-center gap-2 mt-1"
                                        style={{ gap: 'var(--space-2)' }}
                                      >
                                        <span
                                          className="text-gray-600"
                                          style={{ fontSize: '12px' }}
                                        >
                                          <User className="w-3 h-3 inline mr-1" />
                                          {event.actor}
                                        </span>
                                        <span className="text-gray-400">•</span>
                                        <span
                                          className="text-gray-600"
                                          style={{ fontSize: '12px' }}
                                        >
                                          {event.site}
                                        </span>
                                      </div>
                                    </div>

                                    <div
                                      className="text-gray-500 text-right"
                                      style={{ fontSize: '12px' }}
                                    >
                                      <Clock className="w-3 h-3 inline mr-1" />
                                      {event.timestamp}
                                    </div>
                                  </div>

                                  <p className="text-gray-700 mb-2" style={{ fontSize: '14px' }}>
                                    {event.details}
                                  </p>

                                  <div
                                    className="flex items-center gap-2"
                                    style={{ gap: 'var(--space-2)' }}
                                  >
                                    <Badge
                                      variant="outline"
                                      className="font-mono"
                                      style={{ fontSize: '11px' }}
                                    >
                                      {event.correlationId}
                                    </Badge>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => handleCopyCorrelationId(event.correlationId)}
                                      className="h-6 px-2"
                                    >
                                      <Copy className="w-3 h-3" />
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </TabsContent>

                    {/* Alternatives Tab */}
                    <TabsContent value="alternatives" className="mt-0">
                      <div className="space-y-4">
                        <div>
                          <h3 className="text-gray-900 mb-2" style={{ fontSize: '16px' }}>
                            AI-Suggested Alternatives
                          </h3>
                          <p className="text-gray-600 mb-4" style={{ fontSize: '14px' }}>
                            Other mapping options based on usage patterns
                          </p>
                        </div>

                        <div className="space-y-3">
                          {mockAlternatives.map((alt, idx) => (
                            <div
                              key={idx}
                              className="p-4 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
                            >
                              <div
                                className="flex items-start justify-between gap-3 mb-3"
                                style={{ gap: 'var(--space-3)' }}
                              >
                                <div className="flex-1">
                                  {alt.mappingType === 'diagnostic-code' ? (
                                    <div>
                                      <div
                                        className="flex items-center gap-2 mb-1"
                                        style={{ gap: 'var(--space-2)' }}
                                      >
                                        <Badge
                                          className="bg-teal-100 text-teal-700 border-teal-300"
                                          style={{ fontSize: '11px' }}
                                        >
                                          {alt.system}
                                        </Badge>
                                        <span
                                          className="font-mono text-gray-900"
                                          style={{ fontSize: '14px' }}
                                        >
                                          {alt.code}
                                        </span>
                                      </div>
                                      <p className="text-gray-700" style={{ fontSize: '14px' }}>
                                        {alt.description}
                                      </p>
                                    </div>
                                  ) : (
                                    <div>
                                      <div
                                        className="flex items-center gap-2 mb-1"
                                        style={{ gap: 'var(--space-2)' }}
                                      >
                                        <Badge
                                          className="bg-blue-100 text-blue-700 border-blue-300"
                                          style={{ fontSize: '11px' }}
                                        >
                                          Field Mapping
                                        </Badge>
                                      </div>
                                      <p
                                        className="font-mono text-gray-900"
                                        style={{ fontSize: '14px' }}
                                      >
                                        {alt.field} {alt.relation} {alt.value}
                                      </p>
                                    </div>
                                  )}
                                </div>

                                <div className="text-right">
                                  <div className="text-gray-900 mb-1" style={{ fontSize: '14px' }}>
                                    {alt.confidence}% confidence
                                  </div>
                                  <div className="text-gray-500" style={{ fontSize: '12px' }}>
                                    {alt.usageCount} uses
                                  </div>
                                </div>
                              </div>

                              <p className="text-gray-600 mb-3 italic" style={{ fontSize: '14px' }}>
                                {alt.reasoning}
                              </p>

                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleApplyAlternative(alt)}
                                style={{ fontSize: '12px', gap: 'var(--space-2)' }}
                              >
                                <Check className="w-3 h-3" />
                                Apply This Mapping
                              </Button>
                            </div>
                          ))}
                        </div>
                      </div>
                    </TabsContent>
                  </div>
                </ScrollArea>
              </div>
            </Tabs>
          )}
        </SheetContent>
      </Sheet>

      {/* Semantic Explorer Modal */}
      <SemanticExplorerModal
        open={semanticModalOpen}
        onOpenChange={setSemanticModalOpen}
        centralTerm={mapping.emrTerm}
        examples={semanticExamples}
        onUpdate={updatedExamples => {
          setSemanticExamples(updatedExamples);
          toast.success('Semantic mappings updated');
        }}
      />

      {/* Remove Snippet Dialog */}
      <AlertDialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this example?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove &quot;{snippetToRemove?.context.substring(0, 50)}...&quot; from the mapping
              evidence. This action will be logged in the audit trail.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleConfirmRemove('discard')}
              className="bg-red-600 hover:bg-red-700"
            >
              Remove Example
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Full Chart View Modal */}
      {selectedSnippet && (
        <FullChartView
          open={fullChartOpen}
          onOpenChange={nextOpen => {
            setFullChartOpen(nextOpen);
            if (!nextOpen) setSelectedSnippet(null);
          }}
          patientId="PT-2024-089"
          highlightTerm={mapping.emrTerm}
        />
      )}
    </>
  );
}
