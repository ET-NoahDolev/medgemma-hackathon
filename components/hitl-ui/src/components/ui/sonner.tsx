'use client';

import * as React from 'react';
import { Toaster as Sonner, ToasterProps } from 'sonner';
import { getTheme } from '@/design-system/theme';

const Toaster = ({ ...props }: ToasterProps) => {
  // Use design system theme helper for consistency
  const getThemeValue = (): ToasterProps['theme'] => {
    const t = getTheme();
    if (t === 'dark' || t === 'light') return t;
    return 'system';
  };

  const [theme, setTheme] = React.useState<ToasterProps['theme']>(() =>
    typeof document === 'undefined' ? 'system' : getThemeValue()
  );

  React.useEffect(() => {
    const el = document.documentElement;
    const obs = new MutationObserver(() => setTheme(getThemeValue()));
    obs.observe(el, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  return (
    <Sonner
      theme={theme as ToasterProps['theme']}
      className="toaster group"
      toastOptions={{
        style: {
          background: 'var(--popover)',
          color: 'var(--popover-foreground)',
          border: '1px solid var(--border)',
        },
        classNames: {
          toast:
            'group-[.toaster]:!bg-white group-[.toaster]:!text-gray-900 group-[.toaster]:!border-gray-200 group-[.toaster]:!shadow-lg',
          description: 'group-[.toast]:!text-gray-600 group-[.toast]:!text-sm',
          actionButton:
            'group-[.toast]:!bg-teal-600 group-[.toast]:!text-white group-[.toast]:!px-3 group-[.toast]:!py-1.5 group-[.toast]:!rounded group-[.toast]:!text-sm',
          cancelButton: 'group-[.toast]:!bg-gray-100 group-[.toast]:!text-gray-900',
        },
      }}
      position="top-right"
      richColors
      closeButton
      {...props}
    />
  );
};

export { Toaster };
