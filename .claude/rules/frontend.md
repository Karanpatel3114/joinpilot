---
paths:
  - "web/**"
---
# Frontend rules

- React 19, TypeScript in strict mode, Vite, Tailwind CSS. No `any`.
- API types live in `web/src/types/api.ts` and mirror docs/contract.md exactly. Change them only with the `contract-sync` skill.
- Server data goes through TanStack Query hooks in `web/src/api/`. Components never call `fetch` directly.
- Join graphs use React Flow; charts use Recharts.
- Small components, one per file, named for what they show. Pages live in `web/src/pages/`.
- Accessible by default: labels on inputs, keyboard navigation, visible focus, sufficient contrast. Support light and dark themes.
- Every important number on screen (overlap ratio, check result, KPI) shows where it came from, matching the evidence in the API response.
- Tests use Vitest and Testing Library for components; one Playwright test covers the main flow (added in M7).
