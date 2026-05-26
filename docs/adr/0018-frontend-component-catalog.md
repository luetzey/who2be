# ADR-0018 — Frontend-Component-Catalog: In-Repo `/_catalog`-Route in DEV

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), Frontend-Umbau Phase 0

## Kontext

Das Frontend-Standards-Playbook formuliert: "Komponenten als Bibliothek …
eingecheckte Primitives wie eine Bibliothek behandeln". Heute existiert
kein Schaufenster: wer eine Variante einer Primitive sehen oder eine
neue Variante diskutieren will, muss in den Code schauen. Ein
Component-Catalog macht die Bibliothek sichtbar — Varianten, Zustaende
(Hover, Focus, Disabled), Layout-Verhalten in echtem DOM.

Optionen reichen von Storybook (Industrie-Standard, eigene Toolchain)
ueber eine in-Repo-Route (nutzt vorhandene Vite+Router-Infra) bis hin
zu Verzicht.

## Optionen

- **A — Storybook 8.** Industrie-Standard, eigene Stories-Pipeline,
  isolierte MDX-Dokus, Addons fuer A11y, Controls, Backgrounds. Aber:
  zusaetzliche Toolchain (eigene Vite-Config, Storybook-CLI),
  CI-Build-Zeit deutlich groesser, Maintenance der Story-Dateien je
  Komponente.
- **B — In-Repo `/_catalog`-Route, DEV-gated.** Eine Route unter
  `/_catalog`, die im DEV-Build verfuegbar ist
  (`import.meta.env.DEV`), in Prod-Build 404. Showcases pro Primitive
  als kleine `.tsx`-Files. Kein extra Toolchain-Burden; gleicher Lint,
  gleiche Tests, gleicher Build.
- **C — Kein Catalog.** Spart Phase 7 (~3 Tasks). "Komponenten als
  Bibliothek" lebt dann nur in `component-map.md`.

## Entscheidung

**Option B — In-Repo `/_catalog`-Route, DEV-gated.**

Umsetzung in Phase 7:

- `apps/web/src/app/catalog/CatalogPage.tsx`: navigierbare Sektions-
  Liste (Buttons, Inputs, Cards, Alerts, Dialogs, DropdownMenus, Forms,
  Tables, Layout-Primitives, Data-Komponenten, Theme).
- `apps/web/src/app/catalog/showcases/<name>.tsx`: eine Datei pro
  Primitive bzw. Layout-/Data-Komponente. Jede Showcase zeigt alle
  Varianten + Zustaende.
- `apps/web/src/app/routes.tsx`: Route `/_catalog` nur, wenn
  `import.meta.env.DEV`. In Prod-Build kommt die Route nicht in den
  Bundle und Aufrufe landen im Catch-all (→ `/`).
- AppLayout greift, d.h. Catalog steht ebenfalls in light/dark und
  bekommt Updates der Tokens "fuer frei".

## Konsequenzen

- Catalog wird Teil der bestehenden Vite-Pipeline; kein Extra-Build,
  kein Extra-Lint-Setup. CI-Build-Zeit aendert sich nicht spuerbar.
- Showcases sind reine `.tsx`-Files — Aenderung einer Variante = ein
  PR auf der Showcase-Datei plus ggf. der Primitive-Datei. Beide sind
  disjunkt.
- Prod-Bundle enthaelt die Showcases nicht (DEV-Gate via
  `import.meta.env.DEV` + `Vite tree-shaking`). Wenn Phase 7 hier
  scheitert (Vite shakeable nur bei Top-Level-Import), wandert die
  Catalog-Route in einen eigenen Vite-Mode-Chunk.
- Verzicht auf Storybook-Addons (A11y-Addon, Controls) wird durch
  Phase-5-A11y-Tests und Showcase-Code direkt im Code kompensiert.
- Wenn das Projekt waechst und die Bibliothek externe Konsumenten
  bekommt, kann diese ADR auf Option A wechseln; die Showcase-Files sind
  als Storybook-Stories portierbar.
