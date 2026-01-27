import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card } from '@/components/ui/card';
import { useState, useEffect } from 'react';
import { Loader2, X, Search } from 'lucide-react';
import { useGroundCriterion } from '@/hooks/useGroundCriterion';
import { useSubmitFeedback } from '@/hooks/useSubmitFeedback';
import { useEditCriterionMapping } from '@/hooks/useEditCriterionMapping';
import { toast } from 'sonner';

interface EditMappingModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    criterion: {
        id: string;
        text: string;
        snomedCodes?: string[];
        snomedCode?: string;
        entity?: string;
        umlsConcept?: string;
        umlsId?: string;
        relation?: string;
        value?: string;
        unit?: string;
        hitlEntity?: string;
        hitlUmlsConcept?: string;
        hitlUmlsId?: string;
        hitlSnomedCode?: string;
        hitlRelation?: string;
        hitlValue?: string;
        hitlUnit?: string;
        fieldMapping?: {
            field: string;
            relation: string;
            value: string;
        } | null;
    };
    onSave?: () => void;
}

export function EditMappingModal({
    open,
    onOpenChange,
    criterion,
    onSave,
}: EditMappingModalProps) {
    // protocolId not available here; invalidate all criteria queries after grounding.
    const groundCriterion = useGroundCriterion(null);
    const submitFeedback = useSubmitFeedback();
    const editMapping = useEditCriterionMapping();

    // Local state for editing
    const [snomedCodes, setSnomedCodes] = useState<string[]>(criterion.snomedCodes || []);
    const [fieldMapping, setFieldMapping] = useState(
        criterion.fieldMapping || { field: '', relation: '', value: '' }
    );
    const [entity, setEntity] = useState(criterion.hitlEntity ?? criterion.entity ?? '');
    const [relation, setRelation] = useState(criterion.hitlRelation ?? criterion.relation ?? '');
    const [value, setValue] = useState(criterion.hitlValue ?? criterion.value ?? '');
    const [unit, setUnit] = useState(criterion.hitlUnit ?? criterion.unit ?? '');
    const [umlsConcept, setUmlsConcept] = useState(
        criterion.hitlUmlsConcept ?? criterion.umlsConcept ?? ''
    );
    const [umlsId, setUmlsId] = useState(criterion.hitlUmlsId ?? criterion.umlsId ?? '');
    const [snomedCode, setSnomedCode] = useState(
        criterion.hitlSnomedCode ?? criterion.snomedCode ?? ''
    );

    // Candidates from grounding service
    const [candidates, setCandidates] = useState<
        Array<{ code: string; display: string; confidence: number }>
    >([]);

    // Fetch grounding candidates when opening (non-blocking)
    useEffect(() => {
        if (open && criterion.id) {
            // Open modal immediately, load candidates asynchronously
            groundCriterion.mutate(criterion.id, {
                onSuccess: (data) => {
                    setCandidates(data.candidates);
                },
                onError: () => {
                    toast.error('Grounding failed', {
                        description: 'Could not fetch SNOMED candidates. You can still edit manually.',
                    });
                },
            });
        }
    }, [open, criterion.id, groundCriterion]);

    useEffect(() => {
        setSnomedCodes(criterion.snomedCodes || []);
        setFieldMapping(criterion.fieldMapping || { field: '', relation: '', value: '' });
        setEntity(criterion.hitlEntity ?? criterion.entity ?? '');
        setRelation(criterion.hitlRelation ?? criterion.relation ?? '');
        setValue(criterion.hitlValue ?? criterion.value ?? '');
        setUnit(criterion.hitlUnit ?? criterion.unit ?? '');
        setUmlsConcept(criterion.hitlUmlsConcept ?? criterion.umlsConcept ?? '');
        setUmlsId(criterion.hitlUmlsId ?? criterion.umlsId ?? '');
        setSnomedCode(criterion.hitlSnomedCode ?? criterion.snomedCode ?? '');
    }, [criterion]);

    const handleAddCode = (code: string) => {
        if (!snomedCodes.includes(code)) {
            setSnomedCodes([...snomedCodes, code]);
        }
    };

    const handleRemoveCode = (code: string) => {
        setSnomedCodes(snomedCodes.filter((c) => c !== code));
    };

    const handleSave = () => {
        // We need to submit multiple feedbacks if multiple things changed?
        // Ideally we have a bulk update endpoint, but for now we might iterate.
        // Or we use the submitFeedback for 'edit_mapping' (but the API uses atomics add_code etc)
        // Actually the `submitFeedback` handles specific actions. The UI is editing the *state* directly via backend?
        // Wait, storage.set_snomed_codes is used in ground endpoints. 
        // The instructions say "HITL inputs... fine tune our model". 
        // Let's assume we use single atomic actions or just assume updating criterion metadata?
        // The API `submitFeedback` takes `snomed_code_added`, `snomed_code_removed`.
        // This implies we should diff.

        // Diffing Logic (Simulated for this hackathon speed)
        const added = snomedCodes.filter(c => !criterion.snomedCodes?.includes(c));
        const removed = criterion.snomedCodes?.filter(c => !snomedCodes.includes(c)) || [];

        added.forEach(code => {
            submitFeedback.mutate({
                criterion_id: criterion.id,
                action: 'add_code',
                snomed_code_added: code
            });
        });

        removed.forEach(code => {
            submitFeedback.mutate({
                criterion_id: criterion.id,
                action: 'remove_code',
                snomed_code_removed: code
            });
        });

        const mappingForSubmit = {
            field: fieldMapping.field,
            relation,
            value,
        };

        // Field Mapping - we only support one for now, so replacement
        if (
            mappingForSubmit.field !== criterion.fieldMapping?.field ||
            mappingForSubmit.value !== criterion.fieldMapping?.value ||
            mappingForSubmit.relation !== criterion.fieldMapping?.relation
        ) {
            if (criterion.fieldMapping?.field) {
                submitFeedback.mutate({
                    criterion_id: criterion.id,
                    action: 'remove_mapping',
                    field_mapping_removed: JSON.stringify(criterion.fieldMapping)
                });
            }

            // Add new mapping
            submitFeedback.mutate({
                criterion_id: criterion.id,
                action: 'add_mapping',
                field_mapping_added: JSON.stringify(mappingForSubmit)
            });
        }

        editMapping.mutate({
            criterionId: criterion.id,
            payload: {
                user: 'reviewer',
                edits: {
                    entity,
                    relation,
                    value,
                    unit,
                    umls_concept: umlsConcept,
                    umls_id: umlsId,
                    snomed_code: snomedCode,
                },
            },
        });

        toast.success('Mapping updated');
        onOpenChange(false);
        onSave?.();
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
                <DialogHeader>
                    <DialogTitle>Edit Mappings</DialogTitle>
                    <DialogDescription>
                        Associate this criterion with standardized SNOMED CT codes and clinical values.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 overflow-hidden flex flex-col gap-6 py-4">
                    <div className="bg-gray-50 p-3 rounded-md border border-gray-100 text-sm font-medium text-gray-800">
                        &quot;{criterion.text}&quot;
                    </div>

                    <div className="grid grid-cols-2 gap-6 h-full min-h-0">
                        {/* Left: Candidates */}
                        <div className="flex flex-col min-h-0 border-r pr-6">
                            <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                                Suggested SNOMED Codes
                                {groundCriterion.isPending && <Loader2 className="w-3 h-3 animate-spin" />}
                            </h4>
                            <ScrollArea className="flex-1 pr-3">
                                <div className="space-y-2">
                                    {candidates.map((candidate) => (
                                        <Card
                                            key={candidate.code}
                                            className="p-3 cursor-pointer hover:bg-slate-50 transition-colors border-l-4 border-l-transparent hover:border-l-indigo-500"
                                            onClick={() => handleAddCode(candidate.code)}
                                        >
                                            <div className="flex justify-between items-start gap-2">
                                                <div>
                                                    <p className="text-sm font-medium text-gray-900">{candidate.display}</p>
                                                    <p className="text-xs text-gray-500 mt-1 font-mono">{candidate.code}</p>
                                                </div>
                                                <Badge variant="secondary" className="text-[10px]">
                                                    {(candidate.confidence * 100).toFixed(0)}%
                                                </Badge>
                                            </div>
                                        </Card>
                                    ))}
                                    {!groundCriterion.isPending && candidates.length === 0 && (
                                        <p className="text-sm text-gray-500 italic">No suggestions found.</p>
                                    )}
                                </div>
                            </ScrollArea>
                        </div>

                        {/* Right: Selected Mapping */}
                        <div className="flex flex-col gap-6 overflow-y-auto">
                            {/* Selected Codes */}
                            <div>
                                <h4 className="text-sm font-semibold mb-3">Active SNOMED Codes</h4>
                                <div className="flex flex-wrap gap-2">
                                    {snomedCodes.map((code) => (
                                        <Badge key={code} className="pl-2 pr-1 py-1 gap-1" variant="secondary">
                                            {code}
                                            {/* Lookup display name? For now just code due to component simplicity */}
                                            <button
                                                onClick={() => handleRemoveCode(code)}
                                                className="hover:bg-gray-200 rounded-full p-0.5"
                                            >
                                                <X className="w-3 h-3" />
                                            </button>
                                        </Badge>
                                    ))}
                                    {snomedCodes.length === 0 && (
                                        <p className="text-sm text-gray-400 font-light">No codes selected</p>
                                    )}
                                </div>
                            </div>

                            {/* Field Mapping */}
                            <div className="space-y-4">
                                <h4 className="text-sm font-semibold">Structured Data Mapping</h4>
                                <div className="space-y-3">
                                    <div className="space-y-1">
                                        <Label className="text-xs">Entity</Label>
                                        <Input
                                            placeholder="e.g. Age"
                                            value={entity}
                                            onChange={e => setEntity(e.target.value)}
                                        />
                                        {criterion.entity && criterion.entity !== entity && (
                                            <div className="text-[11px] text-gray-500">AI: {criterion.entity}</div>
                                        )}
                                    </div>
                                    <div className="space-y-1">
                                        <Label className="text-xs">Field (Variable)</Label>
                                        <div className="relative">
                                            <Search className="absolute left-2 top-2.5 h-4 w-4 text-gray-400" />
                                            <Input
                                                className="pl-8"
                                                placeholder="e.g. Age, HbA1c"
                                                value={fieldMapping.field}
                                                onChange={e => setFieldMapping({ ...fieldMapping, field: e.target.value })}
                                            />
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="space-y-1">
                                            <Label className="text-xs">Relation</Label>
                                            <Input
                                                placeholder="e.g. >=, EQUAL"
                                                value={relation}
                                                onChange={e => {
                                                    setRelation(e.target.value);
                                                    setFieldMapping({ ...fieldMapping, relation: e.target.value });
                                                }}
                                            />
                                            {criterion.relation && criterion.relation !== relation && (
                                                <div className="text-[11px] text-gray-500">AI: {criterion.relation}</div>
                                            )}
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-xs">Value</Label>
                                            <Input
                                                placeholder="e.g. 18, Yes"
                                                value={value}
                                                onChange={e => {
                                                    setValue(e.target.value);
                                                    setFieldMapping({ ...fieldMapping, value: e.target.value });
                                                }}
                                            />
                                            {criterion.value && criterion.value !== value && (
                                                <div className="text-[11px] text-gray-500">AI: {criterion.value}</div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        <Label className="text-xs">Unit</Label>
                                        <Input
                                            placeholder="e.g. years"
                                            value={unit}
                                            onChange={e => setUnit(e.target.value)}
                                        />
                                        {criterion.unit && criterion.unit !== unit && (
                                            <div className="text-[11px] text-gray-500">AI: {criterion.unit}</div>
                                        )}
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="space-y-1">
                                            <Label className="text-xs">UMLS Concept</Label>
                                            <Input
                                                placeholder="e.g. Date of birth"
                                                value={umlsConcept}
                                                onChange={e => setUmlsConcept(e.target.value)}
                                            />
                                            {criterion.umlsConcept && criterion.umlsConcept !== umlsConcept && (
                                                <div className="text-[11px] text-gray-500">AI: {criterion.umlsConcept}</div>
                                            )}
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-xs">UMLS ID</Label>
                                            <Input
                                                placeholder="e.g. C0011002"
                                                value={umlsId}
                                                onChange={e => setUmlsId(e.target.value)}
                                            />
                                            {criterion.umlsId && criterion.umlsId !== umlsId && (
                                                <div className="text-[11px] text-gray-500">AI: {criterion.umlsId}</div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        <Label className="text-xs">Primary SNOMED Code</Label>
                                        <Input
                                            placeholder="e.g. 371273006"
                                            value={snomedCode}
                                            onChange={e => setSnomedCode(e.target.value)}
                                        />
                                        {criterion.snomedCode && criterion.snomedCode !== snomedCode && (
                                            <div className="text-[11px] text-gray-500">AI: {criterion.snomedCode}</div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={handleSave} disabled={submitFeedback.isPending}>
                        {submitFeedback.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                        Save Changes
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
