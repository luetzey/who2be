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

## 2026-07-18 — Agent-Memory: Kurations-Schleuse statt Auto-Persistenz (ADR-0044)
- **Entscheidung:** Langzeitgedächtnis als agentische MCP-Tools mit 4-stufigem
  `memory_mode` (off < read_only < suggest < auto, Default off) + Freigabe-
  Schleuse (`pending` → menschliche Triage → `active`); `rejected` bleibt als
  Dedup-Basis erhalten; kein agent-seitiges update/delete in v1; System-Prompt
  trägt die Abfrage-Anweisung (`memory_directive` muss/soll), NICHT die
  Memory-Inhalte (kein Content-Push — User-Entscheidung nach zwei
  Design-Runden); `context`-Parameter nur für die Triage-Ansicht. Details:
  ADR-0044, Plan `.claude/plan/2026-07-18-1500_agent-memory.md`.
- **Begründung:** Konsistent mit dem Kurationsprinzip (ADR-0038: Agenten
  ändern nie selbst Inhalte); die Schleuse ist der strukturelle
  Injection-/PII-Schutz. Who2Be bleibt LLM-frei (keine Extraktions-Pipeline,
  kein Judge). FTS-first (tsvector `simple` + pg_trgm) hält On-Prem
  offline-fähig; pgvector bleibt Stufe B (ADR-0037-Linie).
- **Verworfen:** Kap.-11-Pipeline (Who2Be führt keine Chat-Loops aus);
  pgvector/Embeddings ab Tag 1 (neuer Infra-Baustein, On-Prem-Bruch);
  Presidio-PII-Gate (schwere Dependency, Triage ist das echte Gate);
  Soft-Delete (Repo-Konvention Hard-Delete wie agent_feedback);
  Content-Push-Placeholder (bewusst gegen entschieden, als Ausblick notiert).

## 2026-07-18 — Agent-Memory Runde 3: Laufzeit-Einbindung via get_persona (WP-6)
- **Entscheidung:** Der konfigurierte System-Prompt wird nicht live
  aktualisiert — Laufzeit-Injektionspunkt ist `get_persona` (Boot-Sequenz,
  fetch-time). `PersonaService.render` hängt für agent-gebundene Aufrufer mit
  `memory_mode != off` eine Gedächtnis-Sektion an `body_rendered`:
  muss/soll-Anweisung + Top-5 FREIGEGEBENE Memories (Daten-Rahmung,
  Nutzungs-Log-Bump). Revidiert „kein Content-Push" bewusst nur für die
  Laufzeit — die Freigabe-Schleuse garantiert, dass nur menschlich
  kuratierter Inhalt eingebettet wird. Security-Review-Fixes: Nutzungs-Log
  selbstlimitierend (max. 1 Write/Memory/Minute, N-1), `_require_human`
  prüft policy UND agent_id (N-2), Cap zählt bewusst alle Status (N-3,
  dokumentierter Selbst-DoS, menschlich aufräumbar).
- **Begründung:** User-Einwand: Agenten laden zur Laufzeit nur
  Persona/Playbooks/Resources — eine Anweisung, die nur im
  Konfigurations-Prompt lebt, erreicht laufende Agenten nicht zuverlässig.
- **Verworfen:** Nur-Anweisung ohne Fakten (hängt weiter an der
  Tool-Disziplin des Modells); Status quo (nur Tool-Beschreibungen).

## 2026-07-19 — Placeholder-Kind `memory` (ADR-0044-Addendum)
- **Entscheidung:** Expliziter Placeholder-Kind `memory` für positionierbare
  Gedächtnis-Hinweise; Texte aus EINER Quelle (`memory_prompt_block`:
  Placeholder + tools-overview-Fallback + get_persona-Laufzeit-Sektion).
  Doppel-Render-Schutz via Renderer-Body-Scan
  (`RenderContext.has_explicit_memory`) statt Auto-Append-Abschaltung —
  Bestands-Templates rendern unverändert. Seed-Templates + agent_builder
  tragen den Placeholder nach der tools-overview-Pill
  (`BUILDER_CONTENT_VERSION` 9). `off` rendert leer, kein Miss; Direktive
  bleibt reine Textstärke.
- **Begründung:** Builder-Briefing (Hand-Off); Auto-Append allein kann die
  Position nicht steuern. Briefing-Abweichungen dokumentiert: Tool-Gating
  existierte bereits (ADR-0042), „Mit Freigabe"-Copy auf reale
  Pending-Schleuse korrigiert (keine Chat-Bestätigung).
- **Verworfen:** Auto-Append ersatzlos streichen (Regression für
  Bestands-Workspaces mit user-editierbaren Default-Templates).

## 2026-07-19 — Builder-Gedächtnis: suggest, nicht auto (Content-Stand 10)
- **Entscheidung:** Builder + Builder-Lite bekommen `memory_mode='suggest'`
  + `memory_directive='recommended'` in der zentral verwalteten Seed-Policy
  (Verteilung via Policy-Sync, BUILDER_CONTENT_VERSION 10). Aktivierung über
  die UI war nicht möglich (Managed-Lock) — Policy-Änderung ist Repo-Sache.
- **Begründung:** Konsistent zum Kurator-Prinzip des Builders (Vorschläge,
  keine Auto-Persistenz); `is_within`-Nebeneffekt gewollt: Builder kann
  anderen Agenten Memory bis `suggest` freischalten, `auto` bleibt
  Menschen-Entscheidung.
- **Verworfen:** `auto` (widerspricht dem eigenen Kurationsprinzip);
  UI-Freischaltung pro Workspace (Managed-Lock + nicht zentral verteilbar).

