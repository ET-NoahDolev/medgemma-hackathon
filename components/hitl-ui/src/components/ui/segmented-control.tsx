'use client';

import * as React from 'react';
import { cn } from '@/components/ui/utils';

export interface SegmentedControlProps {
  value: string;
  onValueChange: (value: string) => void;
  options: Array<{ value: string; label: string; badge?: React.ReactNode }>;
  className?: string;
  activeColor?: string; // Hex color for active tab (e.g., from trial color)
}

export function SegmentedControl({
  value,
  onValueChange,
  options,
  className,
  activeColor,
}: SegmentedControlProps) {
  // Convert hex color to RGB for dark mode variant
  const getColorClasses = () => {
    if (!activeColor) {
      return 'border-teal-500 dark:border-teal-400';
    }

    // For custom colors, use inline style for border
    return '';
  };

  const getActiveStyle = () => {
    if (!activeColor) return {};

    // Use the trial color directly for dark mode (same as light mode)
    if (activeColor.startsWith('#')) {
      return {
        borderColor: activeColor,
        // @ts-expect-error - CSS custom properties for dark mode not in React.CSSProperties
        '--active-border-color': activeColor,
        '--active-border-color-dark': activeColor,
        '--active-bg-color-dark': activeColor,
      } as React.CSSProperties;
    }

    return {
      borderColor: activeColor,
      // @ts-expect-error - CSS custom properties for dark mode not in React.CSSProperties
      '--active-border-color': activeColor,
      '--active-border-color-dark': activeColor,
      '--active-bg-color-dark': activeColor,
    } as React.CSSProperties;
  };

  return (
    <div
      data-slot="segmented-control"
      className={cn(
        'inline-flex items-center gap-1.5 p-1 rounded-full',
        'bg-gray-100 dark:bg-transparent',
        'border border-gray-200/50 dark:border-transparent',
        className
      )}
    >
      {options.map(option => {
        const isActive = value === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onValueChange(option.value)}
            className={cn(
              'px-3 py-1.5 rounded-full text-xs font-semibold transition-all',
              'flex items-center gap-1.5 whitespace-nowrap shrink-0',
              'border-2 border-transparent',
              isActive
                ? `bg-white text-gray-900 shadow-sm ${getColorClasses()}`
                : 'text-gray-600 hover:text-gray-900'
            )}
            style={isActive && activeColor ? getActiveStyle() : undefined}
          >
            <span className="whitespace-nowrap">{option.label}</span>
            {option.badge}
          </button>
        );
      })}
    </div>
  );
}
