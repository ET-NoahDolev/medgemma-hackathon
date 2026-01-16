import { Check, AlertCircle, Info, Sparkles } from 'lucide-react';

export type StatusType = 'matched' | 'likely' | 'needs-review' | 'not-matched' | 'ai-suggested';

interface StatusTagProps {
  status: StatusType;
  label?: string;
  showIcon?: boolean;
}

const statusConfig = {
  matched: {
    className: 'tag success',
    icon: Check,
    defaultLabel: 'Matched',
  },
  likely: {
    className: 'tag info',
    icon: Info,
    defaultLabel: 'Likely',
  },
  'needs-review': {
    className: 'tag warn',
    icon: AlertCircle,
    defaultLabel: 'Needs Review',
  },
  'not-matched': {
    className: 'tag danger',
    icon: AlertCircle,
    defaultLabel: 'Not Matched',
  },
  'ai-suggested': {
    className: 'tag ai',
    icon: Sparkles,
    defaultLabel: 'AI Suggested',
  },
};

export function StatusTag({ status, label, showIcon = true }: StatusTagProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  // Icon colors should inherit from parent, but we'll ensure they're visible
  const iconColorClass = {
    matched: 'text-green-700 dark:text-green-300',
    likely: 'text-blue-700 dark:text-blue-300',
    'needs-review': 'text-yellow-700 dark:text-yellow-300',
    'not-matched': 'text-red-700 dark:text-red-300',
    'ai-suggested': 'text-orange-700 dark:text-orange-300',
  }[status];

  return (
    <span className={`${config.className} inline-flex items-center gap-1 px-2 py-1 rounded-md`}>
      {showIcon && <Icon className={`w-3 h-3 ${iconColorClass}`} />}
      <span className="text-xs">{label || config.defaultLabel}</span>
    </span>
  );
}
