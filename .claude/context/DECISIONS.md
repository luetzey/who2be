# DECISIONS — Warum so (append-only)

Tragende **Architektur**-Entscheidungen leben als ADR unter
[`../../docs/adr/`](../../docs/adr/) — das ist die kanonische Quelle
(vollständige, aktuelle Liste: siehe `docs/adr/`).
Diese Datei hält **leichtere, session-übergreifende** Entscheidungen, die keinen
eigenen ADR rechtfertigen. Append-only: nie umschreiben; eine Revision bekommt
einen neuen Eintrag mit Verweis.

## 2026-06-14 — LLM-Standards als Repo-Markdown (`docs/standards/`)
- **Entscheidung:** Die stehenden Engineering-Standards (zuvor extern) werden als
  self-contained Markdown unter `docs/standards/` materialisiert; `AGENTS.md` als
  tool-agnostischer Einstieg; `.claude/context/` als Projekt-Gedächtnis.
- **Begründung:** Repo muss ohne externe Quelle vollständig LLM-verständlich sein
  (Anti-Drift). Single-Source: wo ADR/Skill existiert, wird verlinkt statt kopiert.
- **Verworfen:** nur indexieren ohne Materialisieren (Standards blieben verstreut);
  Enforcement-Tooling (zu viel Pflege-Overhead jetzt).

## 2026-06-14 — Repo von externem Agent-Workspace entkoppelt
- **Entscheidung:** Persönlicher Agent-Bootstrap aus `CLAUDE.md` → gitignored
  `CLAUDE.local.md`; öffentliche Docs selbsttragend. `.claude/plan/` bleibt
  öffentlich (Referenz-IDs gewähren ohne Auth keinen Zugriff).
- **Begründung:** Public-Switch-Vorbereitung; öffentliche Datei soll nicht auf
  eine private Quelle als Autorität verweisen.

## 2026-06-14 — Kein History-Rewrite für den Public-Switch
- **Entscheidung:** Bestehende Commits/IDs bleiben in der History.
- **Begründung:** IDs/E-Mail gewähren ohne Auth keinen Zugriff; Rewrite-Risiko
  überwiegt den Nutzen.

## 2026-06-25 — Per-Agent-Connector-URL `?agent=<uuid>` (OAuth)
- **Entscheidung:** Connector-URL darf `…/mcp?agent=<uuid>` tragen; `authorize`
  akzeptiert kanonische Resource **oder** Basis + genau `?agent=<uuid>`. Hint wandert
  in den signierten Blob (kanonische Resource bleibt die Audience); Consent **sperrt**
  den Agenten hart (signierter Wert gewinnt, client-`agent_id` ignoriert). UI zeigt die
  fertige URL auf der Agent-Detail-Seite (`AgentConnectorSection`). Detail: ADR-0036-Addendum.
- **Begründung:** Claude dedupliziert Connectoren nach URL → eindeutige URL je Agent nötig.
  Membership-Prüfung bleibt das autoritative IDOR-Gate; Audience-Kette unangetastet.
  Security-Review ohne ausnutzbaren Befund.
- **Verworfen:** Subdomain-/Pfad-pro-Agent (Infra-Overhead pro Agent); Token im Connector/
  Systemprompt (unnötig, da OAuth-gebunden). **Fail-safe:** ohne Query gilt die Consent-Auswahl.
- **Offen:** E2E gegen echten Claude-Client (ob der `?agent=`-Query als OAuth-`resource`
  ankommt) — durch Fail-safe unkritisch.

## 2026-07-01 — MFA-Step-up: Hold-back im `apply()`, nicht neuer Context-Vertrag
- **Entscheidung:** Die `aal1`-mit-fälligem-Step-up-Session wird zentral in
  `SessionProvider.apply()` zurückgehalten (autoritatives Gate gegen die
  onAuthStateChange-Race), nicht nur im `signIn`-Rückgabewert. Die Challenge/
  Verify-Logik lebt direkt in der `LoginPage` (via `supabase.auth.mfa`, analog
  `MfaSection`) statt als neue `verifyMfa`-Methode im `SessionValue`-Interface.
  `getAuthenticatorAssuranceLevel` fällt bei Fehler fail-open auf „kein Step-up"
  zurück — das Backend-Gate `require_aal2` bleibt die harte Grenze.
