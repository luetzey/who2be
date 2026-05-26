# Frontend-Migrations-Plan

> Living document. Stand: 2026-05-26 · Status wird pro Task gepflegt.
> Vollstaendiger Blueprint im Approved-Plan unter `.claude/plans/`.

**Constraints:** reine UI-Schicht, Feature-Paritaet ist hart (keine
Routen-/API-/Verhaltens-Aenderungen). Tasks sind so geschnitten, dass
keine zwei Tasks dieselbe Datei anfassen (= parallel mergebar).

## Materielle ADRs (Phase 0)

| ADR | Entscheidung |
|---|---|
| [0014](../adr/0014-frontend-color-space.md) Color-Space | **OKLCH** |
| [0015](../adr/0015-frontend-theme-toggle.md) Theme-Toggle | **Header-Toggle light/dark/system, localStorage** |
| [0016](../adr/0016-frontend-a11y-gate.md) A11y-Gate | **vitest-axe + eslint-plugin-jsx-a11y** |
| [0017](../adr/0017-frontend-appshell-outlet.md) AppShell | **Route-Level `<AppLayout>` mit `<Outlet/>`** |
| [0018](../adr/0018-frontend-component-catalog.md) Component-Catalog | **In-Repo `/_catalog` in DEV** |

## Phasen-Uebersicht

| # | Phase | Status | Notion-Milestone |
|---|---|---|---|
| 0 | Docs & Decisions | in-progress | M-FE-0 |
| 1 | Foundation: Token-Skala + Barrels | todo | M-FE-1 |
| 2 | Routing-Refactor + AppShell-Outlet | todo | M-FE-2 |
| 3 | Feedback-Layer (Toaster + `notify`) | todo | M-FE-3 |
| 4 | Feature-Hooks (Pages frei von Fetch-/Form-State) | todo | M-FE-4 |
| 5 | A11y-Gate + Primitive-Luecken | todo | M-FE-5 |
| 6 | Theme-Toggle + OKLCH | todo | M-FE-6 |
| 7 | Component-Catalog | todo | M-FE-7 |
| 8 | Cleanup & Closeout | todo | M-FE-8 |

Phase 6 haengt nur an Phase 2, Phase 7 nur an Phase 1 — beide
parallelisierbar zu Phasen 3–5.

## Task-Tracking

