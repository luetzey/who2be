# Retention- & Loeschkonzept — Who2Be

> ⚠️ **Disclaimer:** Engineering-/Betriebs-Dokumentation, aus dem Loeschpfad
> (`core/purge.py`, `repositories/account_repository.py`), den Migrationen und
> dem Backup-Skript rekonstruiert. **Keine Rechtsberatung.** Fristen und
> Abwaegungen (insb. Aufbewahrung vs. Loeschung) sind rechtlich zu verifizieren.
> Alle `<PLATZHALTER: …>` sind vom Betreiber zu fuellen. Stand der abgeleiteten
> Fakten: 2026-07-08.

Dieses Dokument beschreibt, **wie lange welche Daten aufbewahrt** und **wie sie
geloescht** werden — und wie der Konflikt zwischen DSGVO-Loeschpflicht (Art. 17)
und gesetzlicher Aufbewahrung (GoBD/§147 AO) aufgeloest wird. Adressiert
Audit-Befund **P5**.

---

## 1 · Loesch-Lebenszyklus (Soft-Delete → Grace → Hard-Purge)

Who2Be loescht Konten und Organisationen **zweistufig**:

1. **Soft-Delete (Loeschwunsch):**
   - `DELETE /v1/me` → `request_account_deletion()`: schreibt
     `account_deletion (user_id, requested_at, purge_after = now() + 30 Tage)`.
   - `DELETE /v1/organizations/{id}` → `soft_delete_organization()`: setzt
     `organization.deleted_at = now()`, `organization.purge_after = now() + 30 Tage`.
   - Wirkung: Daten werden aus den Lese-Pfaden (`/v1/me`, `/v1/organizations`)
     **ausgeblendet**, bleiben aber zur **Wiederherstellung waehrend der Grace**
     physisch vorhanden.
2. **30-Tage-Grace:** Karenzzeit (Schutz vor versehentlicher Loeschung). Der
   `purge_after`-Zeitpunkt ist idempotent (mehrfacher Loeschwunsch behaelt den
   fruehesten Termin).
3. **Hard-Purge (`who2be-purge`, Cron):** `purge_expired()` laeuft als **Owner**
   (RLS-Bypass) und entfernt alles, dessen `purge_after <= now()`:
   - **Organisationen:** `DELETE FROM organization …` — per `ON DELETE CASCADE`
     atomar inkl. Workspaces → Personas/Playbooks/Resources/Agents (+ Versionen),
     `org_entitlement`, `mcp_usage`.
   - **Konten:** loescht `api_token`, `org_member`, `workspace_member`, die
     persoenliche Organisation des Nutzers und ruft die **GoTrue-Admin-API** zum
     Loeschen von `auth.users` (E-Mail/Auth-Daten). Erst nach bestaetigtem
     Auth-Delete wird `account_deletion.purged_at = now()` gesetzt
     (idempotenter Retry, falls der Auth-Call scheitert).

---

## 2 · Anonymisierung ueberlebender Audit-Referenzen (WP-D)

Einige Tabellen referenzieren `user_id`, ohne per CASCADE mitgeloescht zu werden
(append-only Audit-/Historie). Damit der **Personenbezug** entfernt wird, ohne
die **Audit-Integritaet** zu zerstoeren, anonymisiert der Hard-Purge diese
Referenzen auf einen Sentinel statt sie zu loeschen:

| Tabelle | Feld | Behandlung beim Purge |
|---|---|---|
| `status_history` | `changed_by` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `audit_log` (WP-A/B) | `actor_id` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `usage_event` (Migration 0053, ADR-0038) | `actor_id` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `agent_feedback` (Migration 0053, ADR-0038) | `actor_id` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `test_case` (Migration 0089, ADR-0053) | `created_by` — **nur** bei `created_by_kind = 'human'` (bei `'agent'` steht dort eine Agent-ID) | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `test_run` (Migration 0089, ADR-0053) | `reported_by_user_id` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `agent_memory` (Migration 0091, ADR-0053) | `confirmed_by` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `agent_memory_event` (Migration 0091, ADR-0053) | `actor_id` — **nur** bei `actor_kind = 'human'` | → Sentinel `00000000-0000-0000-0000-000000000000` |
| `agent_memory` mit `scope='user'` (Migration 0091) | ganze Zeile (`subject_user_id`-gebunden) | beim Account-Purge in allen Workspaces **geloescht** + je Zeile `audit_log` `memory.deleted` ohne Inhalt, s. §4c |
| `workspace_invitation` | `email` (Klartext) | Bereinigung bei `accepted_at IS NOT NULL OR expires_at < now()` (`cleanup_expired_invitations`) |
| `oauth_authorization_code` (Migration 0049) | ganze Zeile (`user_id`-gebunden) | beim Account-Purge **geloescht** (Codes sind nach Konto-Loeschung wertlos); zusaetzlich laufender Cleanup abgelaufener/konsumierter Codes (`cleanup_expired_oauth`) |
| `oauth_refresh_token` (Migration 0049) | ganze Zeile (via `api_token_id`) | beim Account-Purge ueber den `api_token`-FK-CASCADE **geloescht**; zusaetzlich laufender Cleanup abgelaufener Tokens (`cleanup_expired_oauth`; konsumierte, nicht abgelaufene Glieder bleiben fuer Grace-Retry/Rotationsketten-Revocation) |

