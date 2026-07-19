# Verzeichnis von Verarbeitungstaetigkeiten (VVT) — Art. 30 DSGVO

> ⚠️ **Disclaimer:** Engineering-/Betriebs-Dokumentation, aus dem DB-Schema und
> dem Deploy-Setup rekonstruiert. **Keine Rechtsberatung.** Inhaltlich
> verbindlich wird das VVT erst mit den Betreiber-Angaben (Verantwortlicher,
> Kontakt, Aufsichtsbehoerde, finale Auftragsverarbeiter-Vertraege). Alle
> `<PLATZHALTER: …>` sind vom Betreiber zu fuellen. Stand der abgeleiteten
> Fakten: 2026-07-08.

Dieses Verzeichnis ist die nach **Art. 30 Abs. 1 DSGVO** zu fuehrende Uebersicht
der Verarbeitungstaetigkeiten des Verantwortlichen. Es ist aus der Code-Realitaet
(Migrationen in `apps/api/src/who2be_api/migrations/`, Models in
`packages/models/`, Loeschpfad in `core/purge.py`) abgeleitet.

---

## 1 · Verantwortlicher (Art. 30 Abs. 1 lit. a)

- **Verantwortlicher:** `<PLATZHALTER: Firmenname, Rechtsform, Anschrift>`
- **Vertreten durch:** `<PLATZHALTER: vertretungsberechtigte Person(en)>`
- **Kontakt:** `<PLATZHALTER: E-Mail / Telefon>`
- **Datenschutzbeauftragter:** `<PLATZHALTER: Kontakt DSB oder „nicht benannt"
  inkl. Begruendung der Nicht-Benennungspflicht>`
- **Zustaendige Aufsichtsbehoerde:** `<PLATZHALTER: Landes-/Bundesdatenschutzbehoerde>`

> Querverweis: Diese Angaben spiegeln das Impressum (§5 DDG) und die
> Datenschutzerklaerung — siehe [`legal-texts-checklist.md`](./legal-texts-checklist.md).

---

## 2 · Verarbeitungstaetigkeiten (Art. 30 Abs. 1 lit. b — Zwecke)

| # | Verarbeitungstaetigkeit | Zweck | Rechtsgrundlage (Art. 6 DSGVO) |
|---|---|---|---|
| V1 | Registrierung & Kontoverwaltung | Bereitstellung des SaaS, Authentifizierung | lit. b (Vertrag) |
| V2 | Authentifizierung (GoTrue) | Login, Session, OAuth (optional) | lit. b (Vertrag) |
| V3 | Organisations-/Workspace-/Mitglieder-Verwaltung (RBAC) | Mandanten-/Rollenmodell | lit. b (Vertrag) |
| V4 | Einladungen (Workspace-Invitations) | Onboarding weiterer Nutzer | lit. b / lit. f |
| V5 | API-Token-Verwaltung (Agent-Zugriff) | maschineller Zugriff je Workspace | lit. b (Vertrag) |
| V6 | Inhalts-Verwaltung (Personas/Playbooks/Resources/Agents, versioniert) | Kernfunktion der App | lit. b (Vertrag) |
| V7 | Status-/Aenderungs-Historie (`status_history`) | Nachvollziehbarkeit, Versionsworkflow | lit. b / lit. f |
| V8 | Security-/Admin-Audit-Log (`audit_log`, WP-A/B) | Sicherheit, Nachweis (Rollen-/Token-/Loeschereignisse) | lit. f (berechtigtes Interesse) / lit. c |
| V9 | Zahlungs-/Abo-Abwicklung (nur Cloud-Edition, via Mollie) | Vertragsabrechnung | lit. b / lit. c (steuerl. Aufbewahrung) |
| V10 | Entitlement-Journal (`entitlement_history`, WP-A/C) | lueckenloses Tarif-/Zahlungsprotokoll (GoBD) | lit. c (§14b UStG/§147 AO) |
| V11 | Transaktions-Mails (Verify/Invite/Reset) | Konto-/Sicherheitskommunikation | lit. b / lit. f |
| V12 | Server-Logs / Zugriffsdaten | Betrieb, Missbrauchsabwehr | lit. f |
| V13 | Backups (verschluesselt, lokal + Offsite) | Datensicherung / Wiederherstellbarkeit | lit. f / lit. c |
| V14 | Konto-/Org-Loeschung (Soft-Delete + Hard-Purge) | Erfuellung Art. 17 (Loeschung) | lit. c / lit. b |
| V15 | OAuth-Connector (Authorization-Server fuer Remote-MCP: Authorization-Codes, Refresh-Tokens, dynamische Clients — Migration 0049, ADR-0034-Folge) | Verbindung von LLM-Clients (Claude/ChatGPT) per OAuth-Login statt Token-Copy-Paste | lit. b (Vertrag) |
| V16 | Agent-Usage-/Feedback-Events (`usage_event`, `agent_feedback` — Migration 0053, ADR-0038) | Nutzungs-/Qualitaets-Telemetrie konsumierender Agenten fuer Kurations-Aggregate | lit. f (berechtigtes Interesse) |
| V17 | Agent-Memory (`agent_memory` — Migration 0066, ADR-0044): von Agenten vorgeschlagene, menschlich kuratierte Fakten ueber Nutzer/Projekte | Persistentes, pro Agent steuerbares Langzeitgedaechtnis (Freigabe-Schleuse, UI-Verwaltung, Einzel-/Komplett-Loeschung) | lit. f (berechtigtes Interesse) / lit. a bei sensiblen Inhalten (Freigabe = Einwilligungsakt) |