- **Begründung:** `apply()`-Gate schließt die Race deterministisch (egal ob der
  Event aus signIn, Reload oder Refresh stammt). Kein Interface-Zwang auf ~28
  Test-Literale (`signIn: vi.fn()` bleibt zuweisbar; Rückgabetyp-Wechsel auf
  `{ mfaRequired }` ist kompatibel). Fail-open verhindert, dass ein getAAL-
  Ausfall den Login komplett blockiert, ohne die Server-Autorität zu schwächen.
- **Verworfen:** Globaler Step-up-Modal bei jedem 403 `mfa_required` (größerer
  Eingriff, App-weiter Zustand); `verifyMfa` im Context (Test-Churn ohne Nutzen).

## 2026-07-05 — OAuth-Refresh-Reuse: Reject-only statt Ketten-Revocation
- **Entscheidung:** Wiederverwendung eines bereits konsumierten Refresh-Tokens
  außerhalb des 30-s-Grace-Fensters wird nur noch mit `invalid_grant` + Warn-Log
  abgelehnt — `revoke_refresh_chain` läuft dabei NICHT mehr. Die Ketten-Revocation
  bleibt für echte Sicherheits-Events (Membership-Verlust beim Refresh /
  Deprovisioning). Bewusste Abweichung von RFC 9700 §4.14.2 (Revocation-on-Reuse).
- **Begründung:** MCP-Clients (Claude) sind multi-runtime: mehrere Agenten teilen
  sich die Connector-Tokens, veraltete Refresh-Kopien werden gutartig retried.
  Jeder Retry killte alle aktiven Access-Tokens der Kette (auch frisch rotierte
  der gesunden Runtime) → permanenter „verbunden, aber keine Tools"-Lockout
  (Repro gegen echten Stack; #293-Grace war zu eng und single-use). Die
  Revocation stoppte zudem keinen echten Dieb: sie widerrief nur `api_token`-
  Zeilen, nie die Refresh-Kette — ein Dieb mit Nachfolge-Refresh mintet einfach
  neu. Kosten (täglicher Lockout) ohne Nutzen (kein Diebstahl-Schutz).
- **Verworfen:** Grace-Fenster verbreitern (Retry-Loops fallen aus jedem endlichen
  Fenster und killen dann doch); Refresh-Rotation abschaffen (OAuth-2.1-Vorgabe
  für Public Clients); Ketten-Kill inkl. Refresh-Tokens „richtig" bauen (würde
  multi-runtime Clients erst recht hart aussperren).

## 2026-07-09 — Builder-/UI-Block (PR #301): vier kleine Richtungsentscheidungen
- **Trigger-Migration 0063 normalisiert ALLE Versions-Snapshots in-place** (nicht
  nur aktive, keine neuen Versionen): rein syntaktische Kanonisierung (`;`→`,`,
  trim, dedupe) — sonst zeigt jeder künftige Versions-Diff dauerhaft
  Trigger-Rauschen gegen die neue Kanonik. Write-Pfad normalisiert ab jetzt via
  Pydantic-Validator (`normalize_triggers`), Read-Pfad heilt sich beim Parsen selbst.
- **`?group=` ist Anzeige-Präferenz, kein Filter:** zählt nicht in `active`,
  wird von `reset()` nicht geräumt (Gruppierung reduziert nie die Treffermenge).
- **`get_persona(mode=…)`/`render(mode=…)` statt persistentem Agent-Modus:**
  Modus-Anwendung bleibt zustandslos pro Abruf (identity_add append,
  output_style_override replace, 422 mit Modi-Liste bei Unbekanntem); ein
  gespeicherter „aktiver Modus" pro Agent wurde bewusst verworfen (Zustand ohne
  belegten Bedarf).
- **Builder darf Templates via MCP verfassen (Seed-Korrektur zu ADR-0040):**
  Das Agent-Playbook verbot den Template-Bau via MCP, obwohl ADR-0040 +
  `system_prompt_write` ihn vorsehen — Seeds folgen jetzt dem ADR (draft→review;
  Aktivieren bleibt Mensch/UI). Placeholder-Format ist über den neuen
  `GET …/placeholders`-Katalog + `list_placeholders` zur Laufzeit entdeckbar
  statt nur im Frontend-Code.

## 2026-07-18 — Externe Tools (ADR-0043): Alias-Referenz, instruktiv, Naming

