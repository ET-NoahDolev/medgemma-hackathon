import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Info } from 'lucide-react';

interface ConfidenceChipProps {
  confidence: number;
  model?: string;
  version?: string;
  dataSource?: string;
  evidenceLink?: string;
}

export function ConfidenceChip({
  confidence,
  model = 'ElixirAI-v2.1',
  version = '2024.10',
  dataSource,
  evidenceLink,
}: ConfidenceChipProps) {
  const getColor = () => {
    if (confidence >= 0.9) return 'bg-green-100 text-green-700 border-green-300';
    if (confidence >= 0.7) return 'bg-blue-100 text-blue-700 border-blue-300';
    if (confidence >= 0.5) return 'bg-yellow-100 text-yellow-700 border-yellow-300';
    return 'bg-red-100 text-red-700 border-red-300';
  };

  const getIconColor = () => {
    if (confidence >= 0.9) return 'text-green-700 dark:text-green-300';
    if (confidence >= 0.7) return 'text-blue-700 dark:text-blue-300';
    if (confidence >= 0.5) return 'text-yellow-700 dark:text-yellow-300';
    return 'text-red-700 dark:text-red-300';
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border ${getColor()} cursor-help`}
          >
            <span className="text-xs">{Math.round(confidence * 100)}%</span>
            <Info className={`w-3 h-3 ${getIconColor()}`} />
          </span>
        </TooltipTrigger>
        <TooltipContent className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-lg p-4 max-w-xs confidence-tooltip">
          <div className="space-y-2.5">
            <div>
              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-0.5">
                Confidence Score
              </p>
              <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                {(confidence * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-0.5">Model</p>
              <p className="text-sm text-gray-900 dark:text-gray-100">{model}</p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-0.5">Version</p>
              <p className="text-sm text-gray-900 dark:text-gray-100">{version}</p>
            </div>
            {dataSource && (
              <div>
                <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-0.5">
                  Data Source
                </p>
                <p className="text-sm text-gray-900 dark:text-gray-100">{dataSource}</p>
              </div>
            )}
            {evidenceLink && (
              <button className="text-xs text-teal-600 dark:text-teal-400 hover:text-teal-700 dark:hover:text-teal-300 underline mt-2 font-medium">
                View Evidence →
              </button>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
