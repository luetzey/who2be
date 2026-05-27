# Phase 7 — Component-Catalog (M-FE-7)

Branch: `feat/frontend-phase-7`. Vorgaenger: Phase 6 (gemerged). Bezug:
Approved-Plan-Datei `2026-05-26-1530_web-ui-design-system-tailwind-shadcn.md`
sowie ADR 0018 (In-Repo `/_catalog`-Route, DEV-gated).

## Ziel

- DEV-only `/_catalog`-Route, die alle UI-Primitives, Layout-Primitives und
  Data-Komponenten visuell demonstriert (eine Showcase-Sektion pro
  Komponente).
- In Prod-Build (`import.meta.env.DEV === false`) ist die Route nicht
  registriert; Aufruf landet auf dem `*`-Fallback (Navigate to `/`).
- Catalog liegt unter `src/app/catalog/` (sitzt zwischen `app/` und
  Features, nicht in `features/`, weil keine Domaene).
- Showcases verwenden ausschliesslich die Komponenten aus den Barrels
  `@/components/{ui,layout,data}` — keine direkte HTML-Suppe, kein
  Verstoss gegen die `no-restricted-syntax`-Regel.

## Tasks (sequenziell)

- 7.1 Neu: `apps/web/src/app/catalog/CatalogPage.tsx` (Index-Seite mit
  Sektion pro Showcase). Modify: `apps/web/src/app/routes.tsx` —
  `const isDev = import.meta.env.DEV`, Route `/_catalog` nur dann
  gerendert.
- 7.2 Neu: `apps/web/src/app/catalog/showcases/{button,input,textarea,
  card,badge,checkbox,label,alert,dialog,dropdown,form,skeleton,table}.tsx`.
  Eine Datei je Primitive; Default-Export ist eine `ShowcaseSection` mit
  `title` + variantenreichen Beispielen. CatalogPage importiert alle.
- 7.3 Neu: `apps/web/src/app/catalog/showcases/{layout,data}.tsx` —
  Showcases fuer Layout-Primitives (Container/PageHeader/Section/Stack)
  und Data-Komponenten (DataList/DataView/EmptyState/ErrorAlert/
  LoadingState).
- Catalog-interner Wrapper `apps/web/src/app/catalog/ShowcaseSection.tsx`
  fasst Titel + Beschreibung + Demo-Body zusammen (Card-basiert) —
  kein Verstoss gegen Standards, weil reines Doku-Layout.

## Verifikation

- `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` alle gruen.
- `npm run dev` → `/_catalog` liefert die Doku-Seite.
- `npm run build && npm run preview` → `/_catalog` faellt auf `/`
  zurueck (Navigate `*`).
- Bundle-Output zeigt eigene `catalog`-Chunks bzw. Catalog ist nicht
  Bestandteil des Prod-Bundles (DEV-Tree-Shake durch
  `import.meta.env.DEV`-Gate auf der Route-Ebene).

## Out of Scope

- Visual-Regression-Tests, Storybook-Migration, ARIA-Spielwiese ueber
  bestehende A11y-Tests hinaus, Doku-Markdown-Pipeline.
- Erweiterungen der Primitives selbst — der Catalog dokumentiert nur den
  Ist-Zustand.