## 2026-07-19 — Injection-Wächter: „System-Prompt" allein blockt nicht mehr
- **Entscheidung:** Erster echter Feldbefund des Memory-Features: das
  standalone `system.?prompt`-Muster blockte legitime Domänen-Fakten
  („System-Prompt-Templates" ist Who2Be-Alltagsvokabular). Muster verengt:
  nur noch Manipulations-Verb + System-Prompt (verrate/zeige/gib/leak/...)
  bzw. ignoriere/missachte + Regelwerk-Objekt (inkl. System-Prompt).
  Regressions- und Angriffs-Tests ergänzt.
- **Begründung:** Der Filter ist Vorfilter, nicht Richter (ADR-0044) — den
  Graubereich entscheidet die Triage; False Positives untergraben die
  Nutzung des Features schneller als seltene False Negatives, die die
  Freigabe-Schleuse ohnehin abfängt.

## 2026-07-19 — Injection-Wächter konfigurierbar (Stufe B, kein Regex)
- **Entscheidung:** Workspace-Setting `memory_guard` (standard/custom/off +
  literale Allow-/Block-Phrasen). Allow-Suppression nur bei vollständiger
  Treffer-Abdeckung (Bypass-fest); off gilt auf User-Wunsch auch für
  auto-Agenten (UI-Warnung); Verwaltung admin- UND human-only. Details:
  ADR-0044-Addendum 2, Plan 2026-07-19-1030.
- **Verworfen:** Stufe C (freie Regex — ReDoS/Fehlkonfigurations-Risiko,
  Validierungs-Sandbox unverhältnismäßig); Nur-An/Aus (löst False Positives
  nicht ohne Totalverzicht).

## 2026-07-20 — Standards-Pflege-Lauf: Konsolidierung + zwei Leitplanken
- **Konsolidierung (append-only-konform):** Die Einträge 2026-07-18/-19
  (Externe Tools; Agent-Memory Runden 1–3, Placeholder `memory`,
  Builder-Gedächtnis, Injection-Wächter) leben jetzt kanonisch in ADR-0043
  (`docs/adr/0043-external-tool-bindings.md`) und ADR-0044
  (`docs/adr/0044-agent-memory.md` inkl. Addenda) — die ADRs sind die
  maßgebliche Quelle. Die Alt-Einträge hier bleiben unverändert stehen
  (append-only, Historie); die Kürzung dieser Datei aufs Budget (MEM-5,
  `docs/standards-review-2026-07-20.md` §2.12) ist dokumentierter Follow-up.
- **LIC-1 — Billing-Override gehärtet (heute entschieden):** Der Admin-
  `manual_override`-Endpoint verlangt jetzt `require_aal2` UND eine
  Betreiber-Allowlist `WHO2BE_BILLING_OVERRIDE_OPERATORS` — **fail-closed**
  (leere/fehlende Liste ⇒ niemand darf overriden). Die Mechanik-Wahl
  (env-Allowlist als Operator-Identität) ist im PR-Review zu bestätigen
  (Owner-Punkt, Bericht §4).
- **ARC-3 — Interims-Leitplanke bis zur ADR-0002-Entscheidung (enforce vs.
  amend):** keine NEUEN `HTTPException`-/SQL-Vorkommen in
  `apps/api/**/services/` — Fehler als Domain-Exception, SQL übers
  Repository. Bestand bleibt bis zur Owner-Entscheidung unangetastet;
  Leitplanke ist auch in `CLAUDE.md` §Code-Style verankert.

## 2026-07-21 — Builder erhält `external_tool_write` (Content-Stand 11)
- **Entscheidung:** Die kanonische Builder-Policy trägt `external_tool_write`
  (ADR-0043): External-Tool-Bindungen anlegen/pflegen ist Verwaltungs-Arbeit
  des Meta-Agenten; via `is_within` kann er das Recht damit auch gezielt an
  Fach-Agenten vergeben. Verteilung über den Start-Sync (keine
  Spiegel-Migration, Konvention seit 0057). Dazu: sechstes Builder-Playbook
  „External Tool anlegen & pflegen" + External-Tools-Sektion in den
  Agent-Bau-Konventionen; der Playbook-Insert-missing-Zweig des Syncs setzt
  jetzt auch den `playbook_resource_link` auf die Konventions-Resource
  (Lücke: bei vorhandener Resource lief der Link-Zweig nie).
- **Verworfen:** MCP-Tools für Memory-Triage/-Guard (bewusst UI-only — die
  Pending-Schleuse ist die Human-in-the-loop-Grenze, ADR-0044);
  `memory_mode='auto'` für den Builder (Kurator-Prinzip).

## 2026-07-24 — Ein Element, eine Sprache (ADR-0045, ersetzt UI-Teil von ADR-0027)
- **Entscheidung:** Sprache wird vertieft statt entfernt: `locale` wandert auf
  die Identitäts-Zeile (Migration 0069), Reads werden locale-agnostisch,
  `?locale=` ist nur noch Listenfilter, Workspace-`content_locale` steuert
  Default + Rollout-Sprache (Packs in `builder_content.py`, EN-Sidecars unter
  `repositories/en/`), der Renderer injiziert die Output-Sprachanweisung
  automatisch, MCP-Writes taggen die Sprache. `UNIQUE(entity_id, locale,
  version)` bleibt bewusst bestehen (Legacy-Multi-Track), dafür `next_version`
  global + Read-Tie-Break auf die Entity-Sprache.
- **Verworfen:** Default-Track-Trick (alles bleibt 'de', Sprache wählt nur
  Seed-Bodies — Sprache wäre nicht echt im Datenmodell); Multi-Track-UI
  sichtbar machen (genau die per-Element-Mehrsprachigkeit, die nicht gewollt
  ist); Komplett-Entfernung des Sprach-Features (ursprünglicher Anstoß, vom
  User revidiert).

## 2026-07-25 — Semantische Suche & Passage-Retrieval (ADR-0046, Welle 1)
- **Entscheidung:** Chunk-basiertes Retrieval als Fundament, Vektor-Semantik
  additiv darauf (ADR-0046). Löst die als „Stufe B" offen gelassenen
  Folge-Verweise aus ADR-0037 (§35-38) **und** ADR-0044 (§70-71) gemeinsam ein.
  Neue Tabelle `content_chunk` (Migration 0070) hält die aktive Version in
  Passagen, geschnitten an den Heading-Blöcken — `block_id` ist damit exakt der
  bestehende Anker aus ADR-0021, es entsteht keine zweite Ankersprache. Das
  **ersetzt** die in ADR-0037 §53-54 zugesagten, nie angelegten
  Per-Tabelle-`tsvector`-Spalten: eine Textebene statt vier, und sie trägt
  später den Vektor.
- **FTS-Config pro Sprache** (Abweichung von 0066): seit ADR-0045 ist jedes
  Element einsprachig, also stemmt `'german'`/`'english'` sinnvoll. Belegt:
  „Reklamationen" → Stamm `reklamation`, Singular-Query trifft; mit `'simple'`
  unmöglich. Memory bleibt bewusst bei `'simple'` (pro Zeile gemischtsprachig).
- **Zwei Tools, keine Zusammenlegung:** `search` beantwortet „welches ELEMENT",
  `search_content` „welche STELLE". Kuratierte Inhalte und (später) Memory
  bleiben getrennte Verträge — unterschiedliche Vertrauensgrade, die Provenienz
  eines Treffers muss für das Modell ablesbar bleiben.
- **Zwei Fehler in der bestehenden Suche behoben** (beide durch neue Tests
  reproduziert, 6 rot gegen den Altstand): der Read-Scope wurde hinter dem
  `LIMIT` nachgefiltert statt als Prädikat in die Query zu gehen (ADR-0037 §47
  forderte „vor dem Ranking") — ein `assigned`-Agent bekam `[]`, sobald seine
  Treffer hinter den globalen Top-k lagen. Und die Scope-Mengen wurden für ALLE
  Typen geholt, auch für schon ausgeschlossene: ein Agent mit
  `playbook_read=none` bekam auf eine reine Persona-Suche ein 403 statt seiner
  Treffer. Das Scoping liegt jetzt als Single-Source in
  `agent_scope.readable_content_scope`.
- **Verworfen:** Memory in `content_chunk` mitführen (abgeleitet+regenerierbar
  vs. laufzeit-geschrieben+kuratiert — verschiedene Lebenszyklen); externer
  Embedding-Provider (bricht das On-Prem-„kein Phone-Home"-Versprechen, bei
  persönlichen Memories nicht verhandelbar); ANN-Index in v1 (beide Korpora zu
  klein, Brute-Force ist schneller als der Indexaufbau sich rentiert);
  Backfill als SQL-Migration (der Schnitt lebt in Python, eine Migration müsste
  ihn duplizieren) — stattdessen CLI `who2be-chunk-backfill`.
- **Offen (Welle 2/3):** pgvector-Infrastruktur, `EmbeddingPort` als optionale
  Dep-Gruppe, Hybrid-Ranking, Memory-Semantik. Die beiden Lücken sind als
  ausführbare Tests festgehalten (`test_memory_retrieval_baseline.py`:
  Paraphrase → Trigram-Similarity 0.14, cross-lingual → 0.03, beide unter der
  Schwelle 0.3) — Welle 3 muss diese Tests umdrehen.

## 2026-07-25 — ADR-0046 Welle 2: Vektor-Semantik additiv
- **Entscheidung:** `content_vector vector(384)` auf `content_chunk` (Migration
  0071) plus Hybrid-Ranking per Reciprocal Rank Fusion (K=60) und ein
  `mode`-Parameter (`auto|text|semantic|hybrid`) — der in ADR-0037 §35-38
  zugesagte Schalter. `auto` nimmt Semantik, wenn sie da ist, sonst Volltext;
  der Tool-Vertrag ändert sich dadurch nicht.
- **`EmbeddingPort`** als hexagonaler Port (Vorbild `build_entitlement_port`),
  lokaler `fastembed`-Adapter mit `paraphrase-multilingual-MiniLM-L12-v2`
  (384 dim, Apache-2.0, ~0,22 GB) in der optionalen Dep-Gruppe `embeddings`.
  Der Kern importiert `fastembed` nie statisch. Gerechnet wird lokal — kein
  Text verlässt das Deployment (On-Prem-Versprechen).
- **Migration 0071 ist fail-soft** — die wichtigste Korrektur gegenüber dem
  ursprünglichen Plan: `CREATE EXTENSION vector` scheitert hart auf einem
  Postgres ohne pgvector, also genau auf einer selbst gehosteten On-Prem-
  Instanz. Für ein rein additives Feature darf das die Migrationskette nicht
  abbrechen. Fehlt die Extension, entsteht die Spalte nicht;
  `content_chunk_repository.vector_supported` prüft ihre Existenz einmal pro
  Prozess, und alle Pfade bleiben dann lexikalisch.
- **Ähnlichkeitsschranke** `_MIN_VECTOR_SIMILARITY` (Cosinus 0.40) statt reinem
  Top-k: ohne Schwelle liefert eine Vektor-Suche IMMER k Treffer, auch zu einer
  völlig unpassenden Frage — das widerspräche der Tool-Anweisung „findest du
  nichts, sag das offen".
- **Verworfen:** asyncpg-Codec-freier Ansatz mit `::vector`-Casts im SQL (hängt
  am `search_path` und bricht bei Supabase, wo die Extension in `extensions`
  liegt) — stattdessen ein Codec mit dynamischer Schema-Auflösung in
  `core/db.init_connection`. Ebenfalls verworfen: einen ungenutzten
  Query-Parameter mitzubinden (Postgres kann seinen Typ dann nicht ableiten) —
  die Platzhalter werden jetzt dynamisch nummeriert.
- **Offen:** `_MIN_VECTOR_SIMILARITY` ist gegen das reale Modell **nicht
  kalibriert**. Der Modell-Download (huggingface.co) ist in der Entwicklungs-
  umgebung per Netz-Policy gesperrt; die Retrieval-Mechanik ist deshalb gegen
  deterministische Test-Vektoren mit bekannter Geometrie belegt, die
  Modell-Qualität nicht.

## 2026-07-25 — ADR-0046 Welle 3: Memory-Semantik
- **Entscheidung:** `content_vector vector(384)` auf `agent_memory`
  (Migration 0072, fail-soft wie 0071), und `search_active` von der
  lexikografischen `ORDER BY`-Kaskade auf **RRF-Fusion über vier Zweige**
  (FTS, ILIKE, Trigram, Vektor) umgebaut, `importance` als Tiebreak. Die
  Kaskade ließ den ersten Term dominieren — ein perfekter Vektor-Treffer wäre
  hinter jedem beliebigen FTS-Treffer gelandet.
- **Kein Chunking, kein ANN-Index:** `fact` ist auf 300 Zeichen begrenzt (ein
  Vektor pro Zeile), und `MEMORY_MAX_PER_AGENT` = 500 deckelt hart. Ein
  sequentieller Scan über höchstens 500 vorgefilterte Zeilen schlägt jeden
  ANN-Index — und wäre exakt statt approximativ.
- **Zwei Schwellen mit unterschiedlicher Logik:** Suche `0.45`, Dedup `0.92`.
  Die Asymmetrie folgt den Fehlerkosten — ein falsch positiver Dedup verwirft
  einen gültigen Fakt dauerhaft (409), ein falsch negativer kostet nur einen
  von 500 Listenplätzen.
- **Best-effort im Laufzeit-Pfad:** `save_memory` ist ein rate-limitierter
  Agenten-Call, kein Builder-Vorgang. Ein langsames oder kaputtes Modell darf
  ihn nie scheitern lassen; ohne Vektor greift weiterhin der Trigram-Dedup, und
  `who2be-retrieval-backfill` holt nach.
- **Der MCP-Docstring ist eingelöst.** Er versprach dem Modell seit ADR-0044
  „durchsucht dein Langzeitgedächtnis … semantisch", implementiert waren
  FTS + ILIKE + Trigram. Jetzt stimmt es — und der Docstring sagt zusätzlich,
  was ohne aktivierte Semantik gilt.
- **Verworfen:** `ilike` als CTE-Name (reserviertes Postgres-Keyword);
  ein zweiter Backfill-CLI für Memories — stattdessen deckt
  `who2be-retrieval-backfill` (umbenannt von `who2be-chunk-backfill`) beide
  Vektor-Korpora ab.
- **Offen bleibt** die Kalibrierung beider Schwellen gegen das reale Modell —
  huggingface.co ist per Netz-Policy gesperrt, die Retrieval-Mechanik ist gegen
  deterministische Test-Vektoren belegt, die Modell-Qualität nicht.

## 2026-07-26 — ADR-0046-Nachzug: Builder-Wissen (Content-Stand 14) + Seed-/Sync-Passagen
- **Befund:** Ein frisch angelegter Workspace hatte **null** `content_chunk`-
  Zeilen (verifiziert: 6 aktive Playbooks, 0 Passagen). Chunks entstehen nur in
  `version_status._transition`; Seed und Start-Sync schreiben aktive Versionen
  per direktem Insert/Update daran vorbei. `search_content` fand dort also
  ausgerechnet den ausgerollten Builder-Bestand nicht.
- **Entscheidung:** Beide Pfade stoßen den Chunk-Lauf selbst an —
  `_publish_seeded_chunks` (gescopet über `workspace_id`, best-effort im
  eigenen Savepoint) im Seed, ein globaler `backfill_chunks` im Startpfad
  **nur nach einem `BUILDER_CONTENT_VERSION`-Bump**. `backfill_chunks` bekommt
  dafür einen optionalen `workspace_id`-Filter statt einer zweiten SQL-Kopie.
- **Text-Ebene ja, Vektoren nein:** ein Embedding-Lauf gehört weder in die
  Workspace-Anlage noch in den Startpfad (Modell-Ladezeit im Request-/Boot-
  Pfad); `who2be-retrieval-backfill` bleibt der Ort dafür.
- **Content-Stand 14 (DE + EN):** neuer Abschnitt „Auffindbarkeit & Retrieval"
  in den Agent-Bau-Konventionen (Überschriften sind Schnittkanten, nur aktive
  Versionen sind auffindbar, Passage vor Volltext, `mode`-Wahl, Sprachgrenze,
  Retrieval ersetzt keine Trigger) + semantisches Gedächtnis in der
  Memory-Sektion; `search_content` im Beziehungs-Denken der Persona und in den
  Tool-/Wiederverwendungs-Stellen von Playbook- und Pflege-Playbook.
- **Begründung:** Sichtbarkeit (`tool_requirements` + `tools-overview`) macht
  ein Tool aufrufbar, nicht anwendbar. Die Chunk-Grenzen hängen an der
  Überschriftenstruktur — das ist eine **Autoren**-Regel, und der Builder ist
  der Autor.
- **Verworfen:** die Regeln in die Persona schreiben (die Persona trägt die
  Rolle, nicht das Handwerk — die Konventionen sind die Single-Source, die
  Persona verweist nur); Chunk-Rebuild bei jedem App-Start (unnötige Last ohne
  Content-Änderung).

## 2026-08-13 — Agent WorkArea + Knowledge Base — MVP-Zuschnitt
- **Entscheidung (7 User-Entscheidungen, bindend):**
  1. **Scope:** Phase 1 (A–E) und Phase 2 (F–G, K–N, O) gleich detailliert in
     einem Plan.
  2. **Verortung:** bestehender Stack — apps/api + apps/mcp + packages/models,
     Workspace-Tenancy, dieselbe Postgres-DB.
  3. **Blob-Storage:** MinIO/S3-kompatibel, content-addressed (SHA-256),
     neuer Compose-Dienst.
  4. **Kontodaten:** Ausgaben-Analyst läuft gegen Cloud-API — mit
     Lauf-Protokoll; Konto-Ingest bleibt in Phase 2.
  5. **Private Areas:** Menschen ab Rolle `editor` lesen alles (auch private
     Agent-Areas); „privat" heißt privat gegenüber anderen **Agenten**.
     Viewer sehen nur shared Areas.
  6. **Lauf-Protokoll:** Auto-Zugriffslog + Modell-Config am Agenten — der
     Server loggt jeden Agent-Zugriff automatisch (append-only, dedupliziert
     pro Element+Tag); `model_provider`/`model_name` sind betreiber-gepflegte,
     auditierte Felder am Agenten. Kein `record_run`-Selbstauskunfts-Tool.
  7. **Auswertung:** Kein serverseitiges Chart-Rendering — stattdessen
     `query_table` mit Format-Wahl + `save_query_result` (Server persistiert
     Query + eingefrorenes Ergebnis als doc-Artifact; Zahlen schreibt der
     Server, nie das Modell).
- **Begründung:** WorkArea/KB sind Kontext-Speicher für Agenten (kein
  CMS/Wiki, kein Runtime-Host); das Resource-Aggregat bleibt unangetastet,
  `promote_artifact` ist die einzige Brücke.
- **Detail:** ADR-0047 (Umbrella), ADR-0048 (Blob-Storage), ADR-0049
  (Tabellen-Store); Plan
  `.claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md`.

## 2026-08-16 — Security-Review Phase 2 (Tabellen-Store, Zugriffslog, Promote)
- **Entscheidung:**
  1. **Freies Agenten-SQL bekommt Ressourcen-Grenzen, nicht nur ein
     Schreibverbot:** Zeitbudget je Query (`set_progress_handler`,
     `WHO2BE_TABLESTORE_QUERY_TIMEOUT_MS`, Default 5000 ms), Zell-Cap
     (`SQLITE_LIMIT_LENGTH` 1 MB) und Result-Byte-Budget (2 MB). `describe`
     teilt alle drei (dieselbe ro-Connection).
  2. **Authorizer prüft Funktions-NAMEN** statt `SQLITE_FUNCTION` pauschal zu
     erlauben — `fts3_tokenizer` (roher Pointer-Zugriff, verifiziert) war
     sonst erreichbar. Allowlist empirisch gegen sqlite 3.45.1 verifiziert;
     `cast` gehört nicht hinein (Opcode), Window-Funktionen schon.
  3. **Timeout ohne neuen `ProblemReason`:** 408 über den generischen
     Domain-Exception-Weg. Die Taxonomie beschreibt Berechtigungs-/
     Zustandsgründe; Kosten sind keiner davon, und kein Agent muss darauf
     verzweigen. Größen-Grenzen dagegen nutzen das bestehende
     `ingest_too_large` (413).
  4. **Compliance-Attribution ist menschlich:** `model_provider`/`model_name`
     sind für agent-gebundene Tokens gesperrt (403), das Zugriffslog
     snapshottet sie zum Zugriffszeitpunkt (Migration 0080). Das Agent-UPDATE
     bleibt sonst agent-fähig — es ganz zu sperren bräche den Builder-Pfad.
  5. **Append-only gilt auch gegen FK-Cascade:** `agent_access_log.agent_id`
     auf `ON DELETE NO ACTION`. Konsequenz (gewollt): Agenten mit
     protokollierten Zugriffen sind nicht löschbar (409); Purge und
     Test-Teardown räumen als Owner explizit vor der Org-CASCADE auf.
  6. **M1 war bereits geschlossen:** ein aktiver ungebundener Token ist seit
     Migration 0048 per CHECK unmöglich. Das neue Router-Gate
     (`require_agent_bound_token`) ist Defense-in-Depth für den Fall, dass
     ein Kontext ohne Agent-Bindung anders entsteht.
- **Begründung:** Read-only ist eine Aussage über Wirkung, nicht über Kosten;
  und ein Compliance-Journal, das der Protokollierte selbst löschen oder
  umschreiben kann, ist keines.
- **Detail:** ADR-0047 §Nachtrag 2026-08-16; Migration 0080;
  `apps/api/tests/test_security_fixes_phase2.py`.

## 2026-08-16 — Umsetzungs-Entscheidungen WorkArea/KB (Wellen 1–7, nicht im Plan)
- **Entscheidung:**
  1. **SQLite-Funktions-Allowlist statt pauschalem `SQLITE_FUNCTION`:** der
     Authorizer entscheidet über den Funktions-NAMEN (`arg2`), nicht über den
     Opcode. Ein pauschales OK hätte jede eingebaute Funktion freigegeben —
     inklusive `fts3_tokenizer` (roher C-Pointer, les- UND schreibbar) und
     `randomblob`/`zeroblob` als Speicher-DoS. Die Liste ist empirisch gegen
     sqlite 3.45.1 verifiziert: `cast` ist ein Opcode und gehört nicht hinein,
     Window-Funktionen laufen sehr wohl als `SQLITE_FUNCTION` und müssen
     gelistet sein. JSON-Funktionen bleiben draußen — Zellen tragen laut
     ADR-0049 kein JSON, also gibt es keinen Bedarf, der die zusätzliche
     Parser-Angriffsfläche rechtfertigt.
  2. **Menschen-Vorbehalt auf der Modell-Konfiguration:** `model_provider`/
     `model_name` am Agenten dürfen agent-gebundene Tokens nicht setzen (403).
     Sonst schriebe sich der Protokollierte seinen eigenen
     Compliance-Nachweis. Gleiches Prinzip bei Area-Grants: Rechtevergabe ist
     Menschen-Sache, kein Agent erweitert seinen eigenen Zugriff.
  3. **Zugriffslog als Snapshot, nicht als Join:** `sensitivity_at_access` und
     die Modell-Angaben werden zum Zugriffszeitpunkt in die Log-Zeile kopiert
     statt später über den aktuellen Stand gejoint. Eine spätere Umstufung
     eines Artifacts (general → sensitive) darf die Vergangenheit nicht
     umschreiben; die Frage lautet „was galt damals", nicht „was gilt heute".
  4. **Agent-gebundene Tokens auf allen WorkArea-Routen:**
     `require_agent_bound_token` als Router-Gate. WorkArea/KB sind
     Agenten-Werkzeuge — ohne Agent-Identität gibt es weder eine private Area
     noch eine sinnvolle Protokollzeile. Defense-in-Depth: der aktive
     ungebundene Token ist seit Migration 0048 ohnehin per CHECK unmöglich.
  5. **Kein Chart-Rendering, auch nicht als „kleines Extra":** Auswertung
     endet beim Result Set (`query_table` + `save_query_result`, Server friert
     Query + Ergebnis als doc-Artifact ein). Ein Renderer wäre der erste
     Schritt zum BI-Werkzeug und damit Scope-Drift gegen die Non-Goals.
     Zahlen schreibt der Server aus dem Result Set, nie das Modell.
  6. **Retention-Sweeps im bestehenden Purge-Cron statt als eigener Job:** ein
     Org-/Account-Hard-Purge hinterlässt genau die Blob-Zeilen und
     Area-Dateien, die die Sweeps abräumen — nacheinander im selben Lauf
     erledigt das eine Runde statt zweier. Die Sweeps laufen bewusst NICHT in
     einer gemeinsamen Transaktion: jeder ist für sich idempotent, und ein
     nicht erreichbarer Objekt-Storage darf den Artifact-Sweep nicht
     zurückrollen.
  7. **Blob-Orphan-Sweep braucht ein Objekt-Alter, sonst löscht er nichts:**
     der Ingest schreibt das Objekt VOR der Postgres-Transaktion — zwischen
     PUT und COMMIT existiert ein Objekt ohne Katalog-Zeile völlig regulär.
     Ohne Zeitstempel ist dieser Zustand von Müll nicht unterscheidbar.
     Deshalb die optionale Port-Fähigkeit `BlobAgeSource` (`last_modified`,
     MinIO liefert es aus `stat_object`); ein Store ohne Zeitquelle wird
     gemeldet, nicht aufgeräumt. Blind zu löschen wäre Datenverlust.
  8. **Der Datei-Sweep fasst unbekannte Verzeichnisse NICHT an:** gelöscht
     wird nur unter einem Workspace-Verzeichnis, dessen Workspace existiert.
     Grund ist der teuerste Fehlfall: liefe der Purge gegen die falsche (z. B.
     frisch migrierte, leere) Datenbank, sähe jedes Verzeichnis wie ein
     gelöschter Workspace aus. Bewusste Kehrseite: nach einem Workspace-
     Hard-Purge bleiben die Dateien liegen und werden nur gemeldet
     (`unknown_store_dirs`) — die Nachbereinigung ist ein dokumentierter
     Betreiber-Schritt (RUNBOOK + Löschkonzept §4a).
  9. **GDPR-Export trägt Blob-METADATEN, keine Bytes:** base64-kodierte PDFs
     hätten das Bündel je nach Workspace auf hunderte MB gebracht und im
     Fehlerfall unauslieferbar gemacht. Der `storage_key` adressiert die
     Objekte eindeutig; der Betreiber leitet sie über den dokumentierten
     Bucket-Pfad aus. Tabellen-Zeilen kommen dagegen mit — gedeckelt auf
     10 000 je Tabelle mit `truncated`-Flag, gelesen über denselben read-only
     Pfad wie Agenten-SQL (der Export bekommt keine Sonderrechte).
- **Begründung:** Die Punkte fielen während der Umsetzung, nicht bei der
  Planung — sie betreffen durchweg die Grenze zwischen „technisch möglich" und
  „verantwortbar": wer darf Compliance-Daten schreiben, was darf ein
  Aufräum-Job löschen, und wo hört Auswertung auf.
- **Detail:** ADR-0047/0048/0049; `core/purge.py`,
  `services/gdpr_export_service.py`, `blobstore/port.py`;
  `apps/api/tests/test_workarea_retention.py`;
  `docs/compliance/data-retention-and-erasure.md` §4a.

## 2026-08-16 — Dated Befund-Dokumente werden nie rückwirkend umgeschrieben
- **Entscheidung:** Berichte, die einen Zustand zu einem Datum festhalten
  (`docs/standards-review-*.md`, archivierte `.claude/plan/*.md`), bleiben
  unangetastet, auch wenn ein Befund später erledigt ist. Die **Auflösung**
  wird in `.claude/context/STATE.md` verzeichnet — dort, wo der Ist-Zustand
  lebt. Nur *lebende* Dokumente (STATE.md, CLAUDE.md, ROADMAP.md,
  `.claude/plan/README.md`, PR-Template) werden nachgezogen.
- **Anlass:** Das CI-Gate war seit 2026-07-19 durch Actions-Billing tot
  (GIT-2 im Standards-Review 2026-07-20) und läuft seit 2026-08-16 wieder.
  Die Aussage stand an neun Stellen im Repo.
- **Begründung:** Ein Review-Bericht, aus dem Befunde nachträglich
  verschwinden, ist als Beleg wertlos — man kann ihm dann nicht mehr ansehen,
  ob ein Punkt nie gefunden oder still entfernt wurde. Umgekehrt darf eine
  überholte Aussage nicht in Dateien stehen bleiben, die jede Session geladen
  werden (CLAUDE.md): dort würde sie weiterhin Verhalten steuern — konkret:
  lokale Läufe als *Ersatz* für ein Gate rechtfertigen, das wieder greift.
- **Verworfen:** die Befunde im Review-Dokument auf ✅ setzen (fälscht den
  Bericht); nur STATE.md pflegen (die stale Aussage bliebe im
  Session-Kontext wirksam).
- **Detail:** STATE.md §Standards / CI trägt die Belegkette (Runner-IDs statt
  `runner_id: 0`, echte Laufzeiten, der im ersten Lauf gefundene Lint-Fehler).

## 2026-08-16 — jsonb binden: dict an den Pool, `::text::jsonb` bei offenem Executor
- **Entscheidung:** Ein `jsonb`-Bind-Parameter bekommt auf einer Connection MIT
  Pool-Codec (`core/db.init_connection`) das **dict** — nie einen bereits
  serialisierten String. Wo der Executor offen ist (der Aufrufer übergibt Pool
  ODER eine beliebige Connection, z. B. `audit_log_repository.insert`), wird
  `$n::text::jsonb` genutzt: der Parameter ist dann `text`, der Codec greift
  gar nicht erst, und die Form ist auf beiden Connection-Arten korrekt.
  Der Start-Sync (`workspace_repository`) bleibt bei String + `$n::jsonb` —
  er läuft auf einer Owner-Connection ohne Codec; das steht dort begründet und
  in der Allowlist des Drift-Tests.
- **Anlass:** `describe_table` antwortete im Betrieb mit 500. `$4::jsonb` +
  `json.dumps(...)` hatte die Quell-Konvention doppelt encodiert; von den zwei
  Mappern derselben Zeile starb der strenge (siehe STATE.md).
- **Begründung:** Die falsche Form wirft keinen Fehler — sie legt still einen
  JSON-*String* in die Spalte. Gemessen (asyncpg 0.30 / PG 16, festgehalten in
  `apps/api/tests/test_jsonb_bindings.py`): `::jsonb`+dict → `object`,
  `::jsonb`+String → `string`, `::text::jsonb`+String → `object` (mit und ohne
  Codec).
- **Nebenentscheidung:** Eine Zeilenform hat genau **einen** Mapper. Die zweite
  Kopie in `wa_table_repository` ist entfallen; parallel gepflegte Mapper
  driften auseinander, und der tolerantere verdeckt dabei den Fehler, den der
  strengere in einen 500 verwandelt.
- **Verworfen:** überall tolerant lesen (versteckt die Ursache, das Datum
  bleibt falsch); den Codec abschaffen (der Bestand bindet an vielen Stellen
  dicts); `audit_log`-Altzeilen mitmigrieren (ein Audit-Trail wird nicht
  rückwirkend umgeschrieben).
- **Detail:** Migration `0081_jsonb_double_encoded.sql`;
  `apps/api/tests/test_jsonb_bindings.py` (Semantik + Drift-Guard);
  `test_wa_rules.py` (gespeicherter Zustand + Migrationstest),
  `test_wa_tables.py::test_describe_liefert_gesetzte_konventionen`.

## 2026-08-16 — Ein Anker, zwei Auflösungen: Passage oder Block
- **Entscheidung:** `read_artifact(anchor)` liefert die ganze **Passage**, wenn
  der Anker eine Passage eröffnet (Heading-Block bzw. der erste Block vor dem
  ersten Heading) — und weiterhin genau **einen Block** bei jedem anderen
  Anker. Die Passagen-Grenzen kommen aus genau einer Funktion
  (`wa_chunks.split_sections`), die Index und Lesepfad gemeinsam nutzen.
- **Anlass:** Befund A aus dem Builder-Test. Der Treffer-Anker der Suche ist per
  Konstruktion der Heading-Block; der Read gab darauf nur diesen Block zurück,
  also die Überschrift ohne Inhalt. Der dokumentierte Weg
  `search_workarea` → `read_artifact(anchor)` endete im Nichts.
- **Begründung:** Die beiden Nutzungen des Ankers sind verschieden: nach einer
  Suche will man die Fundstelle *lesen*, vor einem `patch_artifact` will man
  die Stelle *sehen*, die man ändert. Beides an einem Parameter zu bedienen
  geht, weil die Anker-Herkunft die Absicht schon trägt — der Suchindex vergibt
  ausschließlich Passagen-Anker. Was geliefert wurde, ist an den `[#…]`-Ankern
  der Antwort ablesbar; es braucht kein zusätzliches Feld.
- **Verworfen:** ein zweiter Parameter (`scope=block|passage`) — er verlagert
  eine Entscheidung auf den Agenten, die die Anker-Herkunft bereits beantwortet;
  *immer* die umgebende Passage liefern — das nähme dem Patch-Pfad den genauen
  Blick; den Suchtreffer auf den ersten Textblock ankern lassen — dann verlöre
  der Treffer seine Überschrift, und `heading_path` im Index würde inkonsistent.
- **Test-Lehre:** Der bestehende End-to-End-Test war grün, weil sein Dokument
  aus EINEM Absatz ohne Überschrift besteht — der einzigen Form, in der „ein
  Block" und „die Passage" dasselbe sind. Ein Beispiel-Dokument, das die
  Fallunterscheidung des Codes nicht enthält, prüft sie auch nicht.
- **Detail:** `services/wa_chunks.split_sections`/`passage_for_anchor`,
  `services/wa_artifacts.read`; `test_wa_blocks.py` (pure Fälle),
  `test_wa_search.py::test_treffer_anker_liefert_die_passage_nicht_nur_die_ueberschrift`.

## 2026-08-17 — KB-Suche wird sprachbewusst (revidiert 0077)
- **Entscheidung:** `kb_node` bekommt eine `locale`-Spalte (Migration 0082,
  Backfill aus `workspace.content_locale`), und die generierte `search`-Spalte
  bildet wie `wa_chunk`/`content_chunk` auf `german`/`english` ab —
  Fallback `simple` bei unbekannter Sprache. Die Sprache ist
  **server-abgeleitet** (`resolve_content_locale`); `KbNodeCreate` bekommt
  kein `locale`-Feld.
- **Anlass:** Befund B. `'simple'` kennt kein Stemming, also war eine Aussage
  über den „Fehlercode" für eine Suche nach „Fehlercodes" unsichtbar —
  während `search_workarea` denselben Text fand.
- **Begründung:** 0077 begründete `'simple'` mit „kurz und ggf.
  gemischtsprachig". Der Preis dieser Annahme war nie beziffert: die KB ist
  für den Agenten der kuratierte Wissensspeicher, und ein stiller Nicht-Treffer
  ist dort teurer als ein gelegentlich unpassend gestemmtes Wort. Die Sprache
  muss auch nicht geraten werden — der Workspace trägt sie seit 0069.
- **Nebenentscheidung:** Die Abbildung Sprache → `regconfig` steht ab jetzt
  **einmal** (`repositories/fts_config.fts_config_expr`) statt als Kopie je
  Suchpfad. Sie muss zwingend mit dem Ausdruck der generierten Spalte
  übereinstimmen; läuft sie auseinander, findet die Query ihren eigenen Index
  nicht — lautlos, ohne Fehler. Eine Änderung der Abbildung verlangt deshalb
  immer eine Migration, die die betroffenen Spalten neu baut.
- **Verworfen:** `locale` als Agenten-Feld in `KbNodeCreate` (eine Entscheidung
  mehr, die falsch getroffen werden kann); Spracherkennung pro Aussage (rät,
  wo eine verlässliche Quelle existiert); zusätzlich auf
  `websearch_to_tsquery` umstellen (beträfe alle drei Suchpfade und gehört
  eigenständig gemessen).
- **Detail:** `0082_kb_node_locale.sql`; `repositories/fts_config.py`;
  `kb_repository.search_nodes`/`insert_node`; `services/kb.create_node`;
  `test_kb.py` (Wortformen, Sprach-Fallback, Migration gegen Altbestand).

## 2026-08-17 — MCP reicht `reason` und `actionable_by` an den Agenten durch
- **Entscheidung:** Jede Fehlerantwort der API wird im MCP-Client über EINE
  Stelle (`client.problem_message`) übersetzt, für **alle** Statuses. Das
  Format ist `"<detail> (reason=<reason>, actionable_by=<actionable_by>)"` —
  Prosa zuerst, Maschinen-Schlüssel als `key=value` hinten. Fehlt die Taxonomie
  (FastAPI-`HTTPException`, Validierungsfehler), bleibt die Meldung, wie sie
  ist; es wird kein `reason` erfunden.
- **Anlass:** Befund C. `reason` existiert seit WP-2 genau dafür, dass ein Agent
  „deterministisch verzweigen kann, ohne den `detail`-Freitext zu parsen"
  (`models/errors.py`) — und der MCP-Server hat es verworfen. Bei
  400/408/413/429/503 kam nicht einmal `detail` an: `Who2Be-API-Fehler (503).`
- **Begründung:** Das teuerste Missverständnis ist nicht ein Fehler, sondern
  ein Fehler ohne Handlungsanweisung. `actionable_by=human` sagt einem Agenten,
  dass jeder Retry Verschwendung ist; `reason=convention_missing` sagt ihm, was
  er selbst nachholen kann. Beides stand serverseitig bereit und kam nie an.
- **Verworfen:** strukturierte Fehler-Objekte statt Text (MCP `ToolError`
  transportiert eine Message — ein JSON-Blob wäre für das Modell schlechter
  lesbar); den Schlüssel voranstellen (die Prosa ist das, wonach das Modell
  handelt); eine globale Server-`instructions`-Sektion zur Fehler-Taxonomie
  (der Connector-Prompt ist knapp budgetiert, und `key=value` erklärt sich).
- **Detail:** `apps/mcp/src/who2be_mcp/client.py::problem_message`,
  `server.py` (Workspace-Lookup); `apps/mcp/tests/test_client.py`
  (Reason-Durchreichung je Status, Nicht-Erfindung ohne Taxonomie, Fallback
  ohne Body).
