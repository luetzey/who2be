# Web-UI Design-System: Tailwind + shadcn/ui

Status: Vorschlag · Phase: 0/1 · Scope: nur `apps/web/`

## Ziel

Visuelles Design fuer die Web-UI etablieren, das **agentensicher** ist
(klare Standards, wenig Freiheitsgrade, lintbar) und **skaliert**
(vertikal geschnittene Features, austauschbare Primitives, zentrale
Design-Tokens). Keine Aenderung am Funktionsumfang — bestehende Seiten
(Personas/Playbooks/Tokens/Login) werden auf das neue System gehoben.

## Leitprinzipien

1. **Tokens statt Magic-Werte.** Farben, Spacing, Radius, Typo
   ausschliesslich aus einer Quelle (`styles/globals.css` `@theme`).
   Kein `#hex`, kein `px` im JSX.
2. **Primitives kapseln.** Alle Buttons/Inputs/Dialogs gehen ueber
   `components/ui/*` (shadcn). Direkte HTML-Buttons in Feature-Code sind
   ESLint-Error.
3. **Vertikal schneiden.** Domaenen-Code lebt in `features/<domain>/`
   (Pages + features-eigene Components). Globale Bausteine in
   `components/`. Cross-Feature-Imports sind verboten.
4. **Klein, typisiert, getestet.** Komponenten klein halten,
   Props-Interfaces explizit, Verhaltenstests bleiben gruen.
5. **Aenderung an einer Stelle.** Theme-Wechsel (Light/Dark/Brand)
   passiert in `globals.css`; Komponenten reagieren ueber Tokens.

## Tech-Auswahl

| Layer            | Tool                                 | Begruendung                                   |
|------------------|--------------------------------------|-----------------------------------------------|
| Styling          | Tailwind CSS v4                      | utility-first, agentenstandard, v4 = config-arm |
| Vite-Integration | `@tailwindcss/vite`                  | offizieller v4-Plugin, kein PostCSS-Setup     |
| Primitives       | shadcn/ui (auf Radix)                | Code gehoert uns, a11y baked-in               |
| Variant-API      | `class-variance-authority`           | typed Variants statt String-Salat             |
| Klassen-Merge    | `clsx` + `tailwind-merge` → `cn()`   | konfliktfreies Mergen                         |
| Icons            | `lucide-react`                       | shadcn-Default, treeshakable                  |
| Forms            | `react-hook-form` + `zod` + shadcn `Form` | typsicher, validiert, Pattern fuer alle Editoren |
| Klassen-Lint     | `eslint-plugin-tailwindcss`          | Klassen-Reihenfolge, Tippfehler, Konflikte    |
| Import-Lint      | `eslint` `no-restricted-imports`     | Cross-Feature- + Deep-Imports verbieten       |

Bewusst **nicht**: Storybook (kommt, sobald >15 UI-Primitives existieren),
Chromatic/Visual-Regression (Phase 2), Theme-Switcher (erst wenn gefordert).

## Ordner-Struktur

```
apps/web/src/
├── app/                       # App-Shell + Komposition
│   ├── App.tsx                # nur Provider + <RouterProvider/>
│   ├── routes.tsx             # zentrale Route-Definitionen
│   └── providers.tsx          # Session/AuthToken/QueryProvider-Kette
├── components/
│   ├── ui/                    # shadcn-Primitives (per CLI generiert)
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── dialog.tsx
│   │   └── ...
│   ├── layout/                # globale Layout-Bausteine
│   │   ├── AppShell.tsx       # Sidebar + Topbar + <Outlet/>
│   │   ├── PageHeader.tsx     # Title + Actions-Slot
│   │   └── Container.tsx
│   └── data/                  # domaenen-agnostische Daten-UI
│       ├── DataList.tsx       # uniform List + leer/lade/fehler
│       ├── EmptyState.tsx
│       ├── ErrorAlert.tsx
│       └── LoadingState.tsx
├── features/                  # vertikal pro Domaene
│   ├── auth/
│   │   ├── pages/LoginPage.tsx
│   │   └── components/LoginForm.tsx
│   ├── personas/
│   │   ├── pages/             # PersonasPage, PersonaDetailPage, PersonaNewPage
│   │   ├── components/        # PersonaList, PersonaForm, PersonaPlaybookPicker
│   │   └── index.ts           # Barrel: nur Pages exportieren (fuer Routing)
│   ├── playbooks/
│   └── tokens/
├── auth/                      # Provider/Context (bestehend, evtl. spaeter nach features/auth/lib)
├── api/                       # API-Client (bestehend)
├── hooks/                     # nur _globale_ Hooks
├── lib/
│   ├── utils.ts               # cn() Helper
│   └── supabase.ts
├── styles/
│   └── globals.css            # @import "tailwindcss" + @theme-Tokens
├── config.ts
└── main.tsx
```

**Regeln zur Struktur:**

