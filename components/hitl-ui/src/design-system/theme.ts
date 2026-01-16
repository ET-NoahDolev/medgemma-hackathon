import type { ThemeName } from '@/design-system/tokens';

const THEME_ATTR = 'data-theme';

export function getTheme(): ThemeName {
  const t = document.documentElement.getAttribute(THEME_ATTR);
  return t === 'dark' ? 'dark' : 'light';
}

export function setTheme(theme: ThemeName) {
  document.documentElement.setAttribute(THEME_ATTR, theme);
}

export function toggleTheme(): ThemeName {
  const next: ThemeName = getTheme() === 'dark' ? 'light' : 'dark';
  setTheme(next);
  return next;
}
