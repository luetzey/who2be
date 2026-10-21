# Datenschutz E1-2: Worker-Routine `audit-retention` (Owner E1a)

Karte: t_8ca9cda6 (Kanban, Rund machen). Vorgaenger: E1-1, PR #911 (Migration
0106, `audit_log.anonymized_at`).

Owner E1a (Memo 2026-10-10): „Nach 12 Monaten loescht der Worker auch den
anonymen Rest."

## Completion-Condition

- `who2be-worker list` zeigt `audit-retention` (`0 4 * * *`, catch_up).
- Integrationstest: anonymisierte Zeilen 11 und 13 Monate alt, nur die 13
  Monate alte faellt. Gegenprobe: eine nicht anonymisierte Zeile mit
  `created_at` vor 13 Monaten bleibt stehen.
- Rot-Probe: Frist auf 0 bzw. Routine entfernt ⇒ Test rot (im Handoff belegt).
- DoD aus CONTRIBUTING.md gruen.

## Entscheidungen (belegt)

- **Anker ist `anonymized_at`, nicht `created_at`.** Belegt: VVT und
  Loeschkonzept §1 sagen „12 Monate ab Anonymisierung", Migration 0106 nennt
  `anonymized_at` ausdruecklich „ihr Anker". Die Karte schreibt „aelter als
  12 Monate"; gemeint ist der anonyme Rest (E1a), nicht das laufende
  Audit-Log lebender Workspaces — das loeschen wir nicht.
- **Kalendermonate:** `$slot - interval '12 months'` in Postgres.
- **Zeitplan `0 4 * * *`**, Timeout 15 min, `catch_up=True` (wie purge),
  kein Tabellen-Store. Liegt nach purge (03:30) und memory-expire (03:45),
  vor routine-run-retention (04:15).
- **Kein Index** (EXPLAIN siehe unten): taeglicher Lauf auf einer kleinen
  Admin-Event-Tabelle; ein Seq-Scan ist billiger als ein weiterer Index, den
  jeder INSERT pflegen muss. Keine Migration.
- Logik in `core/audit_retention.py` (Muster `core/memory_expiry.py`), Routine
  in `worker/routines.py`. Kein eigenes CLI (Owner W4 betrifft nur die zwei
  bestehenden Nachtlaeufe).

## Dateien

1. `apps/api/src/who2be_api/core/audit_retention.py` (neu)
2. `apps/api/src/who2be_api/worker/routines.py`
3. `apps/api/tests/test_worker_routines.py`
4. `docker-compose.yml`, `deploy/dokploy/docker-compose.yml`,
   `deploy/hetzner/who2be/docker-compose.yml` (Override-Durchreichung, sonst
   rot im Drift-Test `test_single_writer_guard.py`)
5. `.env.example`
6. `docs/compliance/vvt.md`, `docs/compliance/data-retention-and-erasure.md`
   (Frist „folgt" → aktiv)
7. `deploy/hetzner/RUNBOOK.md`, `docs/cloud-erstinbetriebnahme.md`
   (Routinen-Tabelle)
8. `changelog.d/t-8ca9cda6-audit-retention.added.md`

## EXPLAIN (lokal, Transaktion mit Rollback)

248 591 Zeilen `audit_log`, davon 20 000 anonymisiert:
`Seq Scan on audit_log … Rows Removed by Filter: 248591`,
Execution Time 57 ms. Ein Lauf am Tag → kein Index, keine Migration.

## Stand

- [x] Code + Test (Rot-Probe: Anker `created_at` statt `anonymized_at` ⇒ rot;
      Frist `0 months` ⇒ rot)
- [x] Deploy/Doku
- [ ] DoD
- [ ] Push, PR