So bleibt nachvollziehbar, **dass** ein Statuswechsel/Audit-/Telemetrie-Ereignis
stattfand, aber nicht mehr **welche Person** dahinterstand. Diese Anonymisierung
wird durch **WP-D** umgesetzt (der Purge laeuft als Owner und darf trotz
Append-only-REVOKE aus WP-A das `UPDATE` ausfuehren); die Abdeckung von
`usage_event`/`agent_feedback`/`oauth_*` schliesst Befund **CMP-1**
(Standards-Review 2026-07-08).

> Hinweis: `audit_log`/`entitlement_history` sowie die Anonymisierungsschritte
> stammen aus den Schwester-Paketen **WP-A/B/D**; dieses Dokument beschreibt den
> Ziel-Stand (ADR-0031).

---

## 3 · Gesetzliche Ausnahme: `entitlement_history`

`entitlement_history` (Tarif-/Zahlungsjournal, Cloud-Edition) wird beim
Hard-Purge **bewusst nicht** geloescht oder anonymisiert:

- `org_id` ist **ohne** `ON DELETE CASCADE` modelliert — das Journal ueberlebt die
  Org-Loeschung.
- Rechtsgrundlage: gesetzliche Aufbewahrungspflicht (§14b UStG / §147 AO);
  Art. 17 Abs. 3 lit. b/e DSGVO erlaubt die Aufbewahrung trotz Loeschanspruch.
- Begruendung/Abwaegung dokumentiert in **ADR-0031** und der
  [GoBD-Verfahrensdokumentation](./gobd-verfahrensdokumentation.md).

`<PLATZHALTER: konkrete Aufbewahrungsfrist + Loeschung NACH Fristablauf>` — nach
Ablauf der gesetzlichen Frist ist auch dieses Journal zu loeschen; das Verfahren
dafuer ist vom Betreiber festzulegen.

---

## 4 · Backups & „Restore-only-Re-Deletion"

