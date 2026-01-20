import { Badge } from '@/components/ui/badge';
import { Link } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MappingDisplayProps {
    snomedCodes?: string[];
    fieldMapping?: {
        field: string;
        relation: string;
        value: string;
    } | null;
    className?: string;
}

export function MappingDisplay({ snomedCodes, fieldMapping, className }: MappingDisplayProps) {
    if (!snomedCodes?.length && !fieldMapping) {
        return null;
    }

    return (
        <div className={cn('flex flex-wrap items-center gap-2 mt-3 p-2 bg-gray-50 rounded-md border border-gray-100', className)}>
            <Link className="h-4 w-4 text-teal-600" />

            {/* SNOMED Codes */}
            <div className="flex gap-1">
                {snomedCodes?.map(code => (
                    <Badge key={code} variant="outline" className="text-xs bg-white text-gray-700 border-gray-200 font-mono">
                        SNOMED: {code}
                    </Badge>
                ))}
            </div>

            {/* Field Mapping */}
            {fieldMapping && (
                <div className="flex items-center gap-1.5 text-xs text-gray-700">
                    {snomedCodes?.length ? <span className="text-gray-300">|</span> : null}
                    <span className="font-medium text-purple-700">{fieldMapping.field}</span>
                    <span className="text-gray-400 font-light">{fieldMapping.relation}</span>
                    <span className="font-medium text-indigo-700">{fieldMapping.value}</span>
                </div>
            )}
        </div>
    );
}
