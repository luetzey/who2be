# Fix: „Importing a module script failed" — Stale-Chunk-Auto-Reload

_Stand: 2026-08-21 12:16 UTC · Branch: `claude/autonomous-code-agent-role-fsw6rh`_

## Problem (User-Report)

Beim Öffnen einer Seite erscheint sporadisch „Unexpected error / Importing a
module script failed". Das ist die `RouteErrorBoundary`
(`apps/web/src/app/RouteErrorBoundary.tsx`) mit der Safari-Fehlermeldung eines
fehlgeschlagenen dynamischen Imports.

## Wurzelursache

1. Alle Pages sind `React.lazy`-Chunks mit Content-Hash im Dateinamen
   (`apps/web/src/app/routes.tsx`).
2. Ein Deploy ersetzt `/assets/*` vollständig — alte Chunk-Dateinamen
   existieren danach nicht mehr (nginx cached Assets bewusst `immutable`).
3. Ein Browser-Tab, der noch das alte `index.html`/den alten Entry-Chunk im
   Speicher hat, fordert beim Navigieren einen alten Chunk an → 404 →
   `import()` rejected → Boundary zeigt den Fehler. Kein Auto-Recovery.
4. Verstärker: `apps/web/nginx.conf` setzt für `index.html` keinen
   `Cache-Control: no-cache` — der Browser darf das HTML heuristisch cachen
   und startet dann auch nach Reload mit veralteten Chunk-Referenzen.

## Lösung (2 Arbeitspakete)

### WP1 — Web: Auto-Reload bei Stale-Chunk-Fehler

- **Neu `apps/web/src/app/stale-chunk.ts`:**
  - `isStaleChunkError(error: unknown): boolean` — matcht die bekannten
    Browser-Meldungen für fehlgeschlagene dynamische Imports
    (Safari „Importing a module script failed", Chrome „Failed to fetch
    dynamically imported module", Firefox „error loading dynamically imported
    module").
  - `reloadOnStaleChunk(): boolean` — lädt die Seite genau EINMAL neu
    (`sessionStorage`-Guard mit Zeitfenster, damit kein Reload-Loop entsteht,
    wenn der Fehler eine andere Ursache hat); Rückgabe: ob ein Reload
    ausgelöst wurde.
- **`RouteErrorBoundary.tsx`:** in `componentDidCatch` bei
  `isStaleChunkError` zuerst `reloadOnStaleChunk()`; nur wenn kein Reload
  mehr erlaubt ist (zweiter Fehlschlag), wie bisher `ErrorAlert` rendern.
- **`main.tsx`:** `window.addEventListener('vite:preloadError', …)` →
  gleicher Guard/Reload (fängt Vite-Preload-Fehler außerhalb der Boundary).
- **Tests** (`apps/web/src/app/stale-chunk.test.ts` +
  Boundary-Test): Matcher-Positiv/Negativ-Fälle, One-Shot-Guard
  (zweiter Aufruf reloadet nicht), Boundary rendert Fallback erst nach
  verbrauchtem Guard.

### WP2 — Infra: `index.html` nie stale ausliefern

- `apps/web/nginx.conf`: SPA-Fallback (`location /`) bekommt
  `add_header Cache-Control "no-cache";` — Browser revalidiert das HTML bei
  jedem Laden (ETag bleibt aktiv, 304 ist billig). `/assets/` bleibt
  `immutable` (Hash-versioniert, korrekt).

## Nicht anfassen (Out of Scope)

- Kein Service Worker / Precaching, keine Retry-Logik pro Import.
- `deploy/hetzner/Caddyfile` unverändert (Caddy proxied nur zu `web:80`,
  Header kommen aus nginx mit; Security-Header-Politik F-12 bleibt in Caddy).
- Keine Änderungen an `routes.tsx`-Lazy-Struktur.

## Completion-Condition (/goal)

- `npm run lint`, `npx tsc --noEmit`, `npm run test:coverage`,
  `npm run build` grün (transkript-nachweisbar).
- Neue Tests decken Matcher + One-Shot-Guard + Boundary-Verhalten ab.
- Verhalten: Stale-Chunk-Fehler → automatischer einmaliger Reload
  (Nutzer sieht die neue Version statt der Fehlerseite); jeder andere
  Fehler → unverändert ErrorAlert.

## Übergabe-Bericht (Phase 4.1)

_Kalibrierung: kleiner Fix, 3 Quell-Dateien + 2 Tests + 1 nginx-Zeile —
Kurzform._

**Betroffene Elemente** (ripgrep-Rückwärtssuche, 2026-08-21):

- DIREKT: `RouteErrorBoundary.tsx` und `main.tsx` importieren
  `stale-chunk.ts`; `AppLayout.tsx` montiert die Boundary;
  `index.html` lädt `main.tsx`.
- TRANSITIV: alle Routen unter `AppLayout` (Fehlerpfad-Verhalten), sonst
  nichts — `stale-chunk.ts` hat keine weiteren Importeure.
- VERMUTET (unsicher): Browser-Verhalten bei `vite:preloadError` ist
  Laufzeit-Verdrahtung durch Vite — nicht statisch nachweisbar.

**Verifikation (Orchestrator-eigener Lauf, 2026-08-21):**

- `npm run lint`: 0 Errors (64 Warnungen, alle in unberührten Alt-Dateien)
- `npx tsc --noEmit`: grün
- `npm run test:coverage`: 177 Dateien / 1000 Tests grün; Statements
  86.73 %, Branches 81.13 % (Floor 79), Functions 82.68 %, Lines 87.75 %
- `npm run build`: `✓ built in 2.35s` (nur vorbestehende
  Chunk-Size-Warnung `blocknote-mantine`)

**Rest-Test-Liste (manuell):** Der echte Deploy-Fall (alter Tab → neuer
Build) ist lokal nicht automatisiert reproduzierbar — nach dem nächsten
Deploy einmal mit offenem Tab navigieren und prüfen, dass die Seite sich
selbst neu lädt statt „Unexpected error" zu zeigen. `sessionStorage`-
Private-Mode-Pfad ist testabgedeckt (kein Reload, ErrorAlert).
