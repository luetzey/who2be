# Web-Client: Pfad-Segmente zentral kodieren (CSPT-Schutz)

Status: aktiv · Karte t_3085bb86 · Basis origin/main f38979bd (nach #811)

## Ziel / Completion-Condition

Kein Wert (ID, Slug, Version, Typ, Workspace-ID) kann im Web-Client den
API-Pfad verlassen. Messbar:

1. `apps/web/src/api/client.ts` enthaelt keine ungetaggte Template-Literal- oder
   `+`-Verkettung mit `/` bzw. `?` und interpoliertem Wert mehr — ein AST-Test
   (TypeScript-Compiler-API) schlaegt sonst fehl.
2. `request`/`requestText`/`requestBlob` nehmen nur noch `ApiPath` (Typ-Ebene);
   `ApiPath` entsteht nur ueber den Tag `apiPath` bzw. `withQuery`.
3. Tests mit `../x`, `%2e%2e%2fx`, `a/b`, `''` fuer >= 5 Aufrufe (getMemory,
   getPersona, exportPersona, triageAgentMemory, exportWaTable, getTestReport,
   createApi-Workspace) — Pfad bleibt genau ein Segment im erwarteten Praefix
   oder der Aufruf wird ohne `fetch` abgelehnt.
4. Rot-Probe: dieselben Tests gegen das alte `client.ts` sind rot.
5. client.contract-Test gruen, Web-DoD gruen (Node 22), CI 17/17.

## Design (vorentschieden, Karte erlaubt begruendete Abweichung — keine)

- Neues Modul `src/api/path.ts`:
  - `apiPath` (Tagged Template): jeder interpolierte `string | number` ist
    genau ein Segment → `encodeURIComponent`. Abgelehnt: leer, `.`, enthaelt
    `..`, `/`, `\`, `?`, `#`. Ein interpoliertes `ApiPath` (z. B. `ws`) wird
    unveraendert uebernommen (bereits geprueft).
  - `withQuery(path, params)`: haengt `URLSearchParams` an (leer → nichts).
  - Ungueltige Werte werfen NICHT beim Bauen (die Api-Methoden sind
    synchrone Arrows; ein sync throw waere fuer `.then/.catch`-Aufrufer
    ein unbehandelter Fehler), sondern markieren das `ApiPath` als ungueltig.
  - `resolveApiPath(p)` (zentral in allen drei request-Helfern): ungueltig →
    `ApiError(404)` ohne Netzabruf; zusaetzlich Abwehr in der Tiefe: der per
    WHATWG-URL normalisierte Pfad muss dem gebauten Pfad gleichen.
- Status 404 statt 400: ein Wert, der kein Segment ist, kann keine
  existierende Ressource sein — und `MemoryDetailSheet` zeigt dann korrekt
  „nicht gefunden“ statt eines Ladefehlers mit Retry. Meldung =
  vorhandener Key `common:errors.apiError` → keine Locale-Aenderung.
- Query-Werte laufen durchgaengig ueber `URLSearchParams` (vorher teils roh:
  `?agent_id=`, `?status=`, `?format=`, `?page=`, `?against=`).

## Dateien (Budget 8 — genutzt 8)

1. `apps/web/src/api/path.ts` (neu)
2. `apps/web/src/api/path.test.ts` (neu, Unit + AST-Regressionsschutz)
3. `apps/web/src/api/client.ts` (alle Pfadbauten umgestellt)
4. `apps/web/src/api/client.cspt.test.ts` (neu, repraesentative Aufrufe)
5. `apps/web/src/api/client.errors.test.ts` (diff-Query: `+` statt `%20`, semantisch geprueft)
6. `apps/web/src/components/memory/MemoryDetailSheet.test.tsx` (`../x` geht nicht mehr ins Netz)
7. `changelog.d/web-client-cspt.security.md`
8. dieser Plan

## Schritte

1. [x] path.ts + Unit-Tests
2. [x] client.cspt.test.ts; Rot-Probe gegen altes client.ts: 65 von 73 rot
3. [x] client.ts umgestellt (Regex fuer die 158 Standardfaelle, Rest von Hand)
4. [x] AST-Waechter; Rot-Probe: `getPersona` roh → Waechter + 2 CSPT-Tests rot
5. [x] Web-DoD Node 22.23.3: lint 0 Fehler (90 Warnungen Baseline), tsc -b OK,
       i18n:check OK, test:coverage 247 Dateien / 1917 Tests gruen, Skip-Budget 0,
       build OK, license:check OK
6. [ ] Commit, Push, (getrennt) PR, CI 17/17

## Abweichungen

- Ablehnung als `ApiError(404)` statt eigenem Fehlertyp (Begruendung oben).
- `apiPath` lehnt zusaetzlich `?`/`#` im STATISCHEN Teil ab: beim Umbau fielen
  zwei Stellen auf, die die Query per `${params.toString()}` in den Pfad
  setzten — mit dem Tag waere der Query-String als Segment kodiert worden.