| Task | Phase | Status | Vorgaenger | Affected Files (Kurz) |
|---|---|---|---|---|
| 0.1 | 0 | in-progress | — | `docs/frontend/architecture.md` |
| 0.2 | 0 | in-progress | — | `docs/frontend/component-map.md` |
| 0.3 | 0 | in-progress | — | `docs/frontend/migration-plan.md` |
| 0.4 | 0 | in-progress | — | `docs/frontend/test-plan.md` |
| 0.5 | 0 | in-progress | — | `docs/adr/0014..0018` |
| 1.1 | 1 | todo | 0.1, 0.5 | `apps/web/src/styles/globals.css` (Spacing/Typo-Skala) |
| 1.2 | 1 | todo | 0.5 | `apps/web/src/components/ui/index.ts` (Barrel) |
| 1.3 | 1 | todo | 0.5 | `apps/web/src/components/{layout,data}/index.ts` (Barrels) |
| 1.4 | 1 | todo | 1.2 | `apps/web/src/lib/feedback.ts` (Stub) |
| 2.1 | 2 | todo | 1.3 | `apps/web/src/app/{routes,AppLayout,RouteErrorBoundary,RouteFallback}.tsx`, `apps/web/src/App.tsx`, `apps/web/src/components/layout/AppShell.tsx`, `apps/web/src/test/setup.ts` |
| 2.2 | 2 | todo | 2.1 | `…/personas/pages/PersonasPage.tsx` (+ Test) |
| 2.3 | 2 | todo | 2.1 | `…/personas/pages/PersonaNewPage.tsx`, `…/PersonaDetailPage.tsx` (+ Tests) |
| 2.4 | 2 | todo | 2.1 | `…/playbooks/pages/PlaybooksPage.tsx`, `…/PlaybookNewPage.tsx`, `…/PlaybookDetailPage.tsx` (+ Tests) |
| 2.5 | 2 | todo | 2.1 | `…/tokens/pages/SettingsTokensPage.tsx` (+ Test) |
| 2.6 | 2 | todo | 2.2–2.5 | `apps/web/src/app/routes.tsx` (Lazy + Suspense) |
| 3.1 | 3 | todo | 1.4, 2.1 | `apps/web/src/app/AppLayout.tsx` (Toaster mount) |
| 3.2 | 3 | todo | 3.1 | `…/personas/pages/PersonaDetailPage.tsx` (+ Test) |
| 3.3 | 3 | todo | 3.1 | `…/playbooks/pages/PlaybookDetailPage.tsx` (+ Test) |
| 3.4 | 3 | todo | 3.1 | `…/tokens/pages/SettingsTokensPage.tsx` (+ Test) |
| 4.1 | 4 | todo | 1.3 | `…/personas/hooks/usePersona.ts` (+ Test) |
| 4.2 | 4 | todo | 1.4, 3.1 | `…/personas/hooks/usePersonaForm.ts` (+ Test) |
| 4.3 | 4 | todo | 4.1, 4.2 | `…/personas/pages/PersonaDetailPage.tsx` (+ Test) |
| 4.4 | 4 | todo | 1.3, 3.1 | `…/playbooks/hooks/usePlaybook.ts`, `…/usePlaybookForm.ts` (+ Tests) |
| 4.5 | 4 | todo | 4.4 | `…/playbooks/pages/PlaybookDetailPage.tsx` (+ Test) |
| 4.6 | 4 | todo | 1.3, 3.1 | `…/tokens/hooks/useTokenMutations.ts` (+ Test) |
| 4.7 | 4 | todo | 4.6 | `…/tokens/pages/SettingsTokensPage.tsx` (+ Test) |
| 5.1 | 5 | todo | 4.3, 4.5, 4.7 | `apps/web/package.json`, `apps/web/src/test/setup.ts`, `apps/web/eslint.config.js` |
| 5.2 | 5 | todo | 5.1 | 4 neue `*.a11y.test.tsx` |
| 5.3 | 5 | todo | 5.1, 4.3 | `…/personas/components/PlaybookLinkItem.tsx`, `…/PersonaDetailPage.tsx` |
| 5.4 | 5 | todo | 5.3 | `apps/web/eslint.config.js` (label-Forbid + jsx-a11y error) |
| 5.5 | 5 | todo | 5.2 | `.github/workflows/ci.yml` |
| 6.1 | 6 | todo | 0.5 | `apps/web/src/styles/globals.css` (OKLCH) |
| 6.2 | 6 | todo | 2.1 | `apps/web/src/app/ThemeProvider.tsx` (+ Test) |
| 6.3 | 6 | todo | 6.1, 6.2 | `apps/web/src/components/ui/theme-toggle.tsx`, `…/layout/AppShell.tsx` |
| 6.4 | 6 | todo | 6.1, 6.2 | `apps/web/src/styles/globals.css` (Dark-Selector) |
| 7.1 | 7 | todo | 2.1 | `apps/web/src/app/catalog/CatalogPage.tsx`, `apps/web/src/app/routes.tsx` |
| 7.2 | 7 | todo | 7.1 | `apps/web/src/app/catalog/showcases/*.tsx` (pro Primitive) |
| 7.3 | 7 | todo | 7.1 | `apps/web/src/app/catalog/showcases/{layout,data}.tsx` |
| 8.1 | 8 | todo | 5, 6, 7 | `docs/frontend/{architecture,migration-plan}.md` |
| 8.2 | 8 | todo | 8.1 | `docs/frontend/smoke-checklist.md` |
| 8.3 | 8 | todo | 8.1 | Notion PROJ-19 Closeout |

## Branch- und Merge-Strategie

- Integration-Branch je Phase: `feat/frontend-phase-<n>`.
- Tasks darauf via `feat/frontend-<n.m>-<kurz>`.
- Phase wird gesammelt nach `main` gemerged (Squash). Roll-Back ist
  `git revert <merge-sha>`. Roll-Back-Order respektieren (8 → 1).
- Keine Feature-Flags noetig. Ausnahme: Theme-Toggle in 6.3 kann hinter
  `import.meta.env.DEV` versteckt werden, falls QA blockt.
