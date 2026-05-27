# Frontend-Migrations-Plan

> Final document. Stand: 2026-05-27 · Alle Phasen (0–8) abgeschlossen.
> Vollstaendiger Blueprint im Approved-Plan unter `.claude/plans/`.

**Constraints (eingehalten):** reine UI-Schicht, Feature-Paritaet war hart
(keine Routen-/API-/Verhaltens-Aenderungen). Tasks waren so geschnitten,
dass keine zwei Tasks dieselbe Datei angefasst haben (= parallel mergebar).

## Materielle ADRs (Phase 0)

| ADR | Entscheidung |
|---|---|
| [0014](../adr/0014-frontend-color-space.md) Color-Space | **OKLCH** |
| [0015](../adr/0015-frontend-theme-toggle.md) Theme-Toggle | **Header-Toggle light/dark/system, localStorage** |
| [0016](../adr/0016-frontend-a11y-gate.md) A11y-Gate | **vitest-axe + eslint-plugin-jsx-a11y** |
| [0017](../adr/0017-frontend-appshell-outlet.md) AppShell | **Route-Level `<AppLayout>` mit `<Outlet/>`** |
| [0018](../adr/0018-frontend-component-catalog.md) Component-Catalog | **In-Repo `/_catalog` in DEV** |

## Phasen-Uebersicht

