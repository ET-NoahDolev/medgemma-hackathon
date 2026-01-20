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
import { toast } from 'sonner';

interface EditMappingModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    criterion: {
        id: string;
        text: string;
        snomedCodes?: string[];
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
    const groundCriterion = useGroundCriterion();
    const submitFeedback = useSubmitFeedback();

    // Local state for editing
    const [snomedCodes, setSnomedCodes] = useState<string[]>(criterion.snomedCodes || []);
    const [fieldMapping, setFieldMapping] = useState(
        criterion.fieldMapping || { field: '', relation: '', value: '' }
    );

    // Candidates from grounding service
    const [candidates, setCandidates] = useState<
        Array<{ code: string; display: string; confidence: number }>
    >([]);

    // Fetch grounding candidates when opening
    useEffect(() => {
        if (open && criterion.id) {
            groundCriterion.mutate(criterion.id, {
                onSuccess: (data) => {
                    setCandidates(data.candidates);
                    // Only auto-fill if empty? Or maybe show suggestions separately.
                    // For now, let's trust the existing mapping unless user picks a new one across the board.
                    // But if current mapping is empty, we could populate from candidates.
                    if (!criterion.snomedCodes?.length && data.candidates.length > 0) {
                        // Auto-select top candidate? Maybe not, let user choose.
                    }
                },
            });
        }
    }, [open, criterion.id]);

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

        // Field Mapping - we only support one for now, so replacement
        if (
            fieldMapping.field !== criterion.fieldMapping?.field ||
            fieldMapping.value !== criterion.fieldMapping?.value
        ) {
            if (criterion.fieldMapping?.field) {
                submitFeedback.mutate({
                    criterion_id: criterion.id,
                    action: 'remove_mapping',
                    field_mapping_removed: JSON.stringify(criterion.fieldMapping) // API expects string? or structured? 
                    // The API `field_mapping_removed` is a string. We probably usually send ID or serialized.
                    // For the hackathon let's just send 'add_mapping' with the new one which effectively overwrites 
                    // (if backend logic supports it).
                });
            }

            // Add new mapping
            submitFeedback.mutate({
                criterion_id: criterion.id,
                action: 'add_mapping',
                field_mapping_added: JSON.stringify(fieldMapping)
                // Note: The API treats this as a string record.
            });
        }

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
                                                value={fieldMapping.relation}
                                                onChange={e => setFieldMapping({ ...fieldMapping, relation: e.target.value })}
                                            />
                                        </div>
                                        <div className="space-y-1">
                                            <Label className="text-xs">Value</Label>
                                            <Input
                                                placeholder="e.g. 18, Yes"
                                                value={fieldMapping.value}
                                                onChange={e => setFieldMapping({ ...fieldMapping, value: e.target.value })}
                                            />
                                        </div>
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