> Hinweis: V8 und V10 (`audit_log`, `entitlement_history`) werden durch die
> Schwester-Pakete **WP-A/B/C** eingefuehrt; dieses VVT beschreibt den Ziel-Stand
> (siehe ADR-0031).

---

## 3 · Datenkategorien (Art. 30 Abs. 1 lit. c)

Abgeleitet aus dem DB-Schema. **Es gibt keine eigene App-User-Tabelle** —
Identitaetsdaten liegen in der von GoTrue verwalteten `auth.users` (PostgreSQL-
`auth`-Schema); die App-Tabellen referenzieren nur die `user_id` (UUID).

| Datenkategorie | Beispiel-Felder | Speicherort (Tabelle) | Quelle |
|---|---|---|---|
| Identitaets-/Stammdaten | E-Mail, (optional) Telefon, Passwort-Hash, Confirm-Zeitstempel | `auth.users` (GoTrue) | `docker-compose.yml` (`supabase/gotrue`) |
| Auth-Metadaten | `created_at`, `last_sign_in_at`, OAuth-Provider | `auth.users` (GoTrue) | GoTrue |
| Mitgliedschaft/Rollen | `user_id`, `role`, `invited_by`, `joined_at` | `org_member`, `workspace_member` | `migrations/0005`, `0007` |
| Einladungsdaten | **`email` (Klartext)**, `role`, `created_by`, `token_hash` (SHA-256), `expires_at`, `accepted_at`, `revoked_at` | `workspace_invitation` | `migrations/0017` |
| API-Token-Metadaten | `owner_id`, `name`, `token_hash` (SHA-256), `last_used_at` | `api_token` | `migrations/0001`, `0010` |
| Nutzergenerierte Inhalte | `owner_id`, `created_by`, `content` (jsonb) | `persona(_version)`, `playbook(_version)`, `resource(_version)`, `agent` | `migrations/0002`, `0003`, `0015`, `0023` |
| Status-/Aenderungs-Historie | `changed_by` (UUID), `from/to_status`, `changed_at`, `note` | `status_history` | `migrations/0012` |
| Security-/Admin-Audit | `actor_id`, `action`, `target`, `detail` (jsonb), `created_at` | `audit_log` (WP-A) | ADR-0031 |
| Abrechnungs-/Tarifdaten | `org_id`, `status`, `source` (mollie/cloud/manual_override/signed_license), `external_ref`, `created_by`, `reason`, `expires_at`, `grace_until` | `org_entitlement`, `entitlement_history` (WP-A/C) | `migrations/0030`, `0043`; ADR-0031 |
| Nutzungs-/Quota-Daten | `org_id`, `period`, `count` (org-Ebene, nicht personenbezogen pro Nutzer) | `mcp_usage` | `migrations/0031` |
| Webhook-Dedupe | `provider` (mollie), `event_id`, `received_at` (Zahlungsaktivitaets-Zeitpunkte) | `processed_webhook_event` | `migrations/0039` |
| OAuth-Connector-Daten | `user_id`, `workspace_id`, `agent_id`, `role`, `code_hash`/`token_hash` (SHA-256), `expires_at`, `consumed_at`; Client-Metadaten (`client_name`, `redirect_uris`) | `oauth_authorization_code`, `oauth_refresh_token` (via `api_token_id`), `oauth_client` | `migrations/0049`, `0062` |
| Agent-Usage-/Feedback-Events | `actor_id` (UUID), `agent_id`, `entity_type/-id`, `version`, `outcome` bzw. `signal`, `note` (Freitext), `created_at` | `usage_event`, `agent_feedback` (append-only) | `migrations/0053` |
| Agent-Memory | `agent_id`, `fact`/`context`/`triage_note` (Freitext, kann personenbezogene Angaben enthalten), `status`, `category`, `importance`, Nutzungs-Log (`retrieval_count`, `last_retrieved_at`) | `agent_memory` | `migrations/0066` |
| Loesch-Lifecycle | `user_id`, `requested_at`, `purge_after`, `purged_at`; `organization.deleted_at/purge_after` | `account_deletion`, `organization` | `migrations/0038` |
| Server-Logs/Zugriffsdaten | IP, User-Agent, Zeitstempel (Reverse-Proxy/App) | Caddy/App-Logs (nicht in der DB) | `deploy/hetzner/Caddyfile` |
| Backup-Daten | verschluesselter Voll-Dump (enthaelt alle obigen Kategorien) | `*.pgc.gpg` + restic-Repo | `deploy/hetzner/scripts/backup.sh` |