Backups (siehe `deploy/hetzner/scripts/backup.sh`,
[`RUNBOOK.md` §Backup & Restore](../../deploy/hetzner/RUNBOOK.md#backup--restore)):

| Pfad | Verfahren | Retention |
|---|---|---|
| Lokal (C5a) — Postgres | `pg_dump -Fc \| gpg --encrypt` | Dumps aelter als **7 Tage** geloescht |
| Lokal (C5a) — Objekt-Store | `aws s3 sync --delete` des Buckets (ADR-0048) | genau **ein** Spiegel, in place ueberschrieben |
| Lokal (C5a) — Tabellen-Store | `VACUUM INTO`-Snapshot je Area-SQLite (ADR-0049) | genau **ein** Snapshot je Area |
| Offsite (C5b) | `restic` via SFTP (Hetzner Storage-Box), alle drei in einem Snapshot | `keep-daily 7 / keep-weekly 4 / keep-monthly 6` + Prune |

Das `--delete` im Objekt-Sync und die Bereinigung verwaister Area-Snapshots
sorgen dafuer, dass geloeschte Daten nicht ueber den lokalen Spiegel weiterleben.

**Problem:** Ein zwischen Loeschung und Backup-Ablauf gezogenes Backup enthaelt
noch die geloeschten Daten. Eine selektive Loeschung **innerhalb** verschluesselter,
inkrementeller Snapshots ist nicht praktikabel.

**Verfahren „Restore-only-Re-Deletion" (Vorschlag, vom Betreiber zu bestaetigen):**
- Backups werden **nicht** punktuell editiert.
- Personenbezogene Daten in Backups laufen ueber die **Retention** aus dem
  Snapshot-Fenster heraus (spaetestens nach ~6 Monaten / `keep-monthly 6`).
- **Wird** ein Backup im Loeschfenster tatsaechlich **wiederhergestellt**, ist die
  betroffene Loeschung **unmittelbar erneut auszufuehren** (der Hard-Purge bzw.
  die Anonymisierung wird auf der restaurierten Instanz wiederholt), bevor die
  Instanz wieder produktiv geht.
- Dokumentations-/Bestaetigungspflicht: `<PLATZHALTER: Bestaetigung des
  Verfahrens + maximale Backup-Verweildauer als verbindliche Aussage>`.

---

## 4a · Agenten-Arbeitsbereich: WorkArea, Knowledge Base, Tabellen, Blobs

Der Agenten-Arbeitsbereich (ADR-0047/0048/0049) haelt Daten in **vier
Speichern** statt nur in Postgres — Loeschung heisst hier deshalb: alle vier
Wege gehen. Der `who2be-purge`-Lauf deckt sie ab (`core/purge.py`,
Abschnitt „WorkArea-/KB-Retention"), zusaetzlich zu den Loeschpfaden aus §1.

| Objekt | Speicher | Loeschung beim Org-/Account-Purge | Laufende Retention |
|---|---|---|---|
| `work_area` / `work_area_grant` | Postgres | CASCADE ueber `workspace` | — |
| `wa_artifact` (doc-Blockliste, Metadaten) | Postgres | CASCADE ueber `work_area` | `cleanup_expired_artifacts` (s. u.) |
| `wa_chunk` (Such-Passagen) | Postgres | CASCADE ueber `wa_artifact` | mit dem Artifact |
| `wa_blob` (Katalog: sha256/Groesse/Media-Type/Storage-Key) | Postgres | **kein** FK auf `workspace` → bleibt stehen, faellt ueber `cleanup_orphan_blobs` | `cleanup_orphan_blobs` (>24 h, unreferenziert) |
| Blob-**Objekte** (Binaerinhalte) | SeaweedFS/S3, selbst gehostet (`blobs/{workspace_id}/{sha256}`) | nicht vom DB-CASCADE erfasst → `cleanup_orphan_blobs` | s. „Blob-Sweep" |
| `wa_table` / `wa_category_rule` / `wa_source_convention` (Katalog) | Postgres | CASCADE ueber `work_area` | — |
| Tabellen-**Zeilen** | SQLite-Datei je Area (`WHO2BE_TABLESTORE_DIR/{workspace_id}/{area_id}.sqlite`) | nicht vom DB-CASCADE erfasst → `cleanup_deleted_area_stores` bzw. Betreiber-Schritt | s. „SQLite-Dateien" |
| `kb_node` / `kb_edge` / `kb_edge_evidence` / `kb_node_source_area` / `kb_conflict` | Postgres | `kb_node_source_area` CASCADE ueber `work_area`; die KB-Kerntabellen tragen **keinen** FK auf `workspace` und sind beim Workspace-Purge explizit zu loeschen | — |
| `agent_access_log` | Postgres | **explizites DELETE** im Purge (s. u.) | — |

### Retention-Semantik von `retention_days`

- `work_area.retention_days` ist die Aufbewahrungsfrist **der Area**, nicht des
  einzelnen Artifacts.
- **Default ist `NULL` = unbegrenzt** — und zwar fuer *alle* Areas, auch fuer
  private Agenten-Areas. Ein Agent verliert seinen Arbeitsstand nicht
  stillschweigend; wer eine Frist will, setzt sie ausdruecklich.
- Gerechnet wird auf `wa_artifact.created_at` (Zeitpunkt der Ablage), **nicht**
  auf `occurred_at` (fachlicher Zeitpunkt, darf beliebig weit zurueckliegen).
- Faellige Artifacts werden **geloescht, nicht anonymisiert** — sie sind
  Arbeitsmaterial, kein Audit-Nachweis. Die `wa_chunk`-Passagen fallen per
  CASCADE mit, die Suche verliert sie im selben Zug.
- Der Sweep ist idempotent und laeuft DB-weit als Owner; ein Lauf ohne faellige
  Artifacts ist ein No-op.

### Blob-Sweep (zwei Richtungen)

Katalog (`wa_blob`) und Objekt-Storage sind getrennte Systeme; jede Seite kann
ohne die andere zurueckbleiben. `cleanup_orphan_blobs` raeumt beide:

1. **Zeile ohne Artifact:** kein `wa_artifact.content_ref`/`blob_sha256` zeigt
   mehr auf den Blob **und** die Zeile ist aelter als **24 h** → Zeile loeschen,
   danach das Objekt. Diese Reihenfolge ist Absicht: ein liegengebliebenes
   Objekt faengt Sweep 2 ein, eine ueberlebende Zeile zeigte dagegen ins Leere.
2. **Objekt ohne Zeile:** Rueckstand einer gescheiterten Ingest-Transaktion
   (der Blob-PUT liegt *vor* dem COMMIT). Geloescht wird nur, was **aelter als
   24 h** ist — waehrend eines laufenden Ingests existiert ein Objekt ohne
   Katalog-Zeile voellig regulaer, und seine Loeschung waere Datenverlust. Das
   Alter liefert der Storage (`last_modified`); ein Store ohne Zeitquelle wird
   nicht aufgeraeumt.
   *Deckelung:* pro Lauf hoechstens `ORPHAN_OBJECT_DELETE_LIMIT` Loeschungen,
   pro Workspace hoechstens `ORPHAN_OBJECT_SCAN_LIMIT` gelistete Keys — der
   Purge laeuft neben dem Betrieb, nicht im Wartungsfenster. Was liegen bleibt,
   nimmt der naechste Lauf.
   *Bekannte Luecke:* gescopet wird auf Workspaces, die im Katalog vorkommen.
   Ein Workspace, dessen **allererster** Ingest scheitert, hat nie eine
   `wa_blob`-Zeile und faellt aus dem Scope; sein einzelnes Objekt bleibt
   liegen (Betreiber-Bereinigung ueber die Bucket-Uebersicht).

**Ohne konfigurierten BlobStore** (ADR-0048: der Normalfall einer Installation
ohne Objekt-Storage) laeuft nur Sweep 1 — die Katalog-Zeilen verschwinden, die
Objekte bleiben unberuehrt; der Lauf vermerkt das in seiner Zusammenfassung.

### SQLite-Dateien der Tabellen-Stores

Die Zeilen der Agenten-Tabellen liegen in **Dateien**, nicht in Postgres, und
haengen an keinem FK: ein `DELETE FROM work_area` laesst die Datei stehen.
`cleanup_deleted_area_stores` ist der Gegenpart und entfernt Datei + WAL/SHM
jeder Area, die es in `work_area` nicht mehr gibt.

**Karenzfrist (24 h):** eine Datei mit kuerzlicher Schreibaktivitaet (juengstes
`mtime` aus `.sqlite`/`-wal`/`-shm`) bleibt liegen, damit ein noch laufender
Schreibvorgang sein Ergebnis nicht verliert; der naechste Lauf nimmt sie. Die
Loeschzusage verschiebt sich damit um maximal einen Cron-Lauf — Begruendung im
ADR-0049-Nachtrag 2026-09-26.

**Bewusst zurueckhaltend:** angefasst wird ein Workspace-Verzeichnis nur, wenn
sein Name eine UUID ist **und** ein Workspace mit dieser ID existiert. Grund
ist der teuerste Fehlfall: liefe der Purge versehentlich gegen die falsche
(z. B. frisch migrierte, leere) Datenbank, saehe *jedes* Verzeichnis wie ein
geloeschter Workspace aus. Die Regel „unbekannt heisst Finger weg" macht daraus
eine Warnzeile statt eines Totalverlusts.

> ⚠️ **Kehrseite — Betreiber-Pflicht:** Nach einem Org-/Workspace-**Hard-Purge**
> existiert der Workspace nicht mehr, sein Verzeichnis bleibt damit
> ausserhalb des automatischen Sweeps und wird nur **gemeldet**
> (`unknown_store_dirs` in der Purge-Zusammenfassung, WARNING im Log). Die
> Verzeichnisse sind im Anschluss an einen Hard-Purge **manuell zu loeschen**;
> siehe [`RUNBOOK.md` §Tabellen-Store](../../deploy/hetzner/RUNBOOK.md#tabellen-store-backup-sqlite-je-workarea).
> `<PLATZHALTER: Betreiber bestaetigt das Verfahren + Frist fuer die manuelle
> Nachbereinigung>`.

### Zugriffslog (`agent_access_log`)

Das Log haelt fest, **welcher Agent wann welches Element gelesen/geschrieben
hat** — inkl. Modell-Anbieter/-Name zum Zugriffszeitpunkt (Snapshot). Es haengt
seit Migration 0080 **nicht** am Agent-CASCADE (`ON DELETE NO ACTION`), damit
ein normaler API-Delete das Compliance-Protokoll nicht mitnimmt. Der
**Hard-Purge ist der legitime Loeschpfad** und entfernt die Zeilen des
Workspace explizit, *bevor* die Organization-CASCADE die Agenten erreicht
(`repositories/account_repository.py`, `_PURGE_ACCESS_LOG_SQL`).
Zweck und Auswertung: [agent-access-log.md](./agent-access-log.md).

---

## 4b · Pruefaelle und Prueflaeufe (`test_case`, `test_run`)

Die Lernschleife (ADR-0053 §3.2, Migration 0089) haelt fest, **was** an einem
Agenten geprueft wird (`test_case`: Eingabe + erwartetes Verhalten) und **mit
welchem Ergebnis** eine Elementversion geprueft wurde (`test_run`: Urteil,
Antwort-Auszug, meldender Mensch bzw. Agent). Personenbezug tragen
`test_case.created_by` (bei `created_by_kind = 'human'`),
`test_run.reported_by_user_id` sowie die Freitexte `input`,
`expected_behavior` und `output_excerpt`, die Nutzerinhalte zitieren koennen.

**Loeschpfade:**

- **Org-/Workspace-Purge:** beide Tabellen haengen mit `ON DELETE CASCADE` an
  `workspace` **und** `agent`; `test_run` zusaetzlich per CASCADE an
  `test_case`. Anders als `agent_access_log` (FK `NO ACTION`) raeumt deshalb
  die Organization-CASCADE in `purge_organization` sie ohne eigenen Schritt
  ab — belegt in `apps/api/tests/test_test_case_compliance.py`.
- **Agent-Delete:** Pruefaelle samt ihren Laeufen fallen mit dem Agenten;
  `test_run.reported_by_agent_id` wird dagegen nur genullt
  (`ON DELETE SET NULL`), der Lauf eines Pruefalls an einem anderen Agenten
  bleibt stehen.
- **Kein Einzel-Delete ueber die API:** `who2be_app` hat auf `test_case` nur
  `UPDATE (status)` (Zurueckziehen statt Loeschen) und auf `test_run` nur
  `SELECT, INSERT` (append-only).
- **Account-Purge:** in fremden Workspaces ueberleben Pruefaelle und Laeufe
  den Account. `purge_account_data` anonymisiert dort die Personen-Spalten
  auf den Sentinel (s. §2) — als Owner, trotz der engen App-Grants. Die
  Freitexte bleiben als Pruefinhalt des Workspace stehen; sie gehoeren dem
  Workspace, nicht der meldenden Person.

**Auskunft:** der GDPR-Export (`services/gdpr_export_service.py`) liefert
beide Tabellen je Workspace als `test_cases` / `test_runs`.

---

## 4c · Gedaechtnis 2.0: Nutzergedaechtnis und Historie (`agent_memory`, `agent_memory_event`)

Migration 0091 (ADR-0053 §3.1) erweitert das Agent-Memory um zwei
Datenkategorien:

- **Nutzergedaechtnis** (`agent_memory.scope = 'user'`): Fakten **ueber**
  einen Menschen (`subject_user_id`), je Workspace und Nutzer (§3.1.1). Er
  haengt an keinem Agenten (`agent_id IS NULL` per DB-CHECK) und ueberlebt
  das Loeschen des einreichenden Agenten (`created_by_agent_id` ON DELETE
  SET NULL).
- **Historie** (`agent_memory_event`, §3.1.2): append-only, je Eintrag jede
  Aenderung mit Akteur (`actor_kind`, bei Menschen `actor_id`) und
  Schnappschuss (`before`/`after`, enthaelt den Fakt).

Agentennotizen (`kind = 'agent_note'`) duerfen keine Angaben ueber Dritte
enthalten (§3.1.5); fuer sie gibt es deshalb keinen Betroffenen-Pfad ausser
dem des Workspace.

**Fristen:**

| Was | Frist | Wirkung |
|---|---|---|
| unbestaetigte Eintraege (`pending`, automatisch aktivierte ohne `confirmed_at`) | **30 Tage** ab Anlage (`expires_at = created_at + 30 Tage`; gesetzte Annahme laut ADR-0053 Anhang B, in Phase F zu ueberpruefen) | Status `expired`, **keine** Loeschung: abgelaufene Eintraege bleiben Dublettenbasis (§3.1.3). Abrufe verlaengern nichts; nur eine menschliche Bestaetigung setzt `expires_at = NULL`. Den Verfallsjob liefert Paket C2b |
| bestaetigte Eintraege | bis zur Loeschung durch einen Menschen oder Purge | — |
| Historie | so lange wie ihr Eintrag | faellt per FK-Cascade mit |

**Loeschpfade:**

- **Einzel-/Komplett-Loeschung** durch einen Menschen: Hard-Delete (ADR-0044,
  Art. 17); die Historie geht per Cascade mit. Zurueck bleibt je Eintrag
  eine `audit_log`-Zeile `memory.deleted` mit Workspace, Akteur und
  Eintrags-ID — **ohne** Fakt, Kontext oder Historie (Weiche M5).
- **Org-/Workspace-Purge:** `agent_memory` haengt seit 0091 per FK-Cascade
  am Workspace, `agent_memory_event` ebenso; die Organization-CASCADE in
  `purge_organization` raeumt beides ab. Hier entsteht **keine**
  `memory.deleted`-Zeile je Eintrag — die Loeschung des Elternobjekts
  dokumentiert den Vorgang.
- **Account-Purge** (`purge_account_data`): das Nutzergedaechtnis des
  Menschen wird in **allen** Workspaces geloescht, nicht anonymisiert — ein
  Fakt ueber eine Person bliebe auch ohne ihre ID ein Fakt ueber sie. Je
  Eintrag eine inhaltsfreie `memory.deleted`-Zeile (Akteur leer = System).
  In ueberlebenden Zeilen fremder Workspaces werden `agent_memory.confirmed_by`
  und `agent_memory_event.actor_id` (nur `actor_kind = 'human'`) auf den
  Sentinel gesetzt (§2). Belegt in `apps/api/tests/test_memory_compliance.py`.

**Auskunft:** der GDPR-Export liefert je Workspace das Agentengedaechtnis als
`agent_memories` und das Nutzergedaechtnis **nur des exportierenden
Menschen** als `user_memories`, beide mit der Historie je Eintrag unter
`events`. Nutzergedaechtnis anderer Mitglieder steht nicht im Buendel.
`agent_memories` folgt der Rollengrenze der Oberflaeche (ab `editor`, wie
`MemoryService.list_memories`): fuer einen `viewer` bleibt der Block leer, und
`export_manifest.agent_memories` traegt `included: false` samt Begruendung.
Die Historie wird nur fuer die tatsaechlich exportierten Eintraege gelesen,
nicht workspace-weit. Belegt in `apps/api/tests/test_memory_compliance.py`.

---

## 5 · Server-Logs / Zugriffsdaten

Reverse-Proxy-Logs (IP, User-Agent, Zeitstempel) liegen ausserhalb der DB:
Caddy schreibt sie nach `/var/log/caddy/access.log` auf dem Volume `caddy-logs`
(`deploy/hetzner/Caddyfile`, Snippet `access_log`).

**Retention: 14 Tage.** Durchgesetzt wird sie von einem **Host-Cron**, der
taeglich `deploy/hetzner/scripts/rotate-access-log.sh` startet: das Skript
rotiert die aktive Datei und loescht aeltere Generationen
(Einrichtung und Quartals-Pruefung: [`RUNBOOK.md` §Access-Logs](../../deploy/hetzner/RUNBOOK.md#access-logs--ressourcen-limits)).
Die Caddy-Konfiguration allein traegt die Frist **nicht**: `roll_size 10MiB` /
`roll_keep 10` begrenzen die Groesse, und `roll_keep_for 336h` wirkt nur auf
bereits rotierte Generationen — bei geringem Anfrageaufkommen kann die aktive
Datei laenger als 14 Tage bestehen.

**Genau ein Loeschpfad, kein Rueckfall.** `roll_keep_for` erfasst
ausschliesslich die von Caddy selbst erzeugten Generationen
(`access-<ts>.log.gz`). Die taeglichen Generationen des Skripts heissen
`access.log.<ts>.gz` und fallen nicht darunter; fuer sie ist das Skript der
einzige Loeschpfad. Umgekehrt raeumt das Skript **beide** Namensklassen. Der
Loeschzeitpunkt liegt bewusst zwei Tage vor der Frist, damit 14 Tage die
Obergrenze und nicht der Mittelwert sind (Herleitung im Skript).

**Restrisiko, benannt statt weggelassen:** Faellt der Cron aus, wird die Frist
ueberschritten. Damit das nicht unbemerkt geschieht, endet jeder Fehlschlag mit
Exit != 0, ein *erfolgreicher* Lauf schreibt einen Zeitstempel
(`/var/log/who2be-logrotate.stamp`), und ein optionaler Dead-Man's-Switch wird
nur bei Erfolg gepingt. Der Quartals-Check im RUNBOOK prueft zuerst diesen
Stempel — ein leeres Log-Verzeichnis unterscheidet einen nie gelaufenen Cron
nicht von einem, der nichts zu tun hatte. Die Wirkung des Verfahrens ist
ausfuehrbar belegt (`deploy/hetzner/tests/test_access_log_rotation.sh`).

**Was gar nicht erst geschrieben wird:** Caddy redigiert `Cookie`,
`Set-Cookie`, `Authorization` und `Proxy-Authorization` per Default zu
`REDACTED` (die Server-Option `log_credentials`, die das abschalten wuerde, ist
nicht gesetzt). Query-Werte sind davon nicht erfasst — weil `api.<DOMAIN>` den
OAuth-Authorization-Endpunkt traegt (ADR-0036), ersetzt ein `format
filter`-Block die Parameter `code`, `token`, `access_token` und
`refresh_token`, bevor die Zeile die Platte erreicht.

Container-Logs (stdout/stderr je Dienst) sind unabhaengig davon auf 3 x 10 MB
gedeckelt (`logging:` in beiden Hetzner-Compose-Dateien).

---

## 6 · Retention-Uebersicht (Kurzreferenz)

| Datenkategorie | Aufbewahrung | Loesch-/Anonymisierungsverfahren |
|---|---|---|
| Konto-/Inhalts-/Mitgliedsdaten | bis Loeschwunsch + 30 Tage Grace | Hard-Purge (CASCADE) inkl. `auth.users` |
| Einladungs-E-Mail (Klartext) | bis Annahme/Ablauf | `cleanup_expired_invitations` |
| `status_history.changed_by`, `audit_log.actor_id` | Eintrag dauerhaft | beim Purge **anonymisiert** (Sentinel) |
| `usage_event.actor_id`, `agent_feedback.actor_id` (0053) | Eintrag dauerhaft (Kurations-Aggregate) | beim Purge **anonymisiert** (Sentinel) |
| OAuth-Authorization-Codes (`oauth_authorization_code`, 0049) | 60 s TTL, single-use | laufender Cleanup (`cleanup_expired_oauth`: abgelaufen ODER konsumiert) + Loeschung der User-Zeilen beim Account-Purge |
| OAuth-Refresh-Tokens (`oauth_refresh_token`, 0049) | 30 Tage TTL, rotierend | laufender Cleanup (`cleanup_expired_oauth`: abgelaufen) + CASCADE-Loeschung beim Account-Purge (`api_token`) |
| WorkArea-Artifacts + Chunks (`wa_artifact`/`wa_chunk`) | Area-Frist `retention_days`; **Default `NULL` = unbegrenzt** (auch privat) | `cleanup_expired_artifacts` (Loeschung, keine Anonymisierung) |
| Blob-Katalog + Objekte (`wa_blob`, SeaweedFS/S3) | bis unreferenziert + 24 h | `cleanup_orphan_blobs` (Zeile → Objekt; Objekt-Sweep nur mit Storage-Zeitstempel) |
| Tabellen-Zeilen (SQLite je Area) | bis Area geloescht | `cleanup_deleted_area_stores`; nach Workspace-Hard-Purge **manueller** Betreiber-Schritt |
| Knowledge Base (`kb_node`/`kb_edge`/…) | bis Loeschung des Workspace | Loeschung (kein `workspace`-FK → explizit) |
| `agent_access_log` | Eintrag dauerhaft (Compliance-Nachweis) | beim Purge **geloescht** (expliziter DELETE vor der Org-CASCADE) |
| Pruefaelle + Prueflaeufe (`test_case`/`test_run`, 0089) | mit Agent bzw. Workspace (kein API-Delete; Laeufe append-only) | Org-/Workspace-Purge: **CASCADE**; Account-Purge: `created_by` (nur `human`) + `reported_by_user_id` **anonymisiert** (Sentinel), s. §4b |
| Agent-Memory unbestaetigt (`agent_memory`, 0091) | **30 Tage** ab Anlage (gesetzte Annahme, ADR-0053 Anhang B) | Verfall auf `expired` (keine Loeschung, Job in C2b); menschliche Bestaetigung hebt den Verfall auf, s. §4c |
| Nutzergedaechtnis (`agent_memory`, `scope='user'`, 0091) + Historie (`agent_memory_event`) | bis Loeschung durch den Menschen bzw. Account-/Workspace-Purge | Account-Purge: **Loeschung** in allen Workspaces + `memory.deleted` ohne Inhalt; Historie per CASCADE; `confirmed_by` + menschliche `actor_id` **anonymisiert** (Sentinel), s. §4c |
| `entitlement_history` | gesetzliche Frist (§147 AO/§14b UStG) | **keine** Loeschung im Purge; Loeschung erst nach Frist |
| Backups lokal / Offsite | 7 Tage / bis 6 Monate | Retention-Ablauf + Restore-only-Re-Deletion |
| Server-Logs | Caddy-Access-Log 14 Tage; Container-Logs 3 x 10 MB je Dienst | Host-Cron startet taeglich `deploy/hetzner/scripts/rotate-access-log.sh` (rotiert + loescht beide Generationen-Namensklassen, RUNBOOK §Access-Logs) — der einzige Loeschpfad fuer die Frist; `roll_keep_for 336h` begrenzt nur Caddys eigene Generationen, `logging:`-Limits die Container-Logs |

---

## 7 · Code-Referenzen (Stand 2026-07-08)

- `apps/api/src/who2be_api/core/purge.py` — `purge_expired()`, `PurgeResult`,
  CLI-Entrypoint `who2be-purge`.
- `apps/api/src/who2be_api/repositories/account_repository.py` —
  `request_account_deletion()`, `soft_delete_organization()`, Purge-Helper,
  (WP-D) `cleanup_expired_invitations()`, (CMP-1) `cleanup_expired_oauth()`.
- `apps/api/src/who2be_api/migrations/0038_account_org_lifecycle.sql` —
  `account_deletion`, Soft-Delete-Felder.
- `apps/api/src/who2be_api/migrations/0049_oauth_connector.sql` —
  `oauth_client`/`oauth_authorization_code`/`oauth_refresh_token`.
- `apps/api/src/who2be_api/migrations/0053_feedback_flywheel.sql` —
  `usage_event`/`agent_feedback` (append-only, `actor_id`).
- `deploy/hetzner/scripts/backup.sh` — Backup-Retention.
- ADR-0031 — Append-only/Anonymisierung/Aufbewahrungs-Abwaegung.

**Agenten-Arbeitsbereich (§4a, Stand 2026-08-16):**

- `apps/api/src/who2be_api/core/purge.py` — `cleanup_expired_artifacts()`,
  `cleanup_orphan_blobs()`, `cleanup_deleted_area_stores()`,
  `run_retention_sweeps()`.
- `apps/api/src/who2be_api/migrations/0073_work_area.sql` — `retention_days`.
- `apps/api/src/who2be_api/migrations/0075_wa_blob.sql` — Blob-Katalog
  (kein `workspace`-FK).
- `apps/api/src/who2be_api/migrations/0079_agent_access_log.sql` +
  `0080_agent_access_log_hardening.sql` — Zugriffslog, FK `NO ACTION`.
- `apps/api/src/who2be_api/tablestore/engine.py` — `delete_area_store()`,
  `snapshot_to()` (`VACUUM INTO`).
- `apps/api/src/who2be_api/services/gdpr_export_service.py` — Art.-20-Buendel
  inkl. WorkArea/KB/Tabellen/Zugriffslog und (§4c) Agenten-/Nutzergedaechtnis
  mit Historie.
- `apps/api/src/who2be_api/migrations/0091_agent_memory_v2.sql` —
  Nutzergedaechtnis, Verfall, Historie `agent_memory_event` (§4c).
- ADR-0047/0048/0049 — WorkArea+KB, Blob-Storage, Tabellen-Store.