| # | Phase | Status | Notion-Milestone | Merge-Commit |
|---|---|---|---|---|
| 0 | Docs & Decisions | done | M-FE-0 | `98bbac7` (PR #25) |
| 1 | Foundation: Token-Skala + Barrels | done | M-FE-1 | `a6fb85f` (PR #26) |
| 2 | Routing-Refactor + AppShell-Outlet | done | M-FE-2 | `46c3d08` (PR #27) |
| 3 | Feedback-Layer (Toaster + `notify`) | done | M-FE-3 | `66a43dc` (PR #28) |
| 4 | Feature-Hooks (Pages frei von Fetch-/Form-State) | done | M-FE-4 | `fac8a4d` (PR #29) |
| 5 | A11y-Gate + Primitive-Luecken | done | M-FE-5 | `ef09cde` (PR #30) |
| 6 | Theme-Toggle + OKLCH | done | M-FE-6 | `29ef7cc` (PR #31) |
| 7 | Component-Catalog | done | M-FE-7 | `44aeb76` (PR #32) |
| 8 | Cleanup & Closeout | done | M-FE-8 | `0270580` (PR #33) |

## Task-Tracking

| Task | Phase | Status | Vorgaenger | Affected Files (Kurz) |
|---|---|---|---|---|
| 0.1 | 0 | done | — | `docs/frontend/architecture.md` |
| 0.2 | 0 | done | — | `docs/frontend/component-map.md` |
| 0.3 | 0 | done | — | `docs/frontend/migration-plan.md` |
| 0.4 | 0 | done | — | `docs/frontend/test-plan.md` |
| 0.5 | 0 | done | — | `docs/adr/0014..0018` |
| 1.1 | 1 | done | 0.1, 0.5 | `apps/web/src/styles/globals.css` (Spacing/Typo-Skala) |
| 1.2 | 1 | done | 0.5 | `apps/web/src/components/ui/index.ts` (Barrel) |
| 1.3 | 1 | done | 0.5 | `apps/web/src/components/{layout,data}/index.ts` (Barrels) |
| 1.4 | 1 | done | 1.2 | `apps/web/src/lib/feedback.ts` (Stub) |
| 2.1 | 2 | done | 1.3 | `apps/web/src/app/{routes,AppLayout,RouteErrorBoundary,RouteFallback}.tsx`, `apps/web/src/App.tsx`, `apps/web/src/components/layout/AppShell.tsx`, `apps/web/src/test/setup.ts` |
| 2.2 | 2 | done | 2.1 | `…/personas/pages/PersonasPage.tsx` (+ Test) |
| 2.3 | 2 | done | 2.1 | `…/personas/pages/PersonaNewPage.tsx`, `…/PersonaDetailPage.tsx` (+ Tests) |
| 2.4 | 2 | done | 2.1 | `…/playbooks/pages/PlaybooksPage.tsx`, `…/PlaybookNewPage.tsx`, `…/PlaybookDetailPage.tsx` (+ Tests) |
| 2.5 | 2 | done | 2.1 | `…/tokens/pages/SettingsTokensPage.tsx` (+ Test) |
| 2.6 | 2 | done | 2.2–2.5 | `apps/web/src/app/routes.tsx` (Lazy + Suspense) |
| 3.1 | 3 | done | 1.4, 2.1 | `apps/web/src/app/AppLayout.tsx` (Toaster mount) |
| 3.2 | 3 | done | 3.1 | `…/personas/pages/PersonaDetailPage.tsx` (+ Test) |
| 3.3 | 3 | done | 3.1 | `…/playbooks/pages/PlaybookDetailPage.tsx` (+ Test) |
| 3.4 | 3 | done | 3.1 | `…/tokens/pages/SettingsTokensPage.tsx` (+ Test) |
| 4.1 | 4 | done | 1.3 | `…/personas/hooks/usePersona.ts` (+ Test) |
| 4.2 | 4 | done | 1.4, 3.1 | `…/personas/hooks/usePersonaForm.ts` (+ Test) |
| 4.3 | 4 | done | 4.1, 4.2 | `…/personas/pages/PersonaDetailPage.tsx` (+ Test) |
| 4.4 | 4 | done | 1.3, 3.1 | `…/playbooks/hooks/usePlaybook.ts`, `…/usePlaybookForm.ts` (+ Tests) |
| 4.5 | 4 | done | 4.4 | `…/playbooks/pages/PlaybookDetailPage.tsx` (+ Test) |
| 4.6 | 4 | done | 1.3, 3.1 | `…/tokens/hooks/useTokenMutations.ts` (+ Test) |
| 4.7 | 4 | done | 4.6 | `…/tokens/pages/SettingsTokensPage.tsx` (+ Test) |
| 5.1 | 5 | done | 4.3, 4.5, 4.7 | `apps/web/package.json`, `apps/web/src/test/setup.ts`, `apps/web/eslint.config.js` |
| 5.2 | 5 | done | 5.1 | 4 neue `*.a11y.test.tsx` |
| 5.3 | 5 | done | 5.1, 4.3 | `…/personas/components/PlaybookLinkItem.tsx`, `…/PersonaDetailPage.tsx` |
| 5.4 | 5 | done | 5.3 | `apps/web/eslint.config.js` (label-Forbid + jsx-a11y error) |
| 5.5 | 5 | done | 5.2 | `.github/workflows/ci.yml` |
| 6.1 | 6 | done | 0.5 | `apps/web/src/styles/globals.css` (OKLCH) |
| 6.2 | 6 | done | 2.1 | `apps/web/src/app/{ThemeProvider,theme-context}.tsx` (+ Tests) |
| 6.3 | 6 | done | 6.1, 6.2 | `apps/web/src/components/ui/theme-toggle.tsx`, `…/layout/AppShell.tsx` |
| 6.4 | 6 | done | 6.1, 6.2 | `apps/web/src/styles/globals.css` (Dark-Selector) |
| 7.1 | 7 | done | 2.1 | `apps/web/src/app/catalog/CatalogPage.tsx`, `apps/web/src/app/routes.tsx` |
| 7.2 | 7 | done | 7.1 | `apps/web/src/app/catalog/showcases/*.tsx` (pro Primitive) |
| 7.3 | 7 | done | 7.1 | `apps/web/src/app/catalog/showcases/{layout,data}.tsx` |
| 8.1 | 8 | done | 5, 6, 7 | `docs/frontend/{architecture,migration-plan,component-map,test-plan}.md` |
| 8.2 | 8 | done | 8.1 | `docs/frontend/smoke-checklist.md` |
| 8.3 | 8 | done | 8.1 | Notion PROJ-19 Closeout (M-FE-0..8 Done, Lessons-Learned-Note) |

## Branch- und Merge-Strategie (Rueckblick)

- Integration-Branch je Phase: `feat/frontend-phase-<n>`. Bewaehrt.
- Phase wurde gesammelt nach `main` gemerged (Squash). Roll-Back ist
  `git revert <merge-sha>` — Order respektieren (8 → 1).
- Keine Feature-Flags noetig. Theme-Toggle (6.3) konnte ohne Flag live.
