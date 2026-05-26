# ADR-0014 — Frontend-Color-Space: OKLCH als Token-Quelle

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), Frontend-Umbau Phase 0

## Kontext

Die Design-Tokens in `apps/web/src/styles/globals.css` sind heute als
HSL-Channel-Variablen ausgedrueckt
(`--background: 0 0% 100%`, konsumiert via `hsl(var(--background))`).
shadcn/ui hat mit Tailwind v4 von HSL auf OKLCH umgestellt — die offizielle
Doku, Generatoren und neuere Themes nutzen OKLCH. Reibung droht, sobald
neue Primitives oder Themes aus dem shadcn-Universum importiert werden.

OKLCH ist wahrnehmungsuniform: ein Sprung von L=0.5 → L=0.6 erscheint
ueber den ganzen Farbraum gleich hell. Das macht systematische Stufen
(Mute, Accent, Hover) konsistenter — besonders im Dark-Mode.

## Optionen

- **A — HSL-Channel (IST belassen).** Null Migrationsaufwand, kein
  Risiko. Aber: Reibung gegen shadcn-v4-Default, jeder neue Generator-
  Snippet muss von Hand uebersetzt werden; Dark-Variante hat in HSL
  ueber den Farbraum hinweg uneinheitliche Helligkeitsspruenge.
- **B — OKLCH.** shadcn-v4-Default. Wahrnehmungsuniform. Migration trifft
  genau 1 File. Test-DOM testet keine Farbwerte → Test-Risiko null.
  Visuelles Risiko: Konversion HSL→OKLCH ist nicht 1:1, Akzente koennen
  geringfuegig abweichen → manueller Side-by-Side noetig.
- **C — Hybrid (neu OKLCH, alt HSL).** Doppelte Wahrheit im Token-File;
  bricht Standard 1 (Single Source of Truth pro Design-Entscheidung).

## Entscheidung

**Option B — OKLCH.**

Migration in Phase 6.1:

- Bestehende HSL-Channels in OKLCH-Aequivalente uebersetzen (manuell mit
  Generator wie `oklch.com`).
- `--color-*` im `@theme inline` schaltet von `hsl(var(--…))` auf
  `oklch(var(--…))` bzw. direkt auf OKLCH-Werte.
- Manueller Side-by-Side mit archiviertem `dist/`-Build aus Vor-6.1:
  0 sichtbare Regressionen ist Acceptance.

Migration ist **auf 1 File begrenzt** (`globals.css`), Komponenten
nutzen weiterhin nur die Token-Namen (`--color-background`, …) — keine
Komponentenaenderung noetig.

## Konsequenzen

- Token-Quelle ist OKLCH; neue shadcn-Snippets sind direkt importierbar.
- Dark-Mode-Stufen werden konsistenter; Hover-/Mute-Abstufungen koennen
  als Token-Reihen (`--color-accent-{50..900}`) bewusst definiert werden,
  wenn die Skala spaeter wachsen soll.
- Eine sehr alte Browser-Generation (z.B. < Safari 15.4, < Chrome 111)
  versteht OKLCH nicht — fuer Who2Be (Owner-Tool, moderne Browser) ein
  akzeptierter Tausch.
- Roll-Back ist 1-File-Revert.
