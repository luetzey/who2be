# Frontend-Komponenten-Karte

> Living document. Stand: 2026-05-26 · Phase 0. Wird in Phase 1/2
> aktualisiert, sobald Barrels und `app/`-Layer existieren.

Eine Zeile pro Komponente. Eintraege folgen der Schichtung aus
[architecture.md](./architecture.md). Spalte **Tokens** nennt die
Token-Familien, die die Komponente konsumiert (alle ueber CSS-Variablen
in `globals.css`).

## UI-Primitives (`components/ui/*`)

| Komponente | Datei | Tokens | Tests | Notiz |
|---|---|---|---|---|
| `Button` | `button.tsx` | `--color-{primary,destructive,…}`, `--radius-md` | `…/button.test.tsx` (Phase 7 Catalog) | `cva` Varianten (default, destructive, outline, secondary, ghost, link) + sizes; `asChild` via Radix-Slot. |
| `Input` | `input.tsx` | `--color-{input,foreground,ring}`, `--radius-md` | `…/input.test.tsx` (Phase 7) | `forwardRef`, Pflicht-Tailwind-Styling. |
| `Textarea` | `textarea.tsx` | dito | Phase 7 | dito. |
| `Card` (+Header/Title/Description/Content/Footer) | `card.tsx` | `--color-card`, `--color-card-foreground`, `--radius-lg` | Phase 7 | Semantische HTML-Wrappers, forwardRef je Sub-Component. |
| `Badge` | `badge.tsx` | `--color-{primary,secondary,destructive}` | Phase 7 | `cva` Varianten. |
| `Checkbox` | `checkbox.tsx` | `--color-{primary,input,ring}` | bestehend | Custom mit `lucide-react`-Check; forwardRef. |
| `Label` | `label.tsx` | `--color-foreground` | Phase 7 | Radix-Label + `cva`. |
| `Alert` (+Title/Description) | `alert.tsx` | `--color-{destructive,foreground}` | Phase 7 | `cva` Varianten (default, destructive). |
| `Dialog` (+Trigger/Content/Header/…) | `dialog.tsx` | `--color-{background,foreground,border}` | Phase 7 | Radix-Dialog. |
| `DropdownMenu` (+Trigger/Content/Item/…) | `dropdown-menu.tsx` | `--color-{popover,accent,…}` | Phase 7 | Radix-DropdownMenu. |
| `Form` (+Field/Item/Label/Control/Message/Description) | `form.tsx` | `--color-{destructive,foreground}` | bestehend (via Page-Tests) | RHF + Radix-Label Integration. |
| `Skeleton` | `skeleton.tsx` | `--color-muted` | bestehend (via LoadingState) | Pulse-Animation. |
| `Table` (+Header/Body/Footer/Head/Row/Cell/Caption) | `table.tsx` | `--color-border`, `--color-muted-foreground` | Phase 7 | Semantische Wrappers. |
| `Toaster` (Sonner) | `sonner.tsx` | `--color-{popover,foreground}` | indirekt (Phase 3) | **Wird in `AppLayout` 1x gemountet (Phase 3.1).** |
| `ThemeToggle` (NEU Phase 6.3) | `theme-toggle.tsx` | `--color-{popover,accent}` | `…/theme-toggle.test.tsx` (Phase 6.3) | DropdownMenu mit light/dark/system. |

## Layout-Primitives (`components/layout/*`)

| Komponente | Datei | Rolle | Tokens | Tests |
|---|---|---|---|---|
| `AppShell` | `AppShell.tsx` | App-Chrome (Nav-Sidebar, Header, Content-Slot). **Ab Phase 2 nur noch von `AppLayout` importierbar.** Bekommt ab Phase 6 Theme-Toggle-Slot im Header. | `--color-{background,foreground,muted,accent,ring}` | indirekt |
| `Container` | `Container.tsx` | Max-Width-Wrapper (5xl) mit responsivem Padding. | `--space-*` | indirekt |
| `PageHeader` | `PageHeader.tsx` | Title + Description + Actions-Slot. | `--space-*` | indirekt |
| `Stack` | `Stack.tsx` | `cva` Flex-Column mit Gap-Skala. | `--space-*` | indirekt |
| `Section` | `Section.tsx` | Semantisches `<section>` mit Flex-Column-Gap. | `--space-*` | indirekt |

## Data-Komponenten (`components/data/*`)

| Komponente | Datei | Rolle | Tests |
|---|---|---|---|
| `DataView` | `DataView.tsx` | Bedingtes Rendern: Loading-Skelett, Error-Alert, EmptyState, oder Kinder. | `DataView.test.tsx` |
| `DataList` | `DataList.tsx` | Generischer `<ul>`-Renderer mit Loading/Error/Empty-States. | `DataList.test.tsx` |
| `LoadingState` | `LoadingState.tsx` | Skeleton-Reihen mit `aria-live`. | indirekt |
| `EmptyState` | `EmptyState.tsx` | Title + Description + Action-Slot, gestrichelter Rahmen. | indirekt |
| `ErrorAlert` | `ErrorAlert.tsx` | `Alert` mit `AlertCircle`-Icon und Title/Message. | indirekt |

