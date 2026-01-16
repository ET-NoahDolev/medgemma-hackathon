import * as React from 'react';
import { cn } from '@/components/ui/utils';

/**
 * Base skeleton component with smooth shimmer animation
 * Used as building block for all skeleton loaders
 */
export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Animation variant
   * - 'pulse': subtle fade in/out
   * - 'shimmer': smooth left-to-right shimmer (default)
   * - 'none': no animation
   */
  variant?: 'pulse' | 'shimmer' | 'none';
  /**
   * Rounded corners
   */
  rounded?: 'none' | 'sm' | 'md' | 'lg' | 'full';
}

export function Skeleton({
  className,
  variant = 'shimmer',
  rounded = 'md',
  ...props
}: SkeletonProps) {
  const roundedClass = {
    none: 'rounded-none',
    sm: 'rounded-sm',
    md: 'rounded-md',
    lg: 'rounded-lg',
    full: 'rounded-full',
  }[rounded];

  const animationClass = {
    pulse: 'animate-pulse',
    shimmer: 'skeleton-shimmer',
    none: '',
  }[variant];

  return (
    <div
      className={cn('bg-gray-200/60 dark:bg-gray-800/60', roundedClass, animationClass, className)}
      {...props}
    />
  );
}

/**
 * Pre-built skeleton components for common patterns
 */

export function SkeletonText({
  lines = 1,
  className,
  ...props
}: { lines?: number } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('space-y-2', className)} {...props}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn('h-4', i === lines - 1 && lines > 1 ? 'w-3/4' : 'w-full')}
        />
      ))}
    </div>
  );
}

export function SkeletonAvatar({
  size = 'md',
  className,
  ...props
}: {
  size?: 'sm' | 'md' | 'lg';
} & React.HTMLAttributes<HTMLDivElement>) {
  const sizeClass = {
    sm: 'h-8 w-8',
    md: 'h-10 w-10',
    lg: 'h-12 w-12',
  }[size];

  return <Skeleton rounded="full" className={cn(sizeClass, className)} {...props} />;
}

export function SkeletonButton({
  size = 'md',
  className,
  ...props
}: {
  size?: 'sm' | 'md' | 'lg';
} & React.HTMLAttributes<HTMLDivElement>) {
  const sizeClass = {
    sm: 'h-8 w-20',
    md: 'h-10 w-24',
    lg: 'h-12 w-32',
  }[size];

  return <Skeleton rounded="md" className={cn(sizeClass, className)} {...props} />;
}

export function SkeletonCard({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'p-6 border border-gray-200 dark:border-gray-800 rounded-lg space-y-4',
        className
      )}
      {...props}
    >
      <Skeleton className="h-6 w-1/3" />
      <SkeletonText lines={3} />
      <div className="flex gap-2">
        <SkeletonButton size="sm" />
        <SkeletonButton size="sm" />
      </div>
    </div>
  );
}
