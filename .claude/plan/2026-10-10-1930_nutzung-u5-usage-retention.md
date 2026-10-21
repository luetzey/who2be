# Nutzung U5: Worker-Routine `usage-retention` (Owner E4b)

Karte: t_e40babcf (Kanban, Rund machen). Muster: `audit-retention` (PR #914,
`core/audit_retention.py`).

Owner E4b (Memo 2026-10-10): „Jetzt 13 Monate festlegen und die Routine
sofort bauen.“ Gegenstand von E4 sind die „rohen Nutzungsdaten“: jede
Auslieferung an einen Agenten als Zeile, also `usage_event`.

## Completion-Condition

- `who2be-worker list` zeigt `usage-retention` (`10 4 * * *`, catch_up).
- Integrationstest ueber den Runner: Zeilen 12 und 14 Monate alt, nur die
  14 Monate alte faellt; die Grenzzeile (genau 13 Monate) bleibt; Worker-Log
  zeigt Start und `succeeded {'deleted': 1}`.
- Integrationstest: `usage_stats`, `usage_list` und `agent_usage`
  (7/30 Tage, Tagesreihe, Agenten) liefern vor und nach dem Lauf dasselbe.
- Rot-Probe: Frist `0 months` bzw. Grenze `<=` ⇒ Test rot (im Handoff belegt).
- DoD aus CONTRIBUTING.md gruen.

## Entscheidungen (belegt)

- **Anker `created_at`, Kalendermonate, Grenze strikt (`<`).** Postgres
  `$slot - interval '13 months'`, Slot statt `now()` (Muster
  `core/memory_expiry.py`, `core/audit_retention.py`).
- **Alle Quellen** (`server` und `agent_report`): E4 betrifft die Rohzeilen
  insgesamt; die 30-Tage-Zaehler und die Phase-E-Fallraten je Version liegen
  weit innerhalb von 13 Monaten.
- **Kein Index, keine Migration.** EXPLAIN ANALYZE (lokal, Temp-Kopie mit
  `LIKE usage_event INCLUDING ALL`, 2 Mio. Zeilen ueber 14 Monate, Rollback):
  Seq Scan 494 ms mit 141 177 geloeschten Zeilen, 454 ms im Dauerzustand
  (nichts zu loeschen). Ein Lauf am Tag. Ein Index auf `created_at` muesste
  dagegen jeder INSERT auf dem heissen Auslieferungspfad mitpflegen.
- **Kein LIMIT-Batching.** Im Dauerzustand loescht ein Lauf einen Tag Rohdaten
  (Konzept 4.3: ~1 000 Zeilen/Tag und Workspace). Der erste echte Loeschlauf
  faellt fruehestens auf 2027-11 (Zaehlbeginn 2026-10-08), auch er ist nur
  ein Tag. Batching waere Code ohne Lastfall.
- **Zeitplan `10 4 * * *`**, Timeout 15 min, `catch_up=True` (wie
  `audit-retention`), kein Tabellen-Store.
- **`agent_access_log` bleibt ohne Frist (begruendet, nicht mitbehandelt).**
  Die Karte sagt „mitbehandeln, falls dort keine Frist besteht – sonst im PR
  begruenden“. Es besteht keine Frist; trotzdem nehme ich das Log nicht auf:
  - E4 betrifft laut Memo die rohen Nutzungsdaten (Auslieferungen),
    das Zugriffslog ist dort nicht genannt.
  - Zweck ist Rechenschaft (VVT V20, lit. c, Art. 5 Abs. 2): „welche Elemente
    sind **je** an welchen externen Modell-Anbieter gegangen“. Eine Frist
    nimmt diese Auskunft fuer alles Aeltere weg — das ist eine eigene
    Owner-Weiche, keine Folge von E4b.
  - Kein direkter Personenbezug (keine `actor_id`, nur Agent/Element/Tag),
    dedupliziert je Tag, Volumen gebunden.
  - Loeschen ist irreversibel, Nicht-Loeschen nicht: die Frist laesst sich
    spaeter mit derselben Routine nachziehen.
  Als Hinweis an @pm auf der Karte vermerkt.
- **ADR-0038-Nachtrag** im selben PR: „immutable/kein Delete“ gilt fuer die
  App-Rolle; die Aufbewahrung endet nach 13 Monaten durch den Worker
  (Owner-Connection). Folgen fuer die Anzeige benannt („zuletzt genutzt“ und
  Gesamtsummen reichen hoechstens 13 Monate zurueck).

## Dateien (14)

1. `apps/api/src/who2be_api/core/usage_retention.py` (neu)
2. `apps/api/src/who2be_api/worker/routines.py`
3. `apps/api/tests/test_worker_routines.py`
4. `docker-compose.yml`, `deploy/dokploy/docker-compose.yml`,
   `deploy/hetzner/who2be/docker-compose.yml` (Override-Durchreichung,
   Drift-Test `test_single_writer_guard.py`)
5. `.env.example`
6. `docs/compliance/vvt.md`, `docs/compliance/data-retention-and-erasure.md`
7. `docs/adr/0038-agent-usage-feedback-flywheel.md` (Nachtrag)
8. `deploy/hetzner/RUNBOOK.md`, `docs/cloud-erstinbetriebnahme.md`
9. `changelog.d/t-e40babcf-usage-retention.added.md`
10. dieser Plan

## Stand

- [ ] Code + Test + Rot-Probe
- [ ] Deploy/Doku/ADR
- [ ] DoD
- [ ] Push, PR
