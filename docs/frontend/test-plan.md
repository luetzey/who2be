# Frontend-Test-Plan

> Living document. Stand: 2026-05-27 · Phasen 0–7 abgeschlossen.

Reine UI-Migration ⇒ Verhalten = API-Calls + Routing + Form-Submit-Reaktionen.
Strategie: bestehende Pages-Tests dienen als **Feature-Paritaets-Snapshots**;
neue Schichten kommen zusaetzlich. Visual-Regression bleibt out-of-scope.

## 1. Test-Schichten

| Schicht | Tool | Was getestet wird | Wann |
|---|---|---|---|
| Unit / Hook | Vitest + RTL | API-Client, `useListData`, `useApi`, `useAuthToken`, `useSession`, ab Phase 4: `usePersona`/`usePersonaForm`/`usePlaybook`/`usePlaybookForm`/`useTokenMutations`. Hook-Verhalten via `renderHook`. | bestehend + Phase 4 ergaenzt 5–6 |
| Component-Render | Vitest + RTL | Layout/Data/Primitives indirekt ueber Page-Tests; `DataList`, `DataView` haben eigene. | bestehend |
| Page-Verhalten | Vitest + RTL | Page-Flow: load → render → user interaction → assert API-Call. Pflicht-Render via `renderInRoutes(page, { path })` (ab Phase 2). | bestehend + Phase 2 angepasst |
| A11y | `vitest-axe` (Setup Phase 5.1) | `expect(container).toHaveNoViolations()` fuer 4 Hauptseiten + Layout-/Data-Komponenten. | Phase 5.2 |
| Lint | `eslint-plugin-jsx-a11y` + bestehende Regeln | Strukturelle A11y-Verstoesse + rohe HTML-Tags + Cross-Feature-Deep-Imports. | jeder PR |
| Build-Gate | `npx tsc --noEmit`, `npm run build` | TypeScript-Strict + Vite-Build. | jeder PR |
| Smoke (manuell) | Markdown-Checkliste (`docs/frontend/smoke-checklist.md`, Phase 8.2) | 7 Pages × 2 Themes × Toast-Flows × Form-Errors × Override-Token-Flow. | Phase-Ende |
| Visual-Regression | Playwright-Screenshots | **OUT OF SCOPE.** Nachfolgeprojekt. | — |

## 2. Test-Setup

Datei: `apps/web/src/test/setup.ts`.

- **bestehend:** `@testing-library/jest-dom/vitest`.
- **Phase 2.1:** `renderInRoutes(page, { path })`-Helper. Wickelt eine
  Page in `<BrowserRouter>` → `<Routes>` → `<Route element={AppLayout}>` →
  `<Route path={path} element={page}>`. So bleibt Page-Test-Setup
  konsistent zur Produktion und Page-DOM enthaelt das tatsaechliche
  Outlet-Layout.
- **Phase 3.1:** `notify`-Mock-Convention. Tests importieren
  `import { notify } from '@/lib/feedback'` und spyn via
  `vi.mock('@/lib/feedback', () => ({ notify: { success: vi.fn(), error: vi.fn() } }))`.
- **Phase 5.1:** `import 'vitest-axe/extend-expect'` und ergaenzt
  `expect.extend(toHaveNoViolations)`.

## 3. CI-Gates

Bestehende Pipeline `.github/workflows/ci.yml`:

```
cd apps/web
npm ci
npm run lint
npx tsc --noEmit
npm test
npm run build
```

**Phase 5.5 ergaenzt** einen sichtbar getrennten `a11y`-Step (eigener
Vitest-Lauf mit `--testNamePattern '\.a11y\.'`), damit A11y-Regressionen
in CI als eigenes rotes Signal erscheinen.

## 4. Feature-Paritaet verifizieren

**Harte Regel:** Page-Tests bestehen mit **0 angepassten Assertions** —
nur Render-Wrapper-Updates erlaubt. Wer eine Assertion aendert, hat
Feature-Paritaet verletzt; das braucht eine bewusste Begruendung im
PR-Body.

**API-Calls-Spy** (Phase 4): in Page-Tests werden `api.updatePersona`,
`api.updatePlaybook`, `api.createToken`, `api.revokeToken`,
`api.setPersonaPlaybooks` mit `vi.spyOn` greifbar. Erwartete Payloads
sind ein Feature-Paritaets-Snapshot — sie bleiben unveraendert ueber alle
Phasen.

**Smoke-Run am Phasenende:** Login → 7 Pages × 1 Mutation je Editor →
Sign-out. Dauer ~5 min. Wird in Phase 8.2 zu einer expliziten Checkliste
ausgeschrieben.

## 5. Pro-Phase-Gates

| Phase | Zusatz-Gate ueber den Standard-Build hinaus |
|---|---|
| 0 | — (Doku-only) |
| 1 | `git diff` auf Pages = 0 (kein Page-Code angefasst). |
| 2 | `grep -r "from '@/components/layout/AppShell'" apps/web/src/features` ist leer. Bundle zeigt eigene Chunks pro Page. |
| 3 | `<Toaster/>` exakt 1×. `grep -r "<Alert role=\"status\">" apps/web/src/features` zeigt nur TokensPage (Token-Reveal). |
| 4 | `grep -rE "(useEffect\|useState\|useApi)" apps/web/src/features/**/pages` zeigt nur Routing-Glue (`useParams`/`useNavigate`). Pages-LOC sinkt ≥ 30 %. |
| 5 | `vitest --run` zeigt `*.a11y.test` mit 0 violations. ESLint mit `jsx-a11y` = 0 Errors. CI hat eigenen `a11y`-Step. |
| 6 | Manueller Side-by-Side Light/Dark gegen `dist/`-Archiv von vor 6.1: 0 sichtbare Regressionen. Theme-Toggle persistiert ueber Reload. |
| 7 | `npm run dev` -> `/_catalog` laedt; `npm run build && npm run preview` -> `/_catalog` ist 404. |
| 8 | `docs/frontend/smoke-checklist.md` vollstaendig abgehakt. |

## 6. Risiken (relevant fuer Tests)

- **AppShell-Outlet-Refactor (Phase 2):** Page-Tests greifen heute teilweise
  Nav-Roles, die nach 2.2–2.5 ausserhalb des Page-DOMs liegen.
  **Mitigation:** `renderInRoutes` aus 2.1 mountet Outlet — Roles bleiben
  greifbar.
- **Toast-Mock (Phase 3):** Sonner rendert im Portal. **Mitigation:**
  Tests spy-en `notify.success` statt DOM-Lookup; `lib/feedback.ts` ist
  der einzige Wrapper-Punkt.
- **OKLCH-Verfaerbung (Phase 6):** Test-DOM testet keine Farbwerte.
  Mitigation = manueller Side-by-Side vor Merge.
