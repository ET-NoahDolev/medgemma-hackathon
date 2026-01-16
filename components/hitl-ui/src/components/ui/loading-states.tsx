import {
  Skeleton,
  SkeletonText,
  SkeletonCard,
  SkeletonAvatar,
  SkeletonButton,
} from '@/components/ui/skeleton';

/**
 * Loading states for common UI patterns
 * Use these to maintain consistency across the app
 */

/**
 * Patient card skeleton loader
 */
export function PatientCardSkeleton() {
  return (
    <div className="flex items-center gap-4 p-4 border border-gray-200 dark:border-gray-800 rounded-lg">
      <SkeletonAvatar size="md" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-5 w-32" />
        <SkeletonText lines={2} />
      </div>
      <div className="flex flex-col gap-2 items-end">
        <Skeleton className="h-6 w-16" />
        <Skeleton className="h-4 w-20" />
      </div>
    </div>
  );
}

/**
 * Patient list skeleton loader
 */
export function PatientListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <PatientCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Dashboard card skeleton
 */
export function DashboardCardSkeleton() {
  return (
    <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-6 space-y-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-4 w-16" />
      </div>
      <SkeletonText lines={2} />
      <div className="flex gap-2">
        <SkeletonButton size="sm" />
        <SkeletonButton size="sm" />
      </div>
    </div>
  );
}

/**
 * Table row skeleton
 */
export function TableRowSkeleton({ columns = 4 }: { columns?: number }) {
  return (
    <tr>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  );
}

/**
 * Table skeleton with header
 */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden">
      <table className="w-full">
        <thead className="bg-gray-50 dark:bg-gray-900">
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="px-4 py-3 text-left">
                <Skeleton className="h-4 w-24" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <TableRowSkeleton key={i} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Protocol card skeleton
 */
export function ProtocolCardSkeleton() {
  return (
    <SkeletonCard>
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
        <Skeleton className="h-8 w-20" />
      </div>
      <SkeletonText lines={2} />
      <div className="flex gap-4 pt-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-24" />
      </div>
    </SkeletonCard>
  );
}

/**
 * Protocol list skeleton
 */
export function ProtocolListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <ProtocolCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Full screen loading fallback
 */
export function ScreenLoadingFallback() {
  return (
    <div className="flex items-center justify-center h-full min-h-[400px]">
      <div className="text-center space-y-4">
        <div className="flex justify-center">
          <div className="h-12 w-12 border-4 border-teal-500 border-t-transparent rounded-full animate-spin" />
        </div>
        <div className="space-y-2">
          <Skeleton className="h-4 w-32 mx-auto" />
          <Skeleton className="h-3 w-24 mx-auto" />
        </div>
      </div>
    </div>
  );
}

/**
 * Inline loading spinner
 */
export function LoadingSpinner({
  size = 'md',
  className,
}: {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}) {
  const sizeClass = {
    sm: 'h-4 w-4 border-2',
    md: 'h-8 w-8 border-4',
    lg: 'h-12 w-12 border-4',
  }[size];

  return (
    <div
      className={`${sizeClass} border-teal-500 border-t-transparent rounded-full animate-spin ${className || ''}`}
      aria-label="Loading"
    />
  );
}
