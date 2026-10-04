# ApprovalQueue: keine rohe Agent-UUID (t_3cd92765)

Status: umgesetzt · Karte t_3cd92765 (Wurzel t_44fae26f, Befund aus Review PR #816) · Basis origin/main b5f00d55 (#820 gemergt)

## Outcome
Gruppenkopf und Gruppenaktionen der Warteschlange „Zur Freigabe“ zeigen nie
eine rohe Agent-ID. Ist ein Agent nicht aufloesbar, steht dort
„Unbekannter Agent“ / „Unknown agent“. Fehlende Namen werden gezielt per
`GET /agents/{id}` nachgeladen.

## Ursache
`useApprovalQueue` laedt `api.listAgents()` ohne Paging, also hoechstens
DEFAULT_LIMIT=100. Fuer jeden weiteren Agenten lieferte `agentName()` den
Wert `null`, und `label: agentName(key) ?? key` zeigte die UUID. Die
Bezeichnung wurde dann von `groupApproveAgent(Aria)`, `moreInGroup`,
`onlyAgent` und `groupConfirm.title` uebernommen.

## Entscheidungen
- **(a) Fallback:** Es gibt eine Stelle, `Group.label` in `ApprovalQueue.tsx`,
  mit dem neuen Key `learning.approval.unknownAgent`. Alle Aktions-Texte lesen
  `group.label`, das deckt sie also mit ab. Gruppiert wird weiter nach
  `agent_id`, zwei Unbekannte bleiben deshalb zwei Gruppen. Es gibt keinen
  Tooltip mit gekuerzter ID, weil die Karte ihn nur optional nennt und die ID
  sonst wieder im DOM stuende.
- **(b) Gezieltes Nachladen statt Paging ueber X-Next-Cursor:**
  `api.listAgents()` gibt nur den Body zurueck. Fuer den Cursor muesste der
  Client-Vertrag (`client.ts`, `listAgents` in mehreren Features) geaendert
  werden, und alle Seiten zu laden kostet bei vielen Agenten O(n/100)
  Requests, auch wenn nur 1–2 Namen fehlen. Gezielt sind es hoechstens so viele
  Requests, wie Agenten in der geladenen Menge fehlen, gedeckelt bei 50.
  Der Pfad laeuft ueber die bestehende `getAgent`-Methode, also ueber
  `apiPath` (CSPT-Schutz aus #813).
- **Cache:** Ein `useRef<Map<id, Promise<Agent|null>>>` je Workspace (Reset
  bei `api`-Wechsel). Gleichzeitige Anfragen teilen sich ein Promise, ein
  Reload nach einer Aktion fragt nicht neu, und 403/404 wird als `null`
  gemerkt. Es gibt dabei keinen Toast und keinen `error`-State.
- **Gating:** `lookupAgents` laeuft nur bei `canManageAgents`, wie
  `listAgents`. Viewer loesen keinen `/agents/{id}`-Abruf aus (das ist
  getestet).
- **loadMore:** Nachgeladene Seiten koennen neue Agenten nennen. Sie laufen
  durch dieselbe Funktion und werden an `agents` angehaengt.

## Dateien (6, Budget 8)
- `apps/web/src/features/memory/components/ApprovalQueue.tsx`
- `apps/web/src/features/memory/hooks/useMemoryApi.ts`
- `apps/web/src/features/memory/pages/MemoryPage.test.tsx`
- `apps/web/src/i18n/locales/de.json`, `en.json`
- `changelog.d/approval-queue-unknown-agent.fixed.md`
- (dieser Plan)

## Verifikation
- Vitest (Node 22.23.3) `src/features/memory src/components/memory`: 87/87 gruen.
- Rot-Proben: Fallback auf `?? key` zurueckgesetzt fuehrt zu 2 roten Tests,
  Nachladen abgeschaltet zu 4 roten, Cache abgeschaltet zu 1 rotem Test.
- lint 0 Fehler / 91 Warnungen (wie main), `tsc -b` ok, `i18n:check` ok,
  `license:check` 0, `build` ok, `test:coverage` 248 Dateien / 1943 Tests gruen.
- Playwright gegen den w2b327-Stack (echtes Login, Rolle admin, echter 404 auf
  `GET /agents/{unbekannt}`): 1280/390 hell und dunkel, Kopf
  „Unbekannter Agent (5)“ neben „coder (1)“, kein Ueberlauf, UUID weder im Text
  noch in aria-label/title, genau 1 Lookup je Seitenaufruf.
