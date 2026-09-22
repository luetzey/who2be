# #541 — Fehlgeschlagenes Offsite-Backup meldet Erfolg: Exit != 0 + self-hosted Heartbeat

- Datum: 2026-09-21
- Issue: luetzey/who2be#541
- Branch: `wt/i541-backup-alarm`
- Kanban: t_ed63ab79

## Owner-Entscheidung (verbindlich, nicht neu aufrollen)

Option **C — beides**:

1. Ein fehlgeschlagener Offsite-Sync macht den Backup-Lauf **rot** (Exit != 0).
   Das revidiert ausdrücklich die Gegenentscheidung aus ADR-0011 (C5a/C5b) und den
   Kommentar `backup.sh:89-91`. Der Vermerk wird **datiert nachgetragen**, nicht
   stillschweigend gelöscht.
2. Zusätzlich ein Dead-Man's-Switch über `BACKUP_HEARTBEAT_URL` (leer = aus), der auf
   einen **self-hosted** Empfänger zeigt. healthchecks.io und jeder andere Dritte sind
   vom Owner abgelehnt — deshalb entsteht auch kein VVT-Eintrag.

## Harte Bedingung

Der lokale GPG-Dump bleibt in **jedem** Fall erhalten. Nur die Erfolgsmeldung fällt weg,
nicht der lokale Pfad. Das wird belegt, nicht behauptet.

## Ist-Zustand (nachgemessen)

- `deploy/hetzner/scripts/backup.sh:94` — `|| { log "WARN: …"; exit 0; }` verschluckt den
  Fehlschlag von `restic backup`.
