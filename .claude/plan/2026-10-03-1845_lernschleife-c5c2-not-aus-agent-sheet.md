# Lernschleife C5c-2 (Web): Not-Aus-Dialog und Detail-Sheet auf der Agent-Seite

Status: aktiv · Karte t_fcbecc46 · Basis origin/main 51a73412 (C5c-1 #805 gemergt)
Spec: gedaechtnisverwaltung-design-spec-2026-10.md §3, §4, §8, §13.6, §14, §15, §16 (C5c).
Schnitt: PM 2026-10-03, Option A (C5c-1 = t_7da03826, C5c-2 = diese Karte).

## Outcome
Auf `/memory` öffnet der Overflow im Seitenkopf („Weitere Aktionen“, nur
editor+) den Not-Aus „Automatisch Freigegebenes zurücknehmen…“; derselbe Dialog
öffnet über `?pullback=1`. Er zählt zuerst (`dry_run`), führt nur mit
`expected_count` aus und fragt bei 409 mit der neuen Zahl neu. Auf der
Agent-Seite öffnet der Chevron je Zeile das Detail-Sheet (`?entry=`).

## Akzeptanzkriterien (Karte)
- Not-Aus zählt zuerst (`dry_run: true`), Ausführung nur mit `expected_count`.
- 409 `memory_batch_count_mismatch`: kein stilles Wiederholen, Dialog bleibt
  offen und nennt die neue Zahl; erst ein neuer Klick führt aus.
- Nur editor+ sieht den Not-Aus (viewer: kein Overflow, `?pullback=1` wirkungslos).
  editor: `include_other_users: false` und der Satz „Das Nutzergedächtnis
  anderer Mitglieder kann nur ein Admin zurücknehmen.“
- Fremdes Nutzergedächtnis nie sichtbar: Vorschau zeigt nur `sample` (zusätzlich
  `visibleToMe`), Admin sieht Fremdes nur als Anzahl (`hidden_count`).
- Chevron auf der Agent-Seite öffnet das Sheet (kein toter Knopf).
- i18n de/en mit echten Umlauten; Screenshots 1280/390 hell+dunkel mit
  scrollWidth<=clientWidth (Dokument UND Dialog/Sheet); e2e-mobile grün; CI 17/17.

## Entscheidungen (aus Repo/Spec/API belegt)
- API (`MemoryRevokeAuto`, models/memory.py): `since` Pflicht (mit Zeitzone),
  `agent_id`, `include_other_users`, `dry_run`, `expected_count`. Server ist
  alles-oder-nichts → es gibt keinen Teilfehler; `learning.pullback.partial`
  entfällt (kein toter Text).
- `since` wird beim Zählen festgehalten und beim Ausführen identisch gesendet;
  sonst zählte „Letzte 24 Stunden“ beim Klick eine andere Menge als die Vorschau.
- „Seit“: `<input type="date">`, min heute−90 Tage, max heute; Beginn des
  lokalen Tages als ISO-Zeitpunkt.
- `include_other_users` = Rolle admin (beide Umfänge). „Nur ein Agent“ setzt
  `agent_id` (Auswahl aus `useAgents`).
- Vorschau neu bei jeder Änderung von Zeitraum/Umfang, entprellt 300 ms
  (`useDebouncedValue`), „Wird gezählt…“ `aria-live="polite"`, Primärknopf bis
  dahin deaktiviert mit Grund in `aria-describedby`.
- 409: neue Zählung (dry_run) mit gleichem `since`; Hinweis „Inzwischen sind es
  {{count}}. Erneut bestätigen?“ (vorhandener Key `approval.countChanged`).
- 0 Treffer: Text „Keine automatisch freigegebenen …“, Primärknopf [Schließen] `outline`.
- Erfolg: Toast „{{count}} Einträge zurückgenommen. Sie warten jetzt in ‚Zur
  Freigabe‘.“; Tab-Zähler und Listen laden neu. Abweichung Spec §8: kein Link im
  Toast (der `notify`-Wrapper kennt keine Aktion; +1 Datei) — der Tab-Zähler
  „Zur Freigabe“ steigt sichtbar.
- Mobil (< md): Bottom-Sheet volle Höhe, Kopf und Buttonzeile fest, nur der
  Mittelteil scrollt (Muster `AutoApprovalLimitsDialog`).
- Agent-Seite: `AgentMemoryCard` setzt `detailLinks` und hostet
  `MemoryDetailSheet` (aus C5c-1) mit `?entry=` und Router-State; Fokus beim
  Schließen ohne Auslöser auf den Kartentitel.

## Dateien (Zählregel: alle außer Plan, Grenze 12)
1. apps/web/src/api/types.ts — MemoryRevokeAutoRequest/Preview/Result
2. apps/web/src/api/client.ts — revokeAuto
3. apps/web/src/api/client.contract.test.ts — Pfad
4. apps/web/src/features/memory/components/PullBackDialog.tsx (neu)
5. apps/web/src/features/memory/components/PullBackDialog.test.tsx (neu, inkl. axe)
6. apps/web/src/features/memory/pages/MemoryPage.tsx — Overflow + `?pullback=1`
7. apps/web/src/components/memory/AgentMemoryCard.tsx — Sheet-Host + Chevron
8. apps/web/src/components/memory/AgentMemoryCard.test.tsx — Chevron öffnet Sheet
9. apps/web/src/i18n/locales/de.json
10. apps/web/src/i18n/locales/en.json
11. changelog.d/t-fcbecc46-memory-pullback.added.md

## Verifikation
- Node 22 (mise): `npm run lint`, `npx tsc -b`, `npm run test:coverage`,
  `npm run build`, `npm run license:check`, `npm run i18n:check`
- Rot-Proben je Zusicherung (dry_run zuerst, expected_count, 409 ohne
  Wiederholung, editor ohne include_other_users, viewer ohne Not-Aus, fremder
  Fakt in sample nicht gerendert, Chevron Agent-Seite).
- Screenshots 1280/390 hell+dunkel mit Messung im Dialog/Sheet (Scratch).
- e2e mobile lokal.

## Fortschritt
- [x] Umsetzung
- [x] Tests + Rot-Proben (10 Fälle PullBackDialog inkl. axe, 2 neue AgentMemoryCard;
  9 Rot-Proben alle rot: expected_count, 409 still wiederholt, editor
  include_other_users, fremder Fakt in sample, Knopf vor Zählung aktiv, viewer
  sieht Not-Aus, Agent-Seite ohne detailLinks, Sheet-Host fehlt, Contract-Pfad)
- [x] DoD web: lint 0 Fehler (90 Warnungen = Bestand main, neue Dateien sauber),
  tsc -b, test:coverage 1813/1813, Skip-Budget 0, build, license:check, i18n:check
- [x] Screenshots 1280/390 hell+dunkel (Scratch c5c2shots/out, measure.json):
  noOverflow überall; Fund bei 390: Agent-Select lief 13 px über den Rand
  (Grid-/Flex-`min-width:auto` bei langen Agentennamen) → `min-w-0` behoben,
  Nachmessung `wide: []`.
- [ ] Push, dann PR

## Abweichungen / Notizen
- Kein Link im Erfolgs-Toast (Spec §8): `notify` kennt keine Aktion; der
  Tab-Zähler „Zur Freigabe“ lädt neu. Folgekandidat, falls gewünscht.
- Test-Lauf lokal: Node 22.23.3 braucht `--no-experimental-webstorage`
  (localStorage-Falle); `NODE_OPTIONS` ist in der Sandbox gesperrt, daher
  `vitest --execArgv=--no-experimental-webstorage`. CI unberührt.