- **Entscheidung 1 — Ausbaustufe B (instruktiv statt Gateway):** Externe Tools
  sind versionierte Workspace-Aggregate mit beschreibenden Daten nur (Name,
  Server-Bezeichnung, Tool-Namen, Nutzungshinweise, Fallback-Text). KEINE
  URLs/Credentials-Speicherung — das ist die v1-Scope. Ein MCP-Gateway/Proxy
  (Ausbaustufe C: Who2Be routet Tool-Calls) wird als **späterer Ausbaupfad im
  ADR** dokumentiert, nicht gebaut. **Begründung:** (1) Instructions im
  System-Prompt sind der Anwendungsfall (der Agent liest, nicht ruft direkt),
  (2) Credentials-Store braucht neue Security-Architektur ohne Mehrwert fuer
  v1, (3) Proxy-Komplexitaet (Timeouts, Routing) lohnt sich erst mit Echo
  aus dem Feld. **Verworfen:** Credential-Store jetzt (zu viel Scope) —
  kommt mit C, wenn nötig.

- **Entscheidung 2 — Alias als Referenz, nicht UUID:** Pills speichern
  target_id = Alias (z. B. `todo`), nicht Tool-UUID. **Begründung:** Ein
  Workspace-Member bindert Tools neu (z. B. anderes Tool-Produkt für
  denselben Alias); Pills bleiben valid ohne Re-Edit, kein brittle UUID-
  Hardcoding. Ausbaupfad C wird aus dem Alias einen Proxy-Namespace bauen.

- **Entscheidung 3 — Naming: `external_tool`, nicht tool/capability/
  integration:** Entitätsname `external_tool` in der DB/API. **Verworfen:**
  `tool` (kollidiert mit MCP-Protokoll "tools"), `capability` (kollidiert mit
  `AgentCapability`), `integration` (zu generisch, kollidiert mit internen
  OAuth-Adaptern). Placeholder-Art heißt `tool-ref` (kurz, editor-freundlich).

- **Entscheidung 4 — Resource-Editor-Ausnahme:** Resource-Editor rendert
  Pills bauartbedingt NICHT (der Body-Pfad `render_template_body` ist nur
  für System-Prompts/Persona/Playbook verdrahtet, nicht für Resource-Body).
  Pills dort wären tote UI ohne Rendering-Semantik. Pills in Persona-/
  Playbook-/System-Prompt-Editoren: ja. Resource-Prosa: ohne Pills.
  **Begründung:** Architektur-Seite (Body-Rendering hat 4 Pfade, Resources
  nutzen einen nicht) — kein Feature-Limit, sondern Konsistenz.

- **Entscheidung 5 — Keine Feedback-Migration:** Feedback-Ziele werden
  erweitert um `entity_type='external_tool'`, aber es gibt **keine Migration**
  auf `feedback` oder `usage_event` Tabellen (kein neues Schema-Feld). Die
  Validierung lebt in Pydantic (`FeedbackEntityType`-Enum), nicht als DB-
  CHECK. **Begründung:** Feedback ist append-only und schema-flexibel
  (entity_type ist bereits Text, wird zur Laufzeit validiert). Null
  Migrations-Overhead, Schema bleibt stabil.

_Bei Wachstum: älteste Einträge zu Einzeilern komprimieren (Titel + Entscheidung
bleiben)._

