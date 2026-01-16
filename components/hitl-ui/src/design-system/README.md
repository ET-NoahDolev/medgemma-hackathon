## Design System (tokens-first)

### What this is

`src/design-system/` is the **source of truth** for design decisions:

- **Tokens** (CSS variables) live in `src/design-system/tokens.css`
- JS/TS accessors live in `src/design-system/tokens.ts`
- Theme helpers live in `src/design-system/theme.ts`

### Rules (best-practice)

- **Do not** define token values anywhere else (especially not in components).
- Components should prefer **semantic tokens** (e.g. `--color-bg-panel`) over primitives.
- Prefer classnames (Tailwind/shadcn) and **CSS variables** over inline `rgba(...)`.
- Use `tokens.ts` only when JS must reference tokens (canvas, dynamic styles).

### Theming

- Theme is controlled via `data-theme="light|dark"` on `<html>`.
- Use `setTheme()` / `toggleTheme()` from `src/design-system/theme.ts`.
