import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/components/ui/utils';

const glassButtonVariants = cva(
  "glass-button relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-300 ease-out disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background focus-visible:ring-ring overflow-hidden",
  {
    variants: {
      variant: {
        default: 'glass-button-default',
        primary: 'glass-button-primary',
        secondary: 'glass-button-secondary',
        outline: 'glass-button-outline',
        ghost: 'glass-button-ghost',
      },
      size: {
        default: 'h-10 px-8 py-2',
        sm: 'h-8 px-6 py-1.5 text-xs min-w-[80px]',
        lg: 'h-12 px-10 py-3 text-base',
        icon: 'size-10 p-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface GlassButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof glassButtonVariants> {
  asChild?: boolean;
}

const GlassButton = React.forwardRef<HTMLButtonElement, GlassButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';

    return (
      <Comp
        data-slot="glass-button"
        className={cn(glassButtonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);

GlassButton.displayName = 'GlassButton';

// eslint-disable-next-line react-refresh/only-export-components -- UI component library pattern: export both component and variants utility
export { GlassButton, glassButtonVariants };
