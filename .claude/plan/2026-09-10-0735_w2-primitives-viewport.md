# W2-Primitives: Viewport-Breite auf 320 px (#513)

_Angelegt 2026-09-10, 43. Lauf. Basis: `main` @ `6572a59`._

## Auftrag

Owner: „setze 513 und 499 um". **#513 ist voll machbar und wird hier umgesetzt.**
**#499 ist es nicht** — siehe §Blocker unten; das Paket nennt den fehlenden
Docker-Daemon selbst als Abbruchgrund, und der Daemon fehlt nachweislich
(`dial unix /var/run/docker.sock: connect: no such file or directory`).

## Was #513 ändert

Drei Primitives, zwei Einzeiler an Aufrufstellen, drei neue Testdateien.
Alle sechs Weichen sind im Issue vorentschieden — hier wird **keine** neu
getroffen.

| Datei | Änderung |
|---|---|
| `components/ui/dialog.tsx:44` | `w-full max-w-lg` → `w-[calc(100vw-2rem)] max-w-lg`, dazu `max-h` + vertikaler Scroll |
| `components/ui/popover.tsx:44` | Cap `max-w-[calc(100vw-1rem)]` in den Default |
| `components/ui/dropdown-menu.tsx:29` | Cap `max-w-[calc(100vw-1rem)]` neben das bestehende `min-w-32` |
| `features/billing/components/BillingPanel.tsx:144` | `grid-cols-2` → `grid-cols-1 sm:grid-cols-2` |
| `features/playbooks/components/ResourceBlockLinkPicker.tsx:192` | dito |
| `dialog.test.tsx`, `popover.test.tsx`, `dropdown-menu.test.tsx` | neu, Muster von `sheet.test.tsx` (W0) |
| `CHANGELOG.md` | ein Eintrag unter §Unreleased → Changed |

## Der Grund, warum `w-` und nicht ein zweites `max-w-`

`cn()` läuft über `tailwind-merge`: zwei `max-w-*`-Klassen im selben String
löschen einander aus, `w-*` und `max-w-*` nicht. Effektivwert wird
`min(100vw − 2rem, 32rem)` — auf Desktop identisch zu heute, auf 320 px
288 px mit 16 px Rand. Dieselbe Eigenschaft trägt den Popover-Cap: er greift
auch bei `w-96` (`PlaceholderHelp.tsx:121`, der belegte Überlauf) und `w-72`
(`PlaybookListToolbar.tsx:200`), ohne die zwei bestehenden engeren
Aufrufstellen-Caps zu überschreiben — die stehen im `className` hinter dem
Default und gewinnen.

## Reihenfolge

1. **Test-first.** Die drei Testdateien zuerst, jeder neue Fall muss vor der
   Änderung rot sein (AK 6). Das ist der Beleg, nicht die Behauptung.
2. Primitives ändern, Tests grün.
3. Die zwei Grid-Einzeiler, dann das Gate-Kommando aus AK 4 gegenprüfen —
   es muss von zwei Zeilen auf null fallen.
4. CHANGELOG.
5. Gates: `npm run lint`, `npx tsc --noEmit`, `npm run test:coverage`,
   `npm run build`. Branches-Floor 79.

## Nicht anfassen

`apps/api`, `apps/mcp`, `packages/**`, `StatusActionBar` (kein Defekt, nach W3
verschoben), echter Fullscreen-Dialog (Weiche 3 verworfen), die zwei
bestehenden Popover-Caps, jede Datei außerhalb der Tabelle oben.

## Blocker: #499 ist in dieser Session nicht abschließbar

`docker info` scheitert — der Socket existiert nicht. Betroffen sind **drei
der sieben Akzeptanzkriterien**: `docker compose up -d --wait`,
`bash scripts/smoke.sh` und die TOTP-E2E-Journeys. Das Issue schreibt dazu
selbst:

> Melde dich statt weiterzumachen, wenn kein Docker-Daemon verfügbar ist
> (dann ist die Kern-Verifikation nicht fahrbar und das Paket nicht
> abschließbar).

Und im Verifikations-Abschnitt: „Ein Sprung über zwei Jahre
Migrationsgeschichte ist kein Pin-Bump — das ist der Grund, warum die
Verifikation unten nicht optional ist." Zwischen `v2.158.1` und der
Zielversion liegen **23 Migrationen**. Der Diff selbst wäre klein (drei Pins,
zwei MFA-Blöcke, vier Doku-Stellen); ungeprüft in drei Deploy-Stacks
geschoben ist er es nicht.

**Wird dem Owner vorgelegt**, statt still zu entscheiden.