## App-Layer (`app/*`, ab Phase 2)

| Komponente | Datei | Rolle | Tests |
|---|---|---|---|
| `routes.tsx` | `app/routes.tsx` | Routen-Definition mit `<Route element={<AppLayout/>}>` und Lazy + Suspense. | indirekt |
| `AppLayout` | `app/AppLayout.tsx` | Mountet `<AppShell>`, `<Outlet>`, `<Toaster>`, ErrorBoundary. | `AppLayout.test.tsx` (Phase 2.1) |
| `RouteErrorBoundary` | `app/RouteErrorBoundary.tsx` | React-Router-V7-ErrorBoundary. | Phase 2.1 |
| `RouteFallback` | `app/RouteFallback.tsx` | Suspense-Fallback (Skeleton-Page). | Phase 2.1 |
| `ThemeProvider` (NEU Phase 6.2) | `app/ThemeProvider.tsx` | `data-theme`-Attribut auf `<html>`, localStorage-Persistenz, `system`-Default. | `ThemeProvider.test.tsx` |

## Feature-Hooks (ab Phase 4)

| Hook | Datei | Rolle | Tests |
|---|---|---|---|
| `usePersona(id)` | `features/personas/hooks/usePersona.ts` | Laedt `getPersona` + `listPersonaVersions`. | `usePersona.test.tsx` |
| `usePersonaForm(persona, onSaved)` | `features/personas/hooks/usePersonaForm.ts` | RHF + Zod + `updatePersona` + `notify.success`. | `usePersonaForm.test.tsx` |
| `usePersonaPlaybooks(id)` (existierend) | `hooks/usePersonaPlaybooks.ts` | Lade + Toggle-State. Wird in Phase 4 leichter (Toast statt `status`). | bestehend |
| `usePlaybook(id)` | `features/playbooks/hooks/usePlaybook.ts` | Analog `usePersona`. | `usePlaybook.test.tsx` |
| `usePlaybookForm(playbook, onSaved)` | `features/playbooks/hooks/usePlaybookForm.ts` | Analog `usePersonaForm`. | `usePlaybookForm.test.tsx` |
| `useTokenMutations()` | `features/tokens/hooks/useTokenMutations.ts` | Kapselt `createToken`/`revokeToken`/Override. | `useTokenMutations.test.tsx` |
| `useListData<T>(loader)` (existierend) | `hooks/useListData.ts` | Generischer Loader. Bleibt. | bestehend |
| `usePersonas`/`usePlaybooks`/`useTokens` (existierend) | `hooks/*` | Wrap von `useListData`. Bleiben. | bestehend |

## Pages (`features/<x>/pages/*`)

Pages komponieren ab Phase 4 nur noch. LOC-Ziel: < 100 Zeilen je Page.

| Page | Datei | Route | Konsumiert |
|---|---|---|---|
| `LoginPage` | `features/auth/pages/LoginPage.tsx` | `/login` (public) | `useSession`, RHF, Zod |
| `PersonasPage` | `features/personas/pages/PersonasPage.tsx` | `/` | `usePersonas` |
| `PersonaNewPage` | `features/personas/pages/PersonaNewPage.tsx` | `/personas/new` | Phase 4: `usePersonaForm` (neu, fuer Create-Variante) |
| `PersonaDetailPage` | `features/personas/pages/PersonaDetailPage.tsx` | `/personas/:id` | `usePersona`, `usePersonaForm`, `usePersonaPlaybooks`, `PlaybookLinkItem` |
| `PlaybooksPage` | `features/playbooks/pages/PlaybooksPage.tsx` | `/playbooks` | `usePlaybooks` |
| `PlaybookNewPage` | `features/playbooks/pages/PlaybookNewPage.tsx` | `/playbooks/new` | Phase 4: `usePlaybookForm` (Create) |
| `PlaybookDetailPage` | `features/playbooks/pages/PlaybookDetailPage.tsx` | `/playbooks/:id` | `usePlaybook`, `usePlaybookForm` |
| `SettingsTokensPage` | `features/tokens/pages/SettingsTokensPage.tsx` | `/settings/tokens` | `useTokens`, `useTokenMutations`, `useAuthTokenContext` |

## Composed Feature-Komponenten (selektiv, ab Phase 5)

| Komponente | Datei | Anlass |
|---|---|---|
| `PlaybookLinkItem` | `features/personas/components/PlaybookLinkItem.tsx` | Ersetzt rohes `<label>` in `PersonaDetailPage.tsx:241`. Kapselt `Label` + `Checkbox`. |

Weitere Composed-Komponenten werden erst gezogen, wenn `>= 2` Pages
dasselbe Markup teilen.
