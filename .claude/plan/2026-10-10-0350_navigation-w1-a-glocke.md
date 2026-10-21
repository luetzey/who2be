# Navigation W1-a: Glocke in der Kopfleiste (Kanban t_c5453f25)

Spec: `navigation-transparenz-design-2026-10.md` §2.3 (Glocke), §2.2 (Arten),
Weichen N2 a (Link, kein Popover), N5 a (kein Polling). API: `GET
/v1/workspaces/{ws}/inbox/counts` aus W1-api (#897, `InboxCounts`).

## Fertig heisst

- Kopfleiste trägt rechts vor Sprache/Theme/Abmelden eine Glocke (`Bell`) als
  Link auf `/w/:ws/inbox`, auf allen Breiten sichtbar, 44 × 44 unter `md`.
- Zähler = `total`; 0 → kein Badge; > 99 → „99+“; laden/Fehler → kein Badge,
  Link funktioniert weiter.
- `aria-label` „Zu erledigen: 7 offen“ / „Zu erledigen: nichts offen“, ohne
  Zahl „Zu erledigen“; Badge `aria-hidden`; `aria-current="page"` + `bg-accent`
  auf `/inbox`.
- Hook `useInboxCounts(agentId?)` (geteilt mit W1-b/W1-c/W2-b): lädt beim
  Mount, bei Workspace-/Token-Wechsel, bei Rückkehr in den Tab
  (`visibilitychange`) und nach jeder eigenen schreibenden API-Anfrage (POST/
  PUT/PATCH/DELETE, entprellt). Kein Polling.

## Weichen (vorentschieden)

- „Nach eigenen Aktionen“: zentral im `request`-Helfer des API-Clients
  (`subscribeApiMutations`) statt an jeder Aktionsstelle. Grund: deckt jede
  heutige und künftige Erledigen-Aktion ab, ohne Fachseiten anzufassen
  (Hotspots Dashboard/AgentDetail bleiben unberührt). Preis: auch Schreib-
  anfragen ohne Bezug lösen eine Zählung aus; entprellt 300 ms, ein GET.
- Route `/inbox` folgt in W1-b; bis dahin führt der Link auf den Catch-all.

## Dateien

`api/client.ts`, `api/types.ts`, `hooks/useInboxCounts.ts` (+ Test),
`components/layout/AppShell.tsx` (+ Test), `i18n/locales/de.json`/`en.json`,
`changelog.d/` Fragment.

## Verifikation

`npm run lint`, `npm run typecheck`, `npx vitest run` (ganze Suite), e2e
`navigation.spec.ts` mobil, Fotos 1280/390 hell/dunkel + measure.json.
