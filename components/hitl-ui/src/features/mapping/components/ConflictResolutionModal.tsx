import { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AlertTriangle, Check, TrendingUp, Shield } from 'lucide-react';

interface Mapping {
  id: string;
  emrTerm: string;
  patientCount: number;
  conflictDetails?: {
    siteA: { code: string; system: string };
    siteB: { code: string; system: string };
  };
}

interface ConflictResolutionModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mapping: Mapping;
  onResolve: (data: {
    selectedMapping: 'siteA' | 'siteB';
    rationale: string;
    applyScope: 'site-only' | 'align-network';
  }) => void;
}

interface ConflictOption {
  id: 'siteA' | 'siteB';
  site: string;
  code: string;
  system: string;
  description: string;
  usageCount: number;
  recommended?: boolean;
}

const mockConflictOptions: ConflictOption[] = [
  {
    id: 'siteA',
    site: 'Boston General Hospital',
    code: 'C0020538',
    system: 'UMLS',
    description: 'Hypertensive disease',
    usageCount: 1247,
    recommended: true,
  },
  {
    id: 'siteB',
    site: 'Cleveland Clinic',
    code: 'C0001234',
    system: 'UMLS',
    description: 'High blood pressure',
    usageCount: 456,
  },
];

export function ConflictResolutionModal({
  open,
  onOpenChange,
  mapping,
  onResolve,
}: ConflictResolutionModalProps) {
  const [selectedMapping, setSelectedMapping] = useState<'siteA' | 'siteB'>('siteA');
  const [rationale, setRationale] = useState('');
  const [applyScope, setApplyScope] = useState<'site-only' | 'align-network'>('site-only');
  const prevOpenRef = useRef(open);

  useEffect(() => {
    // Only reset when transitioning from closed to open
    if (open && !prevOpenRef.current) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Reset state when modal opens
      setSelectedMapping('siteA');
      setRationale('');
      setApplyScope('site-only');
    }
    prevOpenRef.current = open;
  }, [open]);

  const handleResolve = () => {
    if (!rationale.trim()) return;

    onResolve({
      selectedMapping,
      rationale,
      applyScope,
    });
  };

  const canResolve = rationale.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl p-0 flex flex-col h-[90vh]" style={{ gap: 0 }}>
        <DialogTitle className="sr-only">Resolve Mapping Conflict: {mapping.emrTerm}</DialogTitle>
        <DialogDescription className="sr-only">
          Choose the correct mapping to resolve the conflict between different sites
        </DialogDescription>

        {/* Header */}
        <div className="px-6 py-4 border-b bg-red-50 flex-shrink-0">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-red-100 rounded">
              <AlertTriangle className="w-5 h-5 text-red-600" />
            </div>
            <div className="flex-1">
              <h3
                className="text-gray-900 font-semibold flex items-center gap-2"
                style={{ fontSize: '18px' }}
              >
                Resolve Mapping Conflict: <span className="text-red-700">{mapping.emrTerm}</span>
              </h3>
              <p className="text-red-600" style={{ fontSize: '14px' }}>
                Different sites are using conflicting mappings for this term
              </p>
            </div>
          </div>

          <div className="p-3 bg-white border border-red-200 rounded-lg">
            <p className="text-gray-600" style={{ fontSize: '12px' }}>
              <strong>{mapping.patientCount} patients</strong> cannot be auto-processed until this
              conflict is resolved
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ScrollArea className="h-full">
            <div className="p-6 space-y-6">
              {/* Conflicting Mappings */}
              <div className="space-y-3">
                <Label style={{ fontSize: '14px' }}>Select Correct Mapping</Label>

                <div className="border rounded-lg overflow-hidden">
                  {/* Table Header */}
                  <div
                    className="bg-gray-50 border-b grid grid-cols-12 gap-4 px-4 py-2"
                    style={{ fontSize: '12px' }}
                  >
                    <div className="col-span-1"></div>
                    <div className="col-span-3 font-semibold text-gray-700">Site</div>
                    <div className="col-span-3 font-semibold text-gray-700">Code</div>
                    <div className="col-span-3 font-semibold text-gray-700">Description</div>
                    <div className="col-span-2 font-semibold text-gray-700">Usage</div>
                  </div>

                  {/* Table Rows */}
                  {mockConflictOptions.map(option => (
                    <button
                      key={option.id}
                      onClick={() => setSelectedMapping(option.id)}
                      className={`w-full grid grid-cols-12 gap-4 px-4 py-3 border-b last:border-b-0 text-left transition-colors ${
                        selectedMapping === option.id
                          ? 'bg-teal-50 border-teal-200'
                          : 'hover:bg-gray-50'
                      } ${option.recommended ? 'bg-green-50' : ''}`}
                    >
                      <div className="col-span-1 flex items-center">
                        {selectedMapping === option.id ? (
                          <div className="w-5 h-5 bg-teal-600 rounded-full flex items-center justify-center">
                            <div className="w-2 h-2 bg-white rounded-full"></div>
                          </div>
                        ) : (
                          <div className="w-5 h-5 border-2 border-gray-300 rounded-full"></div>
                        )}
                      </div>

                      <div className="col-span-3 flex items-center gap-2">
                        <span className="text-gray-900" style={{ fontSize: '14px' }}>
                          {option.site}
                        </span>
                        {option.recommended && (
                          <Badge
                            className="bg-green-100 text-green-700 border-green-300"
                            style={{ fontSize: '10px' }}
                          >
                            Recommended
                          </Badge>
                        )}
                      </div>

                      <div className="col-span-3 flex items-center">
                        <div>
                          <Badge
                            className="bg-blue-100 text-blue-700 border-blue-300 mb-1"
                            style={{ fontSize: '10px' }}
                          >
                            {option.system}
                          </Badge>
                          <div className="font-mono text-gray-900" style={{ fontSize: '13px' }}>
                            {option.code}
                          </div>
                        </div>
                      </div>

                      <div className="col-span-3 flex items-center">
                        <span className="text-gray-700" style={{ fontSize: '14px' }}>
                          {option.description}
                        </span>
                      </div>

                      <div className="col-span-2 flex items-center">
                        <div
                          className="flex items-center gap-1 text-gray-600"
                          style={{ fontSize: '12px' }}
                        >
                          <TrendingUp className="w-3 h-3" />
                          {option.usageCount.toLocaleString()}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-green-900 flex items-start gap-2" style={{ fontSize: '12px' }}>
                    <Check className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <span>
                      The recommended mapping has higher usage across the network and better
                      semantic precision
                    </span>
                  </p>
                </div>
              </div>

              {/* Rationale */}
              <div className="space-y-3">
                <Label
                  htmlFor="rationale"
                  className="flex items-center gap-2"
                  style={{ fontSize: '14px' }}
                >
                  Resolution Reason
                  <Badge variant="outline" style={{ fontSize: '11px' }}>
                    Required
                  </Badge>
                </Label>
                <Textarea
                  id="rationale"
                  value={rationale}
                  onChange={e => setRationale(e.target.value)}
                  placeholder="Explain why you chose this mapping and how it resolves the conflict..."
                  rows={4}
                  className="resize-none"
                  style={{ fontSize: '14px' }}
                />
                <p className="text-gray-500" style={{ fontSize: '12px' }}>
                  This decision will be logged to the audit trail with full context
                </p>
              </div>

              {/* Apply Scope */}
              <div className="space-y-3">
                <Label style={{ fontSize: '14px' }}>Application Scope</Label>

                <RadioGroup
                  value={applyScope}
                  onValueChange={value => setApplyScope(value as 'site-only' | 'align-network')}
                >
                  <div className="space-y-3">
                    <div className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                      <RadioGroupItem value="site-only" id="site-only" className="mt-1" />
                      <Label htmlFor="site-only" className="flex-1 cursor-pointer">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="font-semibold text-gray-900"
                            style={{ fontSize: '14px' }}
                          >
                            Apply to this site only
                          </span>
                          <Badge
                            className="bg-blue-100 text-blue-700 border-blue-300"
                            style={{ fontSize: '10px' }}
                          >
                            Safe
                          </Badge>
                        </div>
                        <p className="text-gray-600" style={{ fontSize: '12px' }}>
                          Use this mapping only at your site. Other sites will keep their existing
                          mappings.
                        </p>
                      </Label>
                    </div>

                    <div className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-gray-50 transition-colors">
                      <RadioGroupItem value="align-network" id="align-network" className="mt-1" />
                      <Label htmlFor="align-network" className="flex-1 cursor-pointer">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className="font-semibold text-gray-900"
                            style={{ fontSize: '14px' }}
                          >
                            Align with network
                          </span>
                          <Badge
                            className="bg-orange-100 text-orange-700 border-orange-300"
                            style={{ fontSize: '10px' }}
                          >
                            Network-wide
                          </Badge>
                        </div>
                        <p className="text-gray-600" style={{ fontSize: '12px' }}>
                          Suggest this mapping to all sites in the network to improve consistency.
                        </p>
                      </Label>
                    </div>
                  </div>
                </RadioGroup>
              </div>

              {/* Impact Warning */}
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-amber-900 font-semibold mb-1" style={{ fontSize: '14px' }}>
                      Resolution Impact
                    </p>
                    <ul className="text-amber-800 space-y-1" style={{ fontSize: '12px' }}>
                      <li>
                        • {mapping.patientCount} patients will be unblocked for auto-processing
                      </li>
                      <li>• This decision will be permanently logged with full audit trail</li>
                      {applyScope === 'align-network' && (
                        <li>• Other sites will be notified to review this mapping suggestion</li>
                      )}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </ScrollArea>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2 text-gray-600" style={{ fontSize: '12px' }}>
            <Shield className="w-3 h-3" />
            Resolution will be cryptographically signed
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              style={{ fontSize: '14px' }}
            >
              Cancel
            </Button>

            <Button
              onClick={handleResolve}
              disabled={!canResolve}
              variant="destructive"
              className="gap-2"
              style={{ fontSize: '14px' }}
            >
              <Check className="w-4 h-4" />
              Save Resolution
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