## 2026-07-10 — Builder-Rework (PR #302): Pflege-Routine + drei Richtungsentscheidungen
- **Entscheidung 1 — Pflege als Playbook, nicht als Automatik:** Die Feedback-/
  Aufräum-Routine des Builders ist ein fünftes Managed-Playbook
  („Library-Pflege & Feedback-Lauf"), trigger-basiert und mit User im Loop
  (Sammeln → Triage → Zusammenhänge/Lücken → Freigabe → Drafts → Hand-Off).
  **Begründung:** Who2Be hat keinen Playbook-Scheduler; unbeaufsichtigtes
  Umsetzen von Feedback widerspräche dem Kurator-Prinzip („Feedback ändert nie
  selbst Inhalte"). Managed-Funde (Builder selbst) gehen in einen
  Repo-Hand-Off statt in 409-Write-Versuche. **Verworfen:** Composite mit dem
  Konsistenz-Check als Kind (Seed kennt kein Composition-Plumbing für managed
  Playbooks; lohnt erst bei einem zweiten Fall) — stattdessen Prosa-Verweis.
- **Entscheidung 2 — Sync statt Spiegel-Migration:** Neue/geänderte
  Builder-Playbooks erreichen Bestands-Workspaces über
  `sync_managed_builder_content` (neu: Insert-missing + Metadaten-Nachzug
  `type`/`tags`/`triggers` auf der Playbook-Row). **Begründung:** v1→v2/v2→v3
  liefen bereits migrationsfrei; 0047/0060 waren einmalige Backfills vor der
  Insert-Fähigkeit. Metadaten-Drift war real (Trigger-Änderung hätte nie
  verteilt).
- **Entscheidung 3 — Trigger-Hygiene:** Generische Trigger („pruefen",
  „qualitaetscheck") vom Konsistenz-Check entfernt (dokumentierte Kollision
  mit Code-/Repo-Audit-Anfragen); das Pflege-Playbook nutzt bewusst nicht den
  vom Vault-Playbook belegten Trigger „aufraeumen". Konvention im
  `_BUILDER_PLAYBOOKS`-Kommentar festgehalten.
- **Kontext:** Feedback-Backlog (Modi-Regel, fetch_agent-self-only,
  Trigger-Kollision) wurde im selben Zug als „erster Pflege-Lauf" über das
  Repo eingearbeitet; Beziehungs-Denken (search/find_usages vor Neuanlage,
  set_*-Verdrahtung danach) im Persona-Profil verankert.
  `BUILDER_CONTENT_VERSION` 3 → 4.

## 2026-07-10 — MCP tools/list pro Agent gefiltert: fail-open, SSoT in models (ADR-0042)
- **Entscheidung:** Per-Request-Filterung der MCP-Tool-Liste über eine
  FastMCP-Middleware (`PolicyFilterMiddleware`), gespeist aus dem neuen
  SSoT-Mapping `who2be_models.tool_requirements` (47 Tools), das auch der
  `tools-overview`-Prompt-Resolver konsumiert. Fehler bei der whoami-Auflösung
  ⇒ **fail-open** (ungefilterte Liste + Warn-Log); `on_call_tool` blockt
  ausgeblendete Tools nur bei erfolgreich aufgelöster Identity. Details: ADR-0042.
- **Begründung:** Durchsetzung bleibt autoritativ bei der API (ADR-0039) — die
  Filterung ist Kontext-Hygiene/Payload-Ersparnis, keine Security-Grenze. Ein
  fail-closed `tools/list` reproduzierte das bekannte „verbunden, aber keine
  Tools"-Symptom (vgl. Fixes 2026-07-05/07). Drift wird nicht organisatorisch,
  sondern per Paritätstests (MCP: registrierte Tools == Mapping; API: jede
  Gruppe referenziert echte Tool-Namen) zum CI-Fehler gemacht.
- **Verworfen:** FastMCP `enabled=False`/Tag-Filter (global pro Instanz,
  bricht Multi-Tenant-HTTP); fail-closed (UX-Regression wiegt schwerer als der
  kosmetische Schutz); `notifications/tools/list_changed` (TTL ≤ 300 s +
  Reconnect reichen dieser Iteration).
## 2026-07-10 — Builder v5: Modi + Konventions-Resource (drei Entscheidungen)
- **Entscheidung 1 — Modi nur für Haltungswechsel, nicht für Prozeduren:** Der
  Builder bekommt 3 Modi (Architekt = Default/Bau, Kurator = Pflege,
  Berater = Read-only-Auskunft ohne Phasen-Zeremonie). Abgrenzung: Modi tragen
  Stimme/Output-Stil, Playbooks tragen Prozedur — ein Modus wird nie zur
  Playbook-Kopie. **Verworfen:** 4. Prüfer-Modus (Haltung identisch zum
  Kurator, Konsistenz-Check bleibt reines Playbook).
- **Entscheidung 2 — Kurator bindet Playbook in Prosa, nicht via
  `playbook_id`:** Playbook-UUIDs sind workspace-spezifisch, der kanonische
  Seed-Content muss workspace-übergreifend identisch bleiben. Kopplung
  stattdessen über identische Trigger (Modus = Playbook) + Namensnennung im
  identity_add. Per-Workspace-Auflösung im Sync wäre Komplexität ohne
  Rendering-Mehrwert.
- **Entscheidung 3 — Konventionen als Managed-Resource statt Duplikation:**
  Neue Resource „Agent-Bau-Konventionen" (Trigger-Hygiene, Modi-Regel, Naming,
  Policy-Muster, Status-/Kurator-Prinzip, Managed-Grenzen, Beziehungs-Graph),
  per link_scope='resource' aus allen 5 Builder-Playbooks verlinkt (wird bei
  fetch_playbook als Volldokument mitgeliefert → Playbooks bleiben
  selbsttragend trotz gekürzter Konventions-Prosa). Schließt die eigene
  Wissens-Drift-Lücke (Builder-Playbooks hatten null Resource-Links). Seed/
  Sync um Resource-Insert-missing erweitert; weiterhin keine Spiegel-Migration.
  Deep-Copy-Befund: Klone kopieren Persona/Playbooks/Template, NICHT die
  Resource-Links — als Baseline fixiert. `BUILDER_CONTENT_VERSION` 4 → 5.

## 2026-07-10 — Feedback-Resolve für Agenten (Builder v6): Capability-Zuschnitt
- **Entscheidung (User): neue Capability `feedback_resolve`** statt Überladung
  von `promote_retire` oder Freigabe über `feedback_write`. Begründung:
  Schließen (addressed/in_progress/dismissed) ist Kurations-Macht — alle
  Fach-Agenten tragen `feedback_write` (melden), dürfen aber nicht fremdes
  Feedback wegtriagieren; saubere Trennung ADR-0039-konform. **Verworfen:**
  `feedback_write` (Kurations-Macht für alle), `promote_retire`-Überladung
  (Bedeutungs-Doppelung).
- Dabei geschlossen: `set_resolution` hatte für agent-gebundene Tokens kein
  Capability-Gate (nur Rollen-Gate) — jetzt `require_capability`.
- `get_feedback` additiv um `recent_feedback` (id/signal/note/resolution)
  erweitert — ohne IDs kein gezieltes Schließen, ohne Status
  Wiederabarbeitungs-Schleifen.
- **Sync-Novum:** Der Start-Sync zieht erstmals auch die `tool_policy` der
  Managed-Agenten (Builder/Builder-Lite) nach — Policies sind Teil des
  kanonischen Builder-Stands; ohne das bekämen Bestands-Builder neue
  Capabilities nie. Leitplanken im Content: Schließen nur nach User-Freigabe,
  `dismissed` nie ohne Note, Managed-Signale erst nach verteiltem Repo-Fix.
  `BUILDER_CONTENT_VERSION` 5 → 6.

## 2026-07-11 — Builder v7: Konventionen-Resource bleibt lazy, Prosa korrigiert
- **Kontext:** Die v5-Annahme „Agent-Bau-Konventionen wird bei fetch_playbook
  als Volldokument mitgeliefert" war nie Realität: Der Seed setzt kein
  `embedding_mode`, der Link-Default ist `lazy`, und `fetch_playbook` inlined
  nur `link_scope='resource'` + `embedding_mode='inline'`. Folge: fünf
  gleichlautende incorrect-Feedback-Signale (Pflege-Läufe 10.07.) — die
  „verbindlichen" Konventionen wurden faktisch nie geladen (usage_count ~0).
- **Entscheidung: Verdrahtung bleibt `lazy`; die Playbook-/Resource-Prosa wird
  auf den realen Pointer korrigiert und weist das explizite
  `fetch_resource`-Nachladen an** (resource_id aus dem `linked_blocks`-Eintrag,
  da UUIDs workspace-spezifisch sind — kein Hardcoding im kanonischen Content).
  **Begründung:** (1) `lazy` ist der dokumentierte Konventions-Default
  (Token-Budget; Builder-Lite existiert genau dafür — 38 Blöcke Inline-Payload
  bei jedem der 5 Playbook-Fetches wären das Gegenteil); (2) ein Wechsel auf
  `inline` müsste bestehende `playbook_resource_link`-Rows in allen Workspaces
  anfassen — der Start-Sync kann heute nur Content ersetzen und Links
  insert-missing anlegen, nicht updaten; der Prosa-Fix verteilt dagegen über
  den vorhandenen Content-Sync. **Verworfen:** `embedding_mode='inline'`
  (Kontext-Kosten + neues Sync-Plumbing für Link-Updates).
- Dabei mitkorrigiert: `fetch_playbook`-Docstring + `PlaybookWithResources`-
  Model-Doku (versprachen Volldokument für ALLE resource-Scope-Links) und der
  Seed-Kommentar („Volldokument-Referenz"); Persona-Abgleich: Agent-Playbook
  bietet im Hand-Off jetzt den Konsistenz- & Drift-Check an (Feedback-
  Mikrobeobachtung an der Builder-Persona). `BUILDER_CONTENT_VERSION` 6 → 7.
