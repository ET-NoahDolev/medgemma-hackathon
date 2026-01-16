/**
 * Cauldron Design System — JS/TS accessors
 * Use these when a value must be referenced in JS/TS (styles, canvas, etc).
 * Prefer CSS usage (`var(--token)`) in className/style where possible.
 */

export const cssVar = (name: string) => `var(${name})` as const;

export const tokens = {
  color: {
    bgApp: cssVar('--color-bg-app'),
    bgPanel: cssVar('--color-bg-panel'),
    textPrimary: cssVar('--color-text-primary'),
    textSecondary: cssVar('--color-text-secondary'),
    border: cssVar('--color-border'),

    actionPrimary: cssVar('--color-action-primary'),
    actionPrimaryHover: cssVar('--color-action-primary-hover'),
    actionPrimaryPressed: cssVar('--color-action-primary-pressed'),
    actionSecondary: cssVar('--color-action-secondary'),
    actionSecondaryHover: cssVar('--color-action-secondary-hover'),
  },
  cockpit: {
    bg: cssVar('--cockpit-bg'),
    glassBg: cssVar('--glass-bg'),
    glassBorder: cssVar('--glass-border'),
    glassHighlight: cssVar('--glass-highlight'),
    hudFg: cssVar('--hud-fg'),
    hudMuted: cssVar('--hud-muted'),
  },
  font: {
    sans: cssVar('--font-sans'),
    body: cssVar('--fs-body'),
    bodyLg: cssVar('--fs-body-lg'),
    h4: cssVar('--fs-h4'),
    h5: cssVar('--fs-h5'),
    h6: cssVar('--fs-h6'),
  },
  radius: {
    sm: cssVar('--radius-sm'),
    md: cssVar('--radius-md'),
    lg: cssVar('--radius-lg'),
  },
  shadow: {
    sm: cssVar('--shadow-sm'),
    md: cssVar('--shadow-md'),
  },
} as const;

export type ThemeName = 'light' | 'dark';