- `features/<a>/` darf **nicht** aus `features/<b>/` importieren. Geteiltes
  wandert nach `components/` oder `hooks/`.
- Routing importiert **nur** aus `features/<x>/pages` (via Barrel).
- `components/ui/*` ist von Hand selten anzufassen — Anpassungen
  laufen ueber `cva`-Variants oder Tokens, nicht ueber Forks.

## Pfad-Alias

In `tsconfig.app.json`:

```json
"baseUrl": ".",
"paths": { "@/*": ["./src/*"] }
```

In `vite.config.ts` `resolve.alias` `"@": "/src"`.
Damit funktioniert der shadcn-CLI-Standard und Imports werden lesbar:
`import { Button } from "@/components/ui/button"`.

## Einrichtungs-Schritte

1. **Dependencies (in `apps/web/`)**
   ```
   npm i tailwindcss @tailwindcss/vite class-variance-authority \
         clsx tailwind-merge lucide-react react-hook-form zod \
         @hookform/resolvers
   npm i -D eslint-plugin-tailwindcss
   ```

2. **Vite/TS konfigurieren**
   - `@tailwindcss/vite` als Plugin eintragen
   - `@/*`-Alias in `tsconfig.app.json` + `vite.config.ts`
   - `src/styles/globals.css` anlegen mit:
     ```css
     @import "tailwindcss";
     @theme {
       --color-brand-500: oklch(0.62 0.18 264);
       --radius-md: 0.5rem;
       /* weitere Tokens */
     }
     ```
   - In `main.tsx`: `import './styles/globals.css'`

3. **shadcn initialisieren**
   ```
   npx shadcn@latest init     # CSS-Variables on, base color = slate
   npx shadcn@latest add button input label form dialog dropdown-menu \
                           card table badge alert skeleton sonner
   ```
   Generiert nach `src/components/ui/*` und `src/lib/utils.ts` (cn).

4. **Layout-Bausteine bauen**
   - `AppShell` (Sidebar mit Personas/Playbooks/Tokens, Topbar mit
     User-Menu + Logout)
   - `PageHeader` (Titel + Actions-Slot)
   - `DataList<T>` (`items`, `renderItem`, `loading`, `error`, `empty`)

5. **Bestehende Seiten migrieren** (jeweils mit gruenen Tests)
   - Pages aus `src/pages/` → `src/features/<domain>/pages/`
   - HTML-Buttons/Links → `<Button>` / `<Button asChild><Link/></Button>`
   - Listen → `DataList`
   - Forms → `react-hook-form` + shadcn `Form`
   - Routing in `app/routes.tsx` zentralisieren, `App.tsx` wird duenn

6. **Lint-Guardrails**
   - `eslint-plugin-tailwindcss` aktivieren (`classnames-order`, `no-contradicting-classname`)
   - `no-restricted-imports`:
     - verbiete `features/*/!(pages|index)` ausserhalb derselben Feature
     - verbiete `react-router-dom` direkte `<a>`-Wraps
     - verbiete `@/components/ui/*/internal/*`

7. **Skill aktualisieren**
   `.claude/skills/react-conventions/SKILL.md` ergaenzen um:
   - Tailwind + shadcn ist Pflicht; keine eigenen CSS-Dateien
   - Buttons/Inputs **nur** ueber `@/components/ui/*`
   - Neue UI-Primitives via `npx shadcn add` — nicht handschreiben
   - Variants via `cva`, Klassen-Merge via `cn`
   - Feature-Code in `src/features/<domain>/`; Cross-Feature-Imports verboten
   - Tokens **nur** in `styles/globals.css`

## Definition of Done

- `npm run lint`, `npx tsc --noEmit`, `npm test`, `npm run build` gruen
- Alle bestehenden Routen funktionieren visuell konsistent (gleicher
  Shell, gleicher Header)
- `src/pages/` ist leer/entfernt; alles unter `src/features/*/pages/`
- `react-conventions`-Skill aktualisiert
- README-Abschnitt „UI-Konventionen" in `apps/web/README.md` mit
  Verweis auf Skill

## Risiken & Tradeoffs

- **Migrationsaufwand**: 8 Pages + Tests. Risiko: Tests greifen auf
  DOM-Struktur zu — beim Umbau ggf. `data-testid` setzen, statt Tests
  umzuschreiben.
- **shadcn-Updates**: Komponenten gehoeren uns, also keine Auto-Updates.
  Tradeoff bewusst — dafuer keine Lock-in-API.
- **Tailwind v4 vs v3**: v4 hat weniger Tooling-Maturity, dafuer
  drastisch einfachere Config. Bei Problemen Rollback-Pfad: auf v3 +
  `tailwind.config.ts` umstellen, Struktur bleibt gleich.

## Folge-Tickets (out of scope hier)

- Storybook + Chromatic, sobald `components/ui/` >15 Bausteine hat
- Dark-Mode-Toggle (Tokens sind vorbereitet)
- i18n-Schicht (Texte aktuell hart deutsch)