> **Keine besonderen Kategorien (Art. 9 DSGVO)** werden bewusst verarbeitet.
> Frei eingebbare Inhaltsfelder (Personas/Playbooks/Resources) koennen jedoch
> theoretisch personenbezogene Daten enthalten — `<PLATZHALTER: AUP/Hinweis,
> dass Nutzer keine besonderen Kategorien einstellen sollen>`.

---

## 4 · Kategorien betroffener Personen

- Registrierte Nutzer (Konto-Inhaber, Workspace-Mitglieder).
- Eingeladene Personen (E-Mail in `workspace_invitation`, ggf. vor Konto-Anlage).
- Zahlungspflichtige (Cloud-Edition; Zahlungsdaten Mollie-seitig).
- `<PLATZHALTER: ggf. in Inhalten genannte Dritte — abhaengig von der Nutzung>`.

---

## 5 · Empfaenger / Auftragsverarbeiter (Art. 30 Abs. 1 lit. d)

| Empfaenger | Rolle | uebermittelte Daten | Standort | AVV |
|---|---|---|---|---|
| Hetzner Online GmbH | Hosting/IaaS (Server, Volume, Storage-Box) | gesamte DB at-Rest, Backups | DE (`nbg1`/`fsn1`) bzw. FI (`hel1`), EU/EWR | `<PLATZHALTER: AVV mit Hetzner abgeschlossen?>` |
| Mollie B.V. | Zahlungsdienstleister (PSP) | Zahlungs-/Abodaten (Mollie-seitig); App speichert nur Status + `external_ref` | NL (EU/EWR) | `<PLATZHALTER: Mollie-Vertrag/AVV-Status>` |
| GoTrue (self-hosted, Supabase) | Authentifizierung | E-Mail, Auth-Metadaten | selbst gehostet (= Hetzner) | n/a (kein externer Verarbeiter, Eigenbetrieb) |
| Mail-/SMTP-Provider | Transaktionsmails | E-Mail-Adresse + Mail-Inhalt | `<PLATZHALTER: Provider + Standort>` | `<PLATZHALTER: AVV-Status>` |
| OAuth-Provider (optional: Google/GitHub) | Social-Login (falls aktiviert) | Login-Identifier/E-Mail | USA/global | `<PLATZHALTER: nur falls aktiviert — Drittland-Pruefung>` |

