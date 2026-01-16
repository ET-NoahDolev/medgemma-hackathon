import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import {
  Clock,
  User,
  FileText,
  Database,
  CheckCircle2,
  Edit2,
  AlertCircle,
  Download,
  Copy,
  Filter,
} from 'lucide-react';

interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  entity: string;
  entityId: string;
  details: string;
  type: 'approval' | 'correction' | 'sync' | 'mapping' | 'validation';
}

const mockEvents: AuditEvent[] = [
  {
    id: 'AUD-2024-1030-001',
    timestamp: '2024-10-30 14:32:15',
    actor: 'Dr. Sarah Chen',
    action: 'Approved patient for screening',
    entity: 'Patient',
    entityId: 'PT-2024-0042',
    details: 'All I/E criteria met. Confidence: 94%. No manual corrections required.',
    type: 'approval',
  },
  {
    id: 'AUD-2024-1030-002',
    timestamp: '2024-10-30 14:28:43',
    actor: 'Dr. Sarah Chen',
    action: 'Corrected criterion assessment',
    entity: 'Criterion',
    entityId: 'I3 (PT-2024-0042)',
    details:
      'Changed status from "needs-review" to "matched". Rationale: Verified no colonoscopy in procedure history.',
    type: 'correction',
  },
  {
    id: 'AUD-2024-1030-003',
    timestamp: '2024-10-30 14:15:22',
    actor: 'System (ElixirAI)',
    action: 'Applied mapping reuse',
    entity: 'Mapping',
    entityId: 'MAP-HYP-Site003-v2',
    details: 'Reused hypertension exclusion mapping from Site 003. Confidence: 87%.',
    type: 'mapping',
  },
  {
    id: 'AUD-2024-1030-004',
    timestamp: '2024-10-30 13:45:10',
    actor: 'Dr. Sarah Chen',
    action: 'Synced to Veeva EDC',
    entity: 'EDC Sync',
    entityId: 'EDC-2024-1030-001',
    details: 'Synced 8 fields with 2 overrides. Signature captured. Payload ID: VEE-4872.',
    type: 'sync',
  },
  {
    id: 'AUD-2024-1030-005',
    timestamp: '2024-10-30 13:12:33',
    actor: 'Dr. Sarah Chen',
    action: 'Completed validation task',
    entity: 'Validation',
    entityId: 'VAL-001',
    details: 'Low-risk approval for routine data refresh. Patient: PT-2024-0050.',
    type: 'validation',
  },
];

const typeConfig = {
  approval: { icon: CheckCircle2, color: 'bg-green-100 text-green-700' },
  correction: { icon: Edit2, color: 'bg-blue-100 text-blue-700' },
  sync: { icon: Database, color: 'bg-purple-100 text-purple-700' },
  mapping: { icon: AlertCircle, color: 'bg-orange-100 text-orange-700' },
  validation: { icon: CheckCircle2, color: 'bg-teal-100 text-teal-700' },
};

export function AuditTimeline() {
  const [events] = useState<AuditEvent[]>(mockEvents);
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredEvents = events.filter(event => {
    const matchesType = filterType === 'all' || event.type === filterType;
    const matchesSearch =
      event.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
      event.entityId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      event.actor.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesType && matchesSearch;
  });

  const copyEventId = (id: string) => {
    navigator.clipboard.writeText(id);
  };

  const exportAudit = () => {
    // TODO: Implement CSV export functionality
  };

  return (
    <Sheet>
      <SheetTrigger asChild>
        <button className="cockpit-hud-action-btn" title="Audit Trail" aria-label="Audit Trail">
          <Clock className="cockpit-hud-icon" />
        </button>
      </SheetTrigger>
      <SheetContent className="w-[600px] sm:max-w-[600px]">
        <SheetHeader>
          <SheetTitle>Audit Timeline</SheetTitle>
          <SheetDescription>
            View and filter all system events including approvals, corrections, EDC syncs, and
            mappings.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-4">
          {/* Filters */}
          <div className="space-y-3">
            <Input
              placeholder="Search by action, entity, or actor..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full"
            />

            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-500" />
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Filter by type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Events</SelectItem>
                  <SelectItem value="approval">Approvals</SelectItem>
                  <SelectItem value="correction">Corrections</SelectItem>
                  <SelectItem value="sync">EDC Syncs</SelectItem>
                  <SelectItem value="mapping">Mapping Events</SelectItem>
                  <SelectItem value="validation">Validations</SelectItem>
                </SelectContent>
              </Select>

              <Button variant="outline" size="sm" onClick={exportAudit}>
                <Download className="w-4 h-4 mr-1" />
                Export
              </Button>
            </div>
          </div>

          {/* Event List */}
          <ScrollArea className="h-[calc(100vh-280px)]">
            <div className="space-y-3">
              {filteredEvents.map(event => {
                const TypeIcon = typeConfig[event.type].icon;

                return (
                  <div
                    key={event.id}
                    className="p-4 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-all"
                  >
                    <div className="flex items-start gap-3">
                      <div className={`p-2 rounded-lg ${typeConfig[event.type].color}`}>
                        <TypeIcon className="w-4 h-4" />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <h3 className="text-sm text-gray-900">{event.action}</h3>
                          <button
                            onClick={() => copyEventId(event.id)}
                            className="flex-shrink-0 p-1 text-gray-400 hover:text-gray-600"
                            title="Copy event ID"
                          >
                            <Copy className="w-3 h-3" />
                          </button>
                        </div>

                        <div className="space-y-1 text-xs text-gray-600 mb-2">
                          <div className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            <span>{event.actor}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            <span>{event.timestamp}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <FileText className="w-3 h-3" />
                            <span>
                              {event.entity}: {event.entityId}
                            </span>
                          </div>
                        </div>

                        <p className="text-xs text-gray-700 leading-relaxed">{event.details}</p>

                        <div className="mt-2">
                          <Badge variant="outline" className="text-xs font-mono">
                            {event.id}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}

              {filteredEvents.length === 0 && (
                <div className="text-center py-8">
                  <p className="text-sm text-gray-500">No events match your filters</p>
                </div>
              )}
            </div>
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>
  );
}
