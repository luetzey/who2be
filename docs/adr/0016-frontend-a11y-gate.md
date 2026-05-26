# ADR-0016 — Frontend-A11y-Gate: vitest-axe + eslint-plugin-jsx-a11y

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), Frontend-Umbau Phase 0

## Kontext

Das Frontend-Standards-Playbook verlangt ein "Accessibility-Minimum"
(semantisches HTML, sichtbarer Fokus-Ring, `aria-label` fuer Icon-only-
Buttons, Kontrast). Heute existiert kein automatisches A11y-Gate;
Regressionen wuerden erst beim manuellen Smoke-Run auffallen. Das
Repo hat bereits Vitest + Testing Library im Einsatz.

## Optionen

- **A — vitest-axe + eslint-plugin-jsx-a11y.** Headless, in bestehender
  Vitest-Pipeline. Findet strukturelle A11y-Issues (Labels,
  Role-Attribute, Heading-Order, Required-Properties auf Radix-Komponenten,
  Color-Contrast wenn explizite CSS-Color gesetzt). Lint blockt schon
  beim Schreiben. Findet ~80 % der WCAG-Issues. **Keine Browser-Infra
  noetig.**
- **B — @axe-core/playwright (E2E).** Findet zusaetzlich Color-Contrast
  in echter Render-Pipeline. Aber: keine Playwright-Infra im Repo →
  zusaetzliche Toolchain (Browser-Install, CI-Caching, Test-Server-
  Boot) fuer einen MVP-Owner-Tool zu schwer. Sinnvoll erst zusammen mit
  Visual-Regression (out-of-scope).
- **C — Nur jsx-a11y-Lint + manuelle Pruefung.** Billig, aber kein
  Regress-Schutz. Eine A11y-Regression durch eine spaetere Render-
  Aenderung wuerde unentdeckt mergen.

## Entscheidung

**Option A — vitest-axe + eslint-plugin-jsx-a11y.**

Umsetzung in Phase 5:

- Phase 5.1: devDeps `vitest-axe`, `eslint-plugin-jsx-a11y`, Setup-File
  `apps/web/src/test/setup.ts` registriert `toHaveNoViolations`.
  `eslint.config.js` aktiviert `jsx-a11y/recommended` als `error`.
- Phase 5.2: vier neue `*.a11y.test.tsx` fuer `PersonasPage`,
  `PlaybooksPage`, `PersonaDetailPage`, `SettingsTokensPage`. Jeder Test
  rendert die Page mit Mock-Daten und prueft
  `expect(container).toHaveNoViolations()`.
- Phase 5.5: CI-Job ergaenzt sichtbaren `a11y`-Step
  (`vitest --testNamePattern '\.a11y\.'`).
- Playwright + Visual-Regression bleibt ausdruecklich offen fuer ein
  Nachfolge-Projekt; bei Bedarf wechselt diese ADR auf Option B.

## Konsequenzen

- A11y-Regressionen werden automatisiert sichtbar. Pull Requests
  scheitern bei Violations.
- jsx-a11y blockt strukturelle Verstoesse schon im Editor (mit
  `lint-on-save`).
- Color-Contrast-Probleme aus Tailwind-Klassen werden erkannt, wenn der
  Test-DOM die berechneten Werte hat. Solange Tokens via CSS-Variablen
  laufen, ist das eingeschraenkt; Phase 6 (OKLCH-Skala) macht das
  systematischer.
- Kein zusaetzlicher Browser-Apparat in CI noetig. Build-Zeit bleibt
  stabil.
