# Responsive-Fundament (W0 von #431, Issue #438)

- Status: **in Arbeit**
- Datum: 2026-09-05, 22:20 UTC (25. Lauf)
- Issue: #438 (`agent-ready`, `size/S`), Eltern #431

## 1. Ask-Once-Gate

**Bestanden.** Outcome, fuenf Akzeptanzkriterien, explizites Out-of-Scope,
Verifikations-Kommandos und sechs vorentschiedene Weichen stehen im Body.

## 2. Muster-Entscheidung

**Keine Muster-Entscheidung noetig.** Alle drei Bausteine folgen vorhandenen
Vorlagen im Repo statt eine neue Struktur einzufuehren:

| Baustein | Vorlage |
|---|---|
| `useMediaQuery`/`useIsMobile` | `app/ThemeProvider.tsx:22-38` (matchMedia-Guard + `change`-Subscription), Hook-Stil aus `hooks/useDebouncedValue.ts` |
| `Sheet` | `components/ui/dialog.tsx` — derselbe Radix-Dialog, dieselbe `cva`-Mechanik |
| Designsprache-Abschnitt | bestehende §-Struktur, Eintraege in §12 Decision-Map und §13 Fuer AI-Agenten |

Die einzige Struktur-Frage — eigene Breakpoint-Tokens oder Tailwind-Defaults —
ist in Weiche 1 zugunsten der Defaults entschieden, mit Beleg: 25 `.tsx`-Dateien
nutzen die Prefixe bereits, und CLAUDE.md verbietet `tailwind.config.*`.

## 3. Das Besondere an diesem Paket

**Es darf sichtbar nichts tun.** Die drei Bausteine werden angelegt, aber kein
Konsument wird umgestellt — das ist W1 (AppShell) und spaeter. AC 4 macht das
pruefbar: ausser den neuen Dateien duerfen nur `components/ui/index.ts`,
`design-language.md` und `CHANGELOG.md` im Diff stehen.

Damit ist die Hauptgefahr nicht ein Fehler, sondern Scope-Creep: die Versuchung,
`AppShell` gleich mitzunehmen, weil der Hook ja da ist.

## 4. Verifikation

```bash
cd apps/web && npm run lint && npx tsc -b && npm run test:coverage && npm run test:a11y && npm run build
cd apps/web && npx vitest run src/hooks/useMediaQuery.test.tsx src/components/ui/sheet.test.tsx src/components/ui/sheet.a11y.test.tsx
```

Baseline (gemessen, 23. Lauf): 1043 Tests, Coverage 86,69 / 81,36 / 82,27 /
87,71 bei Floors 80/79/75/80.