- `:98` — `restic forget` ist non-fatal ohne jede Folge.
- `:89-91` — der begründende Kommentar (ADR-0011).
- `deploy/hetzner/who2be/docker-compose.yml:288-308` — `backup`-Service, Profile `backup`.
- `deploy/hetzner/.env.example:148-152` — Backup-Sektion.
- `deploy/hetzner/RUNBOOK.md:707-794` — §Backup & Restore.
- `docs/cloud-hosting-owner-guide.md:500-509` — beschreibt den Ist-Zustand ("beendet sich
  mit Erfolg") und wird durch diesen Fix **stale**. Ziehen wir im selben PR nach.
- Keine Bash-Testsuite außer `deploy/hetzner/tests/test_headers.sh` (Smoke, Vorbild für
  Stil und Ablage).

## Design

### backup.sh

- Neu, optional: `BACKUP_HEARTBEAT_URL` — leer ⇒ aus ⇒ Verhalten wie bisher
  (Akzeptanzkriterium 3).
- Ping **nur bei vollständigem Erfolg**, als letzte Aktion. Alarmiert wird durch das
  **Ausbleiben** des Pings; das fängt zusätzlich die Fälle "Cron aus / Container weg /
  Host aus", die ein Exit-Code prinzipiell nicht fangen kann.
- `restic backup` scheitert ⇒ Fehler wird gemerkt, `restic forget` wird übersprungen
  (ohne Snapshot ist Forget sinnlos), **kein** Heartbeat, `exit 1`. Der lokale Dump wird
  dabei nicht angefasst — das explizit loggen, damit der Operator im roten Lauf sofort
  sieht, dass der lokale Pfad steht.
- `restic forget` scheitert ⇒ ebenfalls Fehler ⇒ kein Heartbeat, `exit 1`.
- Ein fehlgeschlagener Heartbeat-Ping ist selbst nicht fatal für den Backup-Status, wird
  aber als WARN geloggt und macht den Lauf rot (sonst wäre ein kaputter Alarmweg still —
  genau der Fehler, den dieses Issue behebt).
- Ping-Helper: `curl` bevorzugt, `wget` als Fallback (das RUNBOOK ruft das Skript auch
  direkt auf dem Host auf). Fehlt beides bei gesetzter URL ⇒ harter Fehler beim
  Env-Check, nicht erst am Ende nach 20 Minuten pg_dump.
- Der Kommentar `:89-91` wird zum datierten Vermerk umgeschrieben (Revision 2026-09-21,
  Issue #541), die alte Begründung bleibt im Wortlaut erkennbar.

### Dockerfile

`curl` in `deploy/hetzner/backup/Dockerfile` ergänzen (Alpine hat kein curl, busybox-wget
wäre der Fallback — wir wollen den geprüften Pfad im Container).

### compose + .env.example

`BACKUP_HEARTBEAT_URL: ${BACKUP_HEARTBEAT_URL:-}` durchreichen; `.env.example` trägt die
Variable leer mit Kommentar (Akzeptanzkriterium 5), inkl. des ausdrücklichen Hinweises,
dass hier **kein** externer Dienst stehen soll.

### Test (Akzeptanzkriterium 1 + 2, ohne Docker-Daemon)

Neu: `deploy/hetzner/tests/test_backup_alarm.sh` — fährt `backup.sh` gegen einen
PATH-Stub (`pg_dump`, `gpg`, `restic`, `curl` als Fakes) in einem Temp-Verzeichnis:

1. **Erfolgsfall offsite:** Exit 0, Dump liegt da, Heartbeat wurde genau einmal gepingt.
2. **Fehlerfall `restic backup`:** Exit != 0, **Dump liegt trotzdem da**, Heartbeat
   **nicht** gepingt. ⇒ das ist der Beleg für die harte Bedingung.
3. **Fehlerfall `restic forget`:** Exit != 0, Dump da, kein Ping.
4. **Lokal-only ohne Heartbeat-URL:** Exit 0, kein Ping, Verhalten unverändert.
5. **Lokal-only mit Heartbeat-URL:** Exit 0, Ping.

Damit ist der Nachweis reproduzierbar und braucht weder Docker-Daemon noch Postgres —
die im Issue vorhergesagte Eskalation entfällt. Der echte Container-Handlauf gehört
weiterhin in den Prod-Smoke (#454) und wird nicht erfunden.

### Doku

- `deploy/hetzner/RUNBOOK.md` §Backup & Restore: neuer Unterabschnitt "Alarmweg
  (Dead-Man's-Switch)" — was der Ping ist, wie ein self-hosted Empfänger minimal
  aussieht, **und wie man ihn testet** (Sync absichtlich auf unerreichbaren Host
  zeigen lassen, Ausbleiben des Pings abwarten) — Akzeptanzkriterium 4.
- `docs/adr/0011-backup-gpg-restic-offsite.md`: datierter Nachtrag 2026-09-21.
- `docs/cloud-hosting-owner-guide.md` §7 Punkt 2: auf den neuen Stand ziehen.
- `CHANGELOG.md` → Unreleased/Fixed.

## Out of Scope (ausdrücklich nicht mitgezogen)

RPO-24h / WAL-Archivierung, die ungetesteten SeaweedFS-Blob-Kommandos (#532), der
Restore-Drill (#454), Wechsel von Backup-Ziel oder Retention.

## Verifikation

```bash
bash -n deploy/hetzner/scripts/backup.sh
shellcheck deploy/hetzner/scripts/backup.sh deploy/hetzner/tests/test_backup_alarm.sh
bash deploy/hetzner/tests/test_backup_alarm.sh
```

Plus die Definition of Done aus CONTRIBUTING.md, soweit vom Diff berührt (der Diff fasst
keinen Python-/TS-Code an; die Suiten laufen trotzdem als Regressionsnachweis).

## Schritte

1. [x] Ist-Zustand lesen, Plan ablegen
2. [ ] `backup.sh` umbauen (Exit-Semantik + Heartbeat + datierter Vermerk)
3. [ ] Dockerfile / compose / `.env.example`
4. [ ] Test `test_backup_alarm.sh` schreiben und grün fahren
5. [ ] RUNBOOK / ADR-0011 / Owner-Guide / CHANGELOG
6. [ ] Verifikation + DoD, Branch pushen, PR öffnen