Technischer Stand siehe auch
[`deploy/hetzner/RUNBOOK.md` §Standort & Auftragsverarbeiter](../../deploy/hetzner/RUNBOOK.md#standort--auftragsverarbeiter).

---

## 6 · Drittlandtransfer (Art. 30 Abs. 1 lit. e)

Nach aktuellem technischem Stand findet **kein** Drittlandtransfer statt — alle
Kern-Verarbeiter (Hetzner, Mollie, self-hosted GoTrue) sitzen in der EU/im EWR.

**Ausnahmen, vom Betreiber zu pruefen:**
- Mail-/SMTP-Provider, falls ausserhalb EU/EWR.
- OAuth-Provider (Google/GitHub), falls Social-Login aktiviert wird → dann
  Garantien (SCC/Angemessenheitsbeschluss) pruefen und hier dokumentieren.
- `<PLATZHALTER: Ergebnis der Drittland-Pruefung + ggf. Garantien>`.

---

## 7 · Loeschfristen (Art. 30 Abs. 1 lit. f)

Vollstaendiges Konzept: [`data-retention-and-erasure.md`](./data-retention-and-erasure.md).
Kurzfassung:

| Datenkategorie | Frist / Trigger |
|---|---|
| Konto-/Inhalts-/Mitgliedsdaten | Soft-Delete bei Loeschwunsch → **30-Tage-Grace** → Hard-Purge (CASCADE), inkl. `auth.users` |
| Einladungs-E-Mail (Klartext) | Bereinigung nach Annahme/Ablauf (WP-D `cleanup_expired_invitations`) |
| Status-/Audit-Referenzen (`changed_by`/`actor_id`, inkl. `usage_event`/`agent_feedback`) | beim Purge **anonymisiert** (Sentinel `00000000-…-0`), Eintrag bleibt erhalten (WP-D, CMP-1) |
| Agent-Memory (`agent_memory`) | Hard-Delete jederzeit via UI (einzeln + „alle loeschen"); Loeschung des Agenten/Workspace/Org raeumt via FK-CASCADE (`agent_id → agent`, Migration 0066); kein `actor_id`-Feld, daher keine Anonymisierung noetig |
| OAuth-Codes/-Refresh-Tokens | Codes 60 s TTL/single-use, Refresh 30 Tage rotierend; laufender Cleanup (`cleanup_expired_oauth`) + Loeschung beim Account-Purge (Codes direkt, Refresh via `api_token`-CASCADE) |
| Backups | lokal 7 Tage; Offsite restic `keep-daily 7 / keep-weekly 4 / keep-monthly 6` |
| Entitlement-/Tarifdaten (`entitlement_history`) | **Aufbewahrung** trotz Erasure: §14b UStG/§147 AO (gesetzliche Ausnahme, ADR-0031) |
| Server-Logs | `<PLATZHALTER: konkrete Log-Retention (z. B. 7–30 Tage)>` |

---

## 8 · Technische & organisatorische Massnahmen (TOM, Art. 32)

Verweis statt Duplikat:
- Verschluesselung at-Rest (Postgres-Volume): `RUNBOOK.md` §Verschluesselung at-Rest.
- Transport-Verschluesselung (TLS) + Security-Header: `deploy/hetzner/Caddyfile`.
- Zugriffskontrolle / Mandantentrennung: RLS-Policies (`migrations/0036`, `0037`),
  Laufzeitrolle `who2be_app` (`NOSUPERUSER, NOBYPASSRLS`), RBAC
  (`workspace_member`).
- Append-only-Audit/Journal: `status_history`/`audit_log`/`entitlement_history`
  (REVOKE UPDATE/DELETE gegen `who2be_app`, ADR-0031).
- Backup-Verschluesselung: GPG + restic (`RUNBOOK.md` §Backup & Restore).
- `<PLATZHALTER: TOM-Anlage fuer AVV (vollstaendige Massnahmenliste)>`.
