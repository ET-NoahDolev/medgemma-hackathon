import { useState } from 'react';
import { StatusTag, StatusType } from '@/components/common/StatusTag';
import { Check, X, AlertCircle, FileText, Edit2, RotateCcw } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';

interface CriteriaItemProps {
  id: string;
  type: 'inclusion' | 'exclusion';
  criterion: string;
  status: StatusType;
  evidence?: string[];
  confidence?: number;
  onCorrect?: (correctedStatus: StatusType, rationale: string) => void;
  onEdit?: () => void;
  correctionHistory?: Array<{
    timestamp: string;
    actor: string;
    oldStatus: StatusType;
    newStatus: StatusType;
    rationale: string;
  }>;
}

export function CriteriaItem({
  id,
  type,
  criterion,
  status,
  evidence = [],
  confidence: _confidence,
  onCorrect,
  onEdit,
  correctionHistory = [],
}: CriteriaItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [rationale, setRationale] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<StatusType>(status);

  const handleSubmitCorrection = () => {
    if (onCorrect && rationale.trim()) {
      onCorrect(selectedStatus, rationale);
      setIsEditing(false);
      setRationale('');
    }
  };

  const getIcon = () => {
    switch (status) {
      case 'matched':
        return <Check className="w-4 h-4 text-green-600" />;
      case 'not-matched':
        return <X className="w-4 h-4 text-red-600" />;
      case 'needs-review':
        return <AlertCircle className="w-4 h-4 text-yellow-600" />;
      default:
        return <AlertCircle className="w-4 h-4 text-blue-600" />;
    }
  };

  return (
    <div className="border-b border-gray-200 py-4 last:border-b-0">
      <div className="flex items-start gap-3">
        <div className="mt-1">{getIcon()}</div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs px-2 py-0.5 rounded ${
                    type === 'inclusion' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}
                >
                  {type === 'inclusion' ? 'I' : 'E'}
                  {id}
                </span>
                <p className="text-sm text-gray-900">{criterion}</p>
              </div>

              {evidence.length > 0 && (
                <div className="mt-2 flex items-center gap-2">
                  <FileText className="w-3 h-3 text-gray-400" />
                  <span className="text-xs text-gray-600">
                    {evidence.length} evidence snippet{evidence.length > 1 ? 's' : ''}
                  </span>
                </div>
              )}

              {correctionHistory.length > 0 && (
                <div className="mt-2 p-2 bg-blue-50 rounded text-xs text-blue-700">
                  <div className="flex items-center gap-1 mb-1">
                    <RotateCcw className="w-3 h-3" />
                    <span>
                      Corrected {correctionHistory.length} time
                      {correctionHistory.length > 1 ? 's' : ''}
                    </span>
                  </div>
                  <p className="text-blue-600">
                    Last: {correctionHistory[0].actor} on {correctionHistory[0].timestamp}
                  </p>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <StatusTag status={status} />
              {onEdit && !isEditing && (
                <button
                  onClick={onEdit}
                  className="p-1 text-gray-400 hover:text-gray-600 rounded"
                  title="Edit criterion"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
              )}
              {onCorrect && !onEdit && !isEditing && (
                <button
                  onClick={() => setIsEditing(true)}
                  className="p-1 text-gray-400 hover:text-gray-600 rounded"
                  title="Correct assessment"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {isEditing && (
            <div className="mt-3 p-3 bg-gray-50 rounded-lg space-y-3">
              <div>
                <label className="text-xs text-gray-600 block mb-2">Correct Status</label>
                <div className="flex gap-2 flex-wrap">
                  {(['matched', 'likely', 'needs-review', 'not-matched'] as StatusType[]).map(s => (
                    <button
                      key={s}
                      onClick={() => setSelectedStatus(s)}
                      className={`px-3 py-1 rounded-md text-xs border transition-all ${
                        selectedStatus === s
                          ? 'border-teal-500 bg-teal-50 text-teal-700'
                          : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
                      }`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs text-gray-600 block mb-2">Rationale (required)</label>
                <Textarea
                  value={rationale}
                  onChange={e => setRationale(e.target.value)}
                  placeholder="Explain why this correction is needed..."
                  className="text-sm"
                  rows={2}
                />
              </div>

              <div className="flex gap-2">
                <Button
                  onClick={handleSubmitCorrection}
                  disabled={!rationale.trim()}
                  size="sm"
                  className="bg-teal-600 hover:bg-teal-700"
                >
                  Submit Correction
                </Button>
                <Button
                  onClick={() => {
                    setIsEditing(false);
                    setRationale('');
                    setSelectedStatus(status);
                  }}
                  variant="outline"
                  size="sm"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
