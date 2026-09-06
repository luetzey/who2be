// TypeScript-Spiegel der Pydantic-Modelle aus packages/models. Handgepflegt —
// es gibt bewusst keinen Cross-Language-Typgenerator.

// Phase 2.1b — wird vom Backend pro Version gefuehrt. Bis 2.1b-A/B gemergt
// ist, fehlen die Felder in der Response; alle UI-Branches lesen sie optional.
export type VersionStatus = 'draft' | 'review' | 'active' | 'inactive'

// Strukturierter Profil-Inhalt (Phase 3-B). Spiegelt
// `PersonaContent` aus packages/models. Optional, weil Backend bis Phase
// 3-0 das Feld nicht garantiert liefert und alte Versionen es nicht
// haben.
export interface PersonaProfile {
  description: string
  blocks: ResourceBlock[]
}

// Track D/E (PR-A) — eine Persona kann auf Skills referenzieren. `SkillRef`
// ist ein schlanker {name, note}-Eintrag (kein Aggregat).
export interface SkillRef {
  name: string
  note: string
}

// Track C5 + PR-A — Persona-Modi. Spiegelt `PersonaMode` aus packages/models.
// `identity_add`/`output_style_override`/`anti_patterns` sind BlockNote-Dokumente
// (ResourceBlock[]), nicht mehr Plain-Strings. `playbook_id`/`playbook_name`
// verknuepfen einen Modus optional mit einem Playbook (denormalisierter Snapshot).
export interface PersonaMode {
  name: string
  trigger?: string | null
  is_default: boolean
  identity_add: ResourceBlock[]
  output_style_override: ResourceBlock[]
  anti_patterns: ResourceBlock[]
  playbook_id?: string | null
  playbook_name?: string
}

export interface PersonaContent {
  description: string
  system_prompt: string
  // `traits` ist mit Phase 3-0 deprecated — Backend liefert/akzeptiert
  // weiterhin ein leeres Array (Default). UI schreibt es nicht mehr.
  traits: string[]
  tags?: string[]
  content?: PersonaProfile | null
  // Track C5 — Modi (optional, Default []).
  modes?: PersonaMode[]
  // Track D/E (PR-A) — Skill-Referenzen (optional, Default []).
  skills?: SkillRef[]
}

export interface Persona {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  current_version: number
  current_status?: VersionStatus
  has_pending_draft?: boolean
  content: PersonaContent
  // Ein Element, eine Sprache (ADR-0045): Top-Level-Attribut statt der
  // frueheren Multi-Track-Sprachauswahl. Optional getragen, solange aeltere
  // Backend-Antworten (Rollout-Uebergang) das Feld noch nicht liefern.
  locale?: string
  created_at: string
  updated_at: string
  // Vom System verwaltet (z. B. der geseedete Builder). User-Mutationen sind
  // serverseitig gesperrt (403 managed_aggregate); die UI rendert read-only.
  is_managed?: boolean
  // List-Card-Pills: nur der List-Endpoint befuellt diese Batch-Aggregat-Zaehler.
  // Anzahl verknuepfter Playbooks bzw. Agenten, die diese Persona nutzen.
  playbook_count?: number
  agent_count?: number
}

export interface PersonaVersion {
  version: number
  status?: VersionStatus
  content: PersonaContent
  created_by: string
  created_at: string
}

export interface PersonaInput {
  name: string
  content: PersonaContent
  // Ein Element, eine Sprache (ADR-0045): einzelne Sprache statt der
  // frueheren Multi-Auswahl (`locales: string[]`). Fehlt das Feld, defaultet
  // das Backend auf die Workspace-Content-Sprache (`Workspace.content_locale`).
  locale?: string
}

// Kuratierte Playbook-Typen (Phase 3-0). Spiegelt `PlaybookType` aus
// packages/models. Backend bleibt schema-kompatibel zu `string`, daher
// liegt das Feld in `PlaybookContent.type` als `string` — die Union ist
// die UI-erwartete Closed-Set-Variante fuer den Select. UI-Selects
// (Phase 3-B) beziehen ihre Optionen daraus.
export type PlaybookType =
  | 'prompt'
  | 'instructions'
  | 'snippet'
  | 'workflow'
  | 'checklist'
  | 'faq'

export interface PlaybookContent {
  description: string
  // Track B (Nur-BlockNote): `body` ist immer JSON.stringify(editor.document)
  // mit Inline-Pills. Der frueher gefuehrte `body_format`-Schalter entfaellt.
  body: string
  type: string
  tags: string[]
  triggers: string | null
}

export interface Playbook {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  current_version: number
  current_status?: VersionStatus
  has_pending_draft?: boolean
  type: string
  tags: string[]
  triggers: string | null
  content: PlaybookContent
  // Ein Element, eine Sprache (ADR-0045). Siehe `Persona.locale`.
  locale?: string
  created_at: string
  updated_at: string
  // Track A8 — abgeleitet: hat Kinder in playbook_composition.
  is_composite?: boolean
  // Vom System verwaltet (Builder-Playbook) — User-Mutationen serverseitig
  // gesperrt (403 managed_aggregate); die UI rendert read-only.
  is_managed?: boolean
  // WP-D2 — Sub-Playbooks eines Composites (id + name, geordnet nach
  // Position). Vom Listen-Endpoint per Batch-Select befuellt; optional,
  // andere Read-Pfade liefern eine leere Liste.
  compose_children?: PlaybookRef[]
}

// Track A8 — Schlanke Referenz fuer Backlinks (Composed-by-Liste).
export interface PlaybookRef {
  id: string
  name: string
}

export interface PlaybookVersion {
  version: number
  status?: VersionStatus
  content: PlaybookContent
  created_by: string
  created_at: string
}

export interface PlaybookInput {
  name: string
  content: PlaybookContent
  // Ein Element, eine Sprache (ADR-0045). Siehe `PersonaInput.locale`.
  locale?: string
}

export interface Token {
  id: string
  workspace_id: string
  name: string
  // An welchen Agenten der Token gebunden ist (null = ungebunden). Ein
  // gebundener Token erbt die MCP-Tool-Policy dieses Agenten.
  agent_id: string | null
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
  // Ablaufzeitpunkt (ISO-8601, ADR-0039) oder null = kein Ablauf. Die UI bildet
  // daraus den „expired"-Bucket (expires_at in der Vergangenheit UND nicht
  // widerrufen). Optional, weil aeltere Backend-Versionen das Feld nicht liefern.
  expires_at?: string | null
}

// Rollen-Hierarchie laut ADR-0023: admin > editor > viewer. Single-Source
// fuer das Frontend (spiegelt `WorkspaceRole` aus packages/models).
export type WorkspaceRole = 'admin' | 'editor' | 'viewer'

export interface MeWorkspaceMembership {
  id: string
  name: string
  slug: string
  role: WorkspaceRole
}

export interface MeOrganization {
  id: string
  name: string
  slug: string
  kind: 'personal' | 'company'
  workspaces: MeWorkspaceMembership[]
}

export interface Me {
  user_id: string
  default_workspace_id: string | null
  organizations: MeOrganization[]
  // `has_password=false` markiert Magic-Link-User ohne gesetztes Passwort.
  // Invitation-Accept leitet die dann auf `/onboarding/set-password` um —
  // sonst landen sie in einer Login-Sackgasse (kein Credential vorhanden).
  // Optional, weil aeltere Backend-Versionen das Feld nicht liefern; Frontend
  // behandelt `undefined` als „Status unbekannt, nicht umleiten".
  has_password?: boolean
}

// Track C — Tenancy-Aggregate (Org/Workspace). Spiegeln `OrganizationRead`
// und `WorkspaceRead` aus packages/models. Genutzt von den Space-Settings-
// Pages (Workspace anlegen/umbenennen/löschen).
export interface Organization {
  id: string
  name: string
  slug: string
  kind: 'personal' | 'company'
  created_at: string
}

export interface Workspace {
  id: string
  org_id: string
  name: string
  slug: string
  created_at: string
  // Workspace-Content-Sprache (ADR-0045): Default fuer neu angelegte Elemente
  // (Persona/Playbook/Resource/Tool/System-Prompt) und Quelle fuer geseedete
  // Standard-Inhalte. Bei Anlage waehlbar (vorbelegt aus der UI-Sprache),
  // danach nur ueber das Backend aenderbar.
  content_locale: string
}

// Track O — Account-/Org-Lifecycle. `purge_after` ist der frueheste
// Hard-Purge-Zeitpunkt (now + 30-Tage-Grace).
export interface AccountDeletion {
  purge_after: string
}

export interface OrganizationDeletion {
  organization_id: string
  purge_after: string
}

// Track O — GDPR-Datenexport. Bewusst lose typisiert: das Buendel ist ein
// 1:1-Abzug der DB-Zeilen (Versionen + jsonb-Inhalte) und wird im Frontend nur
// als Datei heruntergeladen, nicht strukturiert gelesen.
export type GdprExport = Record<string, unknown>

export interface WorkspaceInput {
  name: string
  slug: string
  // Optional — fehlt das Feld, defaultet das Backend auf 'de'. Die
  // Anlage-Form (`OrgSettingsPage`) schickt es immer, vorbelegt aus `useLocale()`.
  content_locale?: string
}

export interface OrganizationInput {
  name: string
  slug: string
}

export interface WorkspaceRenameInput {
  name: string
}

export interface TokenCreated extends Token {
  token: string
}

export interface TokenInput {
  name: string
  // Phase 2.3 — optionaler Rollen-Snapshot. Bleibt weg, solange die Rolle
  // unbekannt ist (Service defaultet dann auf die Rolle des Erstellers).
  role?: WorkspaceRole
  // Pflicht-Bindung an einen Agenten (secure by default): der Token erbt dessen
  // MCP-Tool-Policy. Ungebundene Tokens sind nicht mehr erlaubt.
  agent_id: string
  // Optionaler Ablaufzeitpunkt (ISO-8601, ADR-0039); weggelassen = kein Ablauf.
  expires_at?: string
}

export interface TokenRenameInput {
  name: string
}

// Phase 2.3-C — Multi-User pro Workspace. Spiegelt WorkspaceMemberRead /
// InvitationRead aus packages/models. Endpoints folgen in Prompt A/B; bis
// dahin antwortet das Backend 404 — die Pages fangen das als Error/Empty ab.
export interface Member {
  user_id: string
  // `email` ist die menschenlesbare Identitaet in der Member-Tabelle. Backend
  // liefert sie via LEFT JOIN auf `auth.users`; fehlt das Schema (Test-DB) oder
  // der User keine Email, ist sie null/leer und die UI faellt auf user_id.
  email: string | null
  role: WorkspaceRole
  joined_at: string
}

export interface MemberUpdateInput {
  role: WorkspaceRole
}

export interface Invitation {
  id: string
  email: string
  role: WorkspaceRole
  expires_at: string
  created_at: string
  // Klartext-Token nur unmittelbar nach Erstellung (analog API-Token). Aus der
  // Liste liefert das Backend ihn bewusst nicht (Hash-only, ADR-0023).
  token?: string | null
}

export interface InvitationInput {
  email: string
  role: WorkspaceRole
}

export interface InvitationAcceptResult {
  workspace_id: string
}

// Dashboard-Endpoint (Phase 2.1b §2.1.E + Phase-3-Fix Track 1). Felder
// spiegeln das Backend-DTO aus `packages/models/.../dashboard.py`. `actor`
// und `entity_name` werden absichtlich als optional getragen: alte
// Response-Versionen (vor Track 1) lieferten sie nicht, und auch nach Fix
// soll der Frontend-Code defensiv lesen.
export type DashboardEntityType = 'persona' | 'playbook' | 'resource'

export interface DashboardKpis {
  active_personas: number
  active_playbooks: number
  active_resources?: number
  pending_reviews: number
  // Aufmerksamkeits-Signale (optional: aeltere Backends liefern sie nicht):
  // Gedaechtnis-Vorschlaege in der Freigabe-Schleuse (ADR-0044) und
  // System-Prompt-Templates, deren aktuelle Version zur Review liegt.
  pending_memories?: number
  pending_system_prompts?: number
}

export interface DashboardActor {
  user_id: string
  display_name?: string | null
}

export interface DashboardActivity {
  ts: string
  actor?: DashboardActor | null
  entity_type: DashboardEntityType
  entity_id: string
  entity_name?: string | null
  event: string
  from_version?: number | null
  to_version?: number | null
}

export type StatusDistribution = Record<VersionStatus, number>

export interface DashboardStatusDistribution {
  persona: StatusDistribution
  playbook: StatusDistribution
  resource?: StatusDistribution
}

// Seiten-Metadaten fuer den Activity-Feed (Track G). `activity` traegt nur
// die Eintraege der aktuellen Seite; `total_pages` steuert die Vor-/Zurueck-
// Buttons. Optional getragen, weil aeltere Backend-Versionen das Feld nicht
// liefern — der Konsument faellt dann auf "eine Seite" zurueck.
export interface ActivityPagination {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface DashboardData {
  kpis: DashboardKpis
  activity: DashboardActivity[]
  activity_pagination?: ActivityPagination
  status_distribution: DashboardStatusDistribution
}

// Phase 2.2 — Resources (Block-Editor) + Playbook→Block-Refs. `blocks` ist das
// offene BlockNote-Dokument; nur `id`/`type` sind verbindlich.
export interface ResourceBlock {
  id: string
  type: string
  [key: string]: unknown
}

export interface ResourceContent {
  description: string
  blocks: ResourceBlock[]
  // Track E3 — Tags (optional, Default []).
  tags?: string[]
}

// Kompakte Kind-Summary fuer die aufklappbare Resource-List-Karte. Spiegelt
// die vom List-Endpoint befuellten Felder von `SubResourceRead` (id/name +
// Status/Version der aktuellen Kind-Version). Optional getragen, weil andere
// Read-Pfade (get/MCP-fetch) das Feld nicht befuellen.
export interface SubResourceSummary {
  id: string
  name: string
  status?: VersionStatus
  version?: number
}

export interface Resource {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  // Workspace-eindeutiger Slug (Backend leitet ihn beim Anlegen aus dem Namen
  // ab). Vom Backend garantiert; im TS als Pflichtfeld gefuehrt.
  slug: string
  current_version: number
  current_status?: VersionStatus
  has_pending_draft?: boolean
  content: ResourceContent
  // Ein Element, eine Sprache (ADR-0045). Siehe `Persona.locale`.
  locale?: string
  created_at: string
  updated_at: string
  // Vom System verwaltet — User-Mutationen serverseitig gesperrt
  // (403 managed_aggregate); die UI rendert read-only.
  is_managed?: boolean
  // List-Card-Pills: nur der List-Endpoint befuellt diese Batch-Aggregat-Zaehler.
  // DISTINCT-Playbooks, die diese Resource referenzieren, bzw. Anzahl der
  // eingebetteten/verlinkten Sub-Resources.
  playbook_link_count?: number
  sub_resource_count?: number
  // List-Card: direkte Sub-Resource-Kinder (Summary), damit die Karte sie
  // aufklappen kann. Nur der List-Endpoint befuellt das Feld (Batch, kein N+1);
  // andere Read-Pfade lassen es leer/weg.
  sub_resources?: SubResourceSummary[]
}

export interface ResourceVersion {
  version: number
  status?: VersionStatus
  content: ResourceContent
  created_by: string
  created_at: string
}

export interface ResourceInput {
  name: string
  content: ResourceContent
  // Ein Element, eine Sprache (ADR-0045). Siehe `PersonaInput.locale`.
  locale?: string
}

// WP-4 (Blueprint `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`):
// externe MCP-Server/Tool-Bindings. Rein instruktiv — KEINE Server-URLs,
// KEINE Credentials (Entscheidung 2). Spiegelt `ExternalToolContent`
// (packages/models/src/who2be_models/external_tool.py).
export interface ExternalToolContent {
  display_name: string
  mcp_server_name: string
  tool_names: string[]
  // Stringifiziertes BlockNote-JSON-Dokument (wie `PlaybookContent.body`).
  usage_notes: string
  fallback_note: string | null
  tags: string[]
}

export interface ExternalTool {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  // Workspace-eindeutiger Faehigkeits-Alias (Ziel der `tool-ref`-Placeholder-
  // Referenz, WP-2). Vom Backend beim Anlegen aus dem Namen abgeleitet, falls
  // nicht gesetzt; danach unveraenderlich (kein Feld in `ExternalToolUpdate`).
  alias: string
  current_version: number
  current_status?: VersionStatus
  has_pending_draft?: boolean
  content: ExternalToolContent
  // Ein Element, eine Sprache (ADR-0045). Siehe `Persona.locale`.
  locale?: string
  created_at: string
  updated_at: string
  // Vom System verwaltet — User-Mutationen serverseitig gesperrt
  // (403 managed_aggregate); die UI rendert read-only.
  is_managed?: boolean
}

export interface ExternalToolVersion {
  version: number
  status?: VersionStatus
  content: ExternalToolContent
  created_by: string
  created_at: string
}

export interface ExternalToolInput {
  name: string
  content: ExternalToolContent
  // Ein Element, eine Sprache (ADR-0045). Nur beim Create genutzt
  // (ExternalToolCreate); Update-Aufrufer lassen das Feld weg
  // (ExternalToolUpdate kennt kein `locale`, `extra=forbid`).
  locale?: string
}

// Phase 3-B — Heading-only Block-Refs. Backend liefert ab Track A
// `available_in` und `section_preview`; bis dahin sind beide Felder
// optional und das Frontend faellt auf `available` + `preview` zurueck.
export type LinkAvailability = 'active' | 'draft' | null

export interface ResourceLink {
  resource_id: string
  resource_name: string
  block_id: string | null
  position: number
  available: boolean
  available_in?: LinkAvailability
  preview: string | null
  section_preview?: string | null
  link_scope?: ResourceLinkScope
  embedding_mode?: EmbeddingMode
}

// Phase-3-Fixes Track 4: ein Playbook→Resource-Link kann entweder das
// ganze Dokument referenzieren ('resource') oder einen Heading-Anker
// ('block'). Default im Backend ist 'block' — der optionale Feldwert
// bleibt zur Wire-Backward-Compat optional.
export type ResourceLinkScope = 'resource' | 'block'

// Embed-Modus einer Einbettung. 'lazy' (Default): reine Referenz — der MCP
// sendet das Ziel NICHT inline mit, der Agent laedt es bei Bedarf nach.
// 'inline': das Ziel-Dokument wird fest mitgesendet. Optional zur Wire-
// Backward-Compat (fehlt → 'lazy').
export type EmbeddingMode = 'lazy' | 'inline'

// Backlink-Records (Phase-3-Plan §Track-A.4). Endpoints liefern 404, bis
// Track A merged — die Hooks behandeln das als leere Liste + EmptyState.
export interface PlaybookUsage {
  persona_id: string
  persona_name: string
}

export interface ResourceUsage {
  playbook_id: string
  playbook_name: string
  block_count: number
}

// Einzel-Element-Delete (Plan 2026-06-05): wird ein Element noch von anderen
// Aggregaten referenziert, blockiert das Backend mit 409 und liefert die
// Verwender. Normalisierte Sicht eines Verwender-Eintrags — die UI liest den
// rohen Body defensiv aus, Felder sind daher allesamt optional.
export interface DeleteBlocker {
  id?: string
  name?: string
  // Quelle der Referenz: Map-Schluessel aus `blocked_by`
  // (agents/personas/playbooks/resources/composites).
  type?: string
}

// `HTTPException.detail` des Backends (`DeleteBlocked`): Klartext-`message` plus
// `blocked_by` als Map Quelle->Records. Die Records tragen quellspezifische
// Feldnamen (agent_name/persona_name/playbook_name/name; agent_id/persona_id/
// …/id), daher hier bewusst `unknown[]` — die Normalisierung macht
// `extractDeleteBlockers`.
export interface DeleteBlockedDetail {
  message?: string
  blocked_by?: Record<string, unknown[]>
}

export interface DeleteBlockedBody {
  // FastAPI verschachtelt `detail`: bei Delete-Konflikten ein DeleteBlockedDetail,
  // bei anderen Fehlern ein String. `blocked_by` auf Top-Level bleibt als
  // defensiver Fallback erlaubt.
  detail?: DeleteBlockedDetail | string
  blocked_by?: Record<string, unknown[]>
}

// Einzel-Element-Export (Plan 2026-06-05). JSON ist ein lose typisierter
// Abzug (Identitaet + alle Versionen), wird nur als Datei heruntergeladen.
export type EntityExport = Record<string, unknown>

export type EntityExportFormat = 'json' | 'markdown'

export interface ResourceLinkItemInput {
  resource_id: string
  block_id: string | null
  position: number
  link_scope: ResourceLinkScope
  embedding_mode?: EmbeddingMode
}

// Track E — Sub-Resource-Composition (Resource->Resource, §3.3).
// Schlanker Resource-Pointer fuer Used-By-Backlinks.
export interface ResourceRef {
  id: string
  name: string
}

// Ein direkter Sub-Resource-Verweis (Ausgabe). `fetch_call` ist die fertige
// MCP-Anweisung; im Web nur informativ. Backend liefert 404, bis Track E
// merged — die Hooks behandeln das als leere Liste.
export interface SubResource {
  id: string
  name: string
  link_scope: ResourceLinkScope
  block_id: string | null
  position: number
  fetch_call: string
  embedding_mode?: EmbeddingMode
}

// Eingabe-Item fuer PUT .../sub_resources. Default-Scope ist 'resource'
// (Volldokument-Referenz); Block-Anker analog ResourceLinkItemInput.
export interface SubResourceLinkInput {
  child_id: string
  block_id: string | null
  position: number
  link_scope: ResourceLinkScope
  embedding_mode?: EmbeddingMode
}

// Phase 3 Runde 3 Track 3 — SystemPromptTemplate-Aggregat.

// Track B (Nur-BlockNote): `body` ist immer ein stringifiziertes BlockNote-
// JSON-Dokument; der frueher gefuehrte `body_format`-Schalter entfaellt.
export interface SystemPromptTemplateContent {
  description: string
  body: string
}

export interface SystemPromptTemplate {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  slug: string
  current_version: number
  current_status?: VersionStatus
  has_pending_draft?: boolean
  content: SystemPromptTemplateContent
  // Ein Element, eine Sprache (ADR-0045). System-Prompt-Templates waren beim
  // urspruenglichen Content-i18n-Rollout (ADR-0027) bewusst ausgespart —
  // ziehen hier nach.
  locale?: string
  created_at: string
  updated_at: string
  // Vom System verwaltet (Builder-Template) — User-Mutationen serverseitig
  // gesperrt (403 managed_aggregate); die UI rendert read-only.
  is_managed?: boolean
  // List-Card-Pill: nur der List-Endpoint befuellt diesen Batch-Aggregat-Zaehler.
  // Anzahl der Agenten, die dieses Template nutzen.
  agent_count?: number
}

export interface SystemPromptTemplateVersion {
  version: number
  status?: VersionStatus
  content: SystemPromptTemplateContent
  created_by: string
  created_at: string
}

export interface SystemPromptTemplateInput {
  name: string
  slug?: string
  content: SystemPromptTemplateContent
  // Ein Element, eine Sprache (ADR-0045). Nur beim Create genutzt — Update
  // laesst das Feld weg (kein Sprachwechsel im Update-Payload vorgesehen).
  locale?: string
}

// Phase 3 Runde 3 Track 3 — Agent-Aggregat (Top-Level-Konfig, keine Versions).
export type AgentStatus = 'enabled' | 'disabled'

// Was dem Agenten zur Aktivierbarkeit fehlt — Codes aus `AgentRead.missing`.
export type AgentMissing = 'persona' | 'template' | 'persona_active'

// Pro-Agent-MCP-Tool-Policy (spiegelt AgentToolPolicy aus packages/models).
// Read-Scope: 'all' = ganzer Workspace, 'assigned' = nur zugewiesene (fuer
// agent_read: nur der eigene Agent), 'none' = aus.
export type ReadScope = 'all' | 'assigned' | 'none'

// ADR-0044 — Agent-Memory (kuratiert, agentisch). Lebenszyklus: `pending`
// (nur Triage-UI, retrieval-unsichtbar) → `active` (einzig retrieval-sichtbar)
// oder `rejected` (bleibt als Dedup-Wächter-Zeile bestehen, endgültig loeschbar).
export type MemoryStatus = 'pending' | 'active' | 'rejected'
export type MemoryCategory =
  | 'preference'
  | 'fact'
  | 'project'
  | 'instruction'
  | 'entity'
  | 'general'
// Speicher-Modus pro Agent, 4-stufig (geordnet): off < read_only < suggest <
// auto. Policy-Default 'off' (secure-by-default) — siehe DEFAULT_TOOL_POLICY.
export type MemoryMode = 'off' | 'read_only' | 'suggest' | 'auto'
// Verbindlichkeit der Abfrage-Anweisung im System-Prompt (nur bei mode != off
// wirksam). Default 'recommended'.
export type MemoryDirective = 'required' | 'recommended'

export interface MemoryRead {
  id: string
  agent_id: string
  status: MemoryStatus
  fact: string
  // Nur Triage-Hilfe (1 Satz Begruendung des Agenten) — nie im Retrieval/Prompt.
  context: string | null
  category: MemoryCategory
  importance: number
  source: string
  triage_note: string | null
  retrieval_count: number
  last_retrieved_at: string | null
  created_at: string
  updated_at: string
}

export interface MemoryTriageInput {
  action: 'approve' | 'reject'
  // Fakt-Edition vor Freigabe — nur bei action='approve' sinnvoll.
  fact?: string
  note?: string
}

export interface MemoryUpdateInput {
  fact?: string
  category?: MemoryCategory
  importance?: number
}

// ADR-0044-Addendum — Workspace-weiter Injection-Filter fuer save_memory,
// konfigurierbar pro Workspace (admin-only, Agent-Tokens 403). 'standard'
// (Default) = eingebauter Filter; 'custom' = eingebauter Filter + eigene
// literale Ausnahme-/Block-Phrasen (kein Regex, ADR-0044-Addendum); 'off' =
// kein Injection-Filter — gilt auch fuer Agenten im Automatisch-Modus (Dedup/
// Wichtigkeits-Schwelle/Limit bleiben davon unberuehrt). Phrasen: 2-100
// Zeichen, max. 50 pro Liste (Server validiert hart; Client spiegelt die
// Grenzen).
export type MemoryGuardMode = 'standard' | 'custom' | 'off'

export interface MemoryGuardConfig {
  mode: MemoryGuardMode
  allow_phrases: string[]
  block_phrases: string[]
}

export interface AgentToolPolicy {
  playbook_read: ReadScope
  resource_read: ReadScope
  agent_read: ReadScope
  // WP-3: Read-Scope fuer das ExternalTool-Aggregat. Default 'all' (nicht
  // 'assigned' wie die anderen Domains) — ExternalTool ist ein flacher
  // Workspace-Katalog ohne Persona-/Playbook-Zuordnung; 'assigned' verhaelt
  // sich serverseitig wie 'all' (keine Einschraenkung), nur 'none' sperrt.
  external_tool_read: ReadScope
  persona_read: boolean
  persona_write: boolean
  playbook_write: boolean
  resource_write: boolean
  agent_write: boolean
  // ADR-0040: System-Prompt-Templates verfassen + zur Review einreichen
  // (Aktivieren bleibt serverseitig gesperrt). ADR-0038: feedback_write deckt
  // das Usage-/Feedback-Flywheel ab (Default an); feedback_resolve die Triage
  // (Signale schliessen: addressed/in_progress/dismissed — Default aus).
  system_prompt_write: boolean
  // WP-3: ExternalTool-Aggregat schreiben (Default aus, secure by default).
  external_tool_write: boolean
  feedback_write: boolean
  feedback_resolve: boolean
  promote_retire: boolean
  // ADR-0047 — Agenten-Arbeitsbereich. `workarea_write` deckt Artifacts,
  // Ingest und Tabellen ab; `kb_write` die belegten Aussagen. Die Kanten sind
  // bewusst ein EIGENES Recht: sie sind im MVP nicht loeschbar, ein Fehlgriff
  // ist also dauerhaft. Zusaetzlich zur Capability entscheidet immer noch der
  // Area-Grant, WELCHEN Arbeitsbereich ein Agent sieht.
  workarea_write: boolean
  kb_write: boolean
  kb_edge_write: boolean
  // ADR-0039: Tag-Praedikat-Write-Scoping. Pro Domain (persona/playbook/resource)
  // erlaubte Tags; fehlend/leer = keine Tag-Einschraenkung. Optional, damit
  // Bestands-Payloads ohne das Feld weiterhin valide sind.
  write_tags?: Record<string, string[]>
  // ADR-0039: per-Domain-Verfeinerung von promote_retire (Narrowing). Fehlt ein
  // Domain-Eintrag, gilt das ungeteilte promote_retire.
  transition_grants?: Record<string, { promote: boolean; retire: boolean }>
  // ADR-0039: max. Schreib-Mutationen/Minute (null/fehlend = unbegrenzt).
  write_rate_limit?: number | null
  // ADR-0044: Agent-Memory-Speicher-Modus + Verbindlichkeit der Abfrage-
  // Anweisung im System-Prompt. Optional fuer Abwaerts-Kompatibilitaet
  // (JSONB); Defaults siehe DEFAULT_TOOL_POLICY.
  memory_mode?: MemoryMode
  memory_directive?: MemoryDirective
}

// Default-Policy fuer neue Agenten: nur Zugewiesenes lesen (least privilege/
// "secure by default"), nichts schreiben. Fuer agent_read heisst 'assigned'
// "nur der eigene Agent"; Owner kann pro Agent auf 'all' hochstufen.
export const DEFAULT_TOOL_POLICY: AgentToolPolicy = {
  playbook_read: 'assigned',
  resource_read: 'assigned',
  agent_read: 'assigned',
  // Default 'all' (nicht 'assigned') — siehe Feld-Kommentar oben.
  external_tool_read: 'all',
  persona_read: true,
  persona_write: false,
  playbook_write: false,
  resource_write: false,
  agent_write: false,
  system_prompt_write: false,
  external_tool_write: false,
  // Flywheel-Telemetrie ist Default an (ADR-0038), opt-out pro Agent; die
  // Triage (Signale schliessen) ist secure-by-default aus.
  feedback_write: true,
  feedback_resolve: false,
  promote_retire: false,
  // ADR-0047: Arbeitsbereich + Knowledge Base sind secure-by-default aus.
  workarea_write: false,
  kb_write: false,
  kb_edge_write: false,
  // ADR-0044: Gedaechtnis ist secure-by-default aus; Verbindlichkeit der
  // (erst bei mode != off aktiven) Abfrage-Anweisung defaultet auf "soll".
  memory_mode: 'off',
  memory_directive: 'recommended',
}

export interface Agent {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  description: string
  // null = leere Huelle: Persona bzw. Template noch nicht zugewiesen.
  persona_id: string | null
  system_prompt_template_id: string | null
  status: AgentStatus
  // Welche MCP-Tools der Agent nutzen darf (Default: alles lesen, nichts schreiben).
  tool_policy: AgentToolPolicy
  // Ob die verknuepfte Persona eine aktive Version hat (serverseitig gelesen).
  persona_active: boolean
  // Aktivierbar (enabled/kopierbar) = Persona + Template gesetzt UND Persona aktiv.
  activatable: boolean
  // Offene Luecken zur Aktivierbarkeit; leer ⇒ activatable.
  missing: AgentMissing[]
  created_at: string
  updated_at: string
  // Vom System verwaltet (geseedeter Builder) — User-Mutationen serverseitig
  // gesperrt (403 managed_aggregate). Duplizieren bleibt erlaubt (Deep-Copy).
  is_managed?: boolean
  // List-Card-Pills: nur der List-Endpoint befuellt diese denormalisierten
  // Namen/Zaehler. persona_name/template_name = null ohne Verknuepfung;
  // template_version = aktive Template-Version (null ohne aktive Version);
  // playbook_count = Playbooks der verknuepften Persona;
  // pending_memory_count = Gedaechtnis-Vorschlaege in der Freigabe-Schleuse
  // (agent_memory.status='pending', ADR-0044).
  persona_name?: string | null
  template_name?: string | null
  template_version?: number | null
  playbook_count?: number
  pending_memory_count?: number
  // Persoenlicher Favoriten-Stern des angemeldeten Users (Issue #427). Wie die
  // Pills darueber nur vom List-Endpoint befuellt; die Detail-Seite zeigt
  // keinen Stern und laesst das Feld deshalb auf `undefined`. Gesetzt/entfernt
  // ueber `favoriteAgent`/`unfavoriteAgent`, nicht ueber `updateAgent`.
  is_favorite?: boolean
  // ADR-0047 — betreiber-gepflegte Modell-Config: welches LLM diesen Agenten
  // faehrt. Sie gilt pro Agent-KONFIGURATION, nicht pro Einzelaufruf (Who2Be
  // ist kein Runtime-Host) und ist zusammen mit `agent_access_log` die
  // Grundlage der Compliance-Auskunft „welche sensiblen Elemente gingen je an
  // einen externen Anbieter". Pflege ist MENSCHEN vorbehalten — ein
  // agent-gebundener Token bekommt 403, sonst koennte ein Agent seine eigene
  // Attribution faelschen. null = nicht hinterlegt.
  model_provider?: string | null
  model_name?: string | null
}

export interface AgentInput {
  name: string
  description?: string
  // Optional: ohne Refs entsteht eine leere Huelle.
  persona_id?: string | null
  system_prompt_template_id?: string | null
  status?: AgentStatus
  tool_policy?: AgentToolPolicy
}

export interface AgentCopyInput {
  // Ohne Namen leitet der Server "<Name> (Kopie)" ab.
  name?: string
}

export interface AgentUpdateInput {
  name?: string
  description?: string
  persona_id?: string
  system_prompt_template_id?: string
  status?: AgentStatus
  // Gesetzt ⇒ ersetzt die Policy ganz; weggelassen ⇒ unveraendert.
  tool_policy?: AgentToolPolicy
  // Modell-Config (ADR-0047). Drei-Wege-Semantik: weggelassen ⇒ unveraendert,
  // nicht-leerer String ⇒ setzen, `''` ⇒ explizit auf null LEEREN. Ein
  // stehengebliebener falscher Anbieter wuerde die Compliance-Auskunft
  // dauerhaft verfaelschen — deshalb muss Leeren moeglich sein.
  model_provider?: string
  model_name?: string
}

export type AgentRenderFormat = 'plain' | 'markdown' | 'html'

export interface AgentRenderResult {
  content: string
  unresolved_placeholders: string[]
  format: AgentRenderFormat
}

// Pill-Preview (Editor-Overlay): aufgeloester Output einer einzelnen
// Placeholder-Pill. `unresolved=true`, wenn der Resolver keinen Wert fand
// (z. B. persona-field ohne Persona-Kontext) — die UI zeigt dann einen Hinweis.
export interface PlaceholderPreviewInput {
  kind: string
  target_id: string
  persona_id?: string
}

export interface PlaceholderPreview {
  kind: string
  target_id: string
  text: string
  unresolved: boolean
}

// Track A — Versionierung-Core. Spiegelt `VersionDiff`/`VersionDiffChange`
// aus packages/models. Serverseitig berechneter, read-only Feld-/Block-Diff
// einer Version gegen einen Vergleichsstand (`against`).
export type VersionDiffOp = 'added' | 'removed' | 'changed'

export interface VersionDiffChange {
  path: string
  op: VersionDiffOp
  before?: unknown
  after?: unknown
}

export interface VersionDiff {
  version: number
  against: string
  against_version: number | null
  changes: VersionDiffChange[]
  identical: boolean
  // WP-C (additiv): kanonische Klartext-Serialisierung beider Content-Staende
  // fuer den git-artigen Zeilen-Diff. Fehlen die Felder (aeltere API), faellt
  // die UI auf den reinen Feld-Diff zurueck.
  before_text?: string | null
  after_text?: string | null
}

// Track A — Status-Historie einer Version ("warum aktiv"). Spiegelt
// `StatusHistoryEntry` aus packages/models. `version` ist seit Migration 0029
// gefuehrt; Alt-Eintraege tragen null.
export interface ProvenanceEntry {
  id: string
  entity_type: string
  entity_id: string
  version: number | null
  from_status: VersionStatus | null
  to_status: VersionStatus
  changed_by: string
  changed_at: string
  note: string | null
}

// Track D — aufgeloestes Org-Entitlement + MCP-Verbrauch fuer den Billing-Slot.
// Spiegelt `EntitlementInfo` aus `routers/billing.py`. `edition` steuert die
// Sichtbarkeit: das Billing-Panel rendert nur unter `'cloud'`.
export interface EntitlementUsage {
  period: string
  count: number
}

export interface EntitlementInfo {
  edition: 'cloud' | 'onprem'
  status: 'active' | 'inactive'
  features: string[]
  expires_at: string | null
  mcp_monthly_quota: number | null
  mcp_rate_per_min: number | null
  usage: EntitlementUsage
}

// Mollie-Checkout (Track J). `plan` ist der buchbare Tier-Code (z. B. `'pro'`).
export interface CheckoutInput {
  plan: string
}

export interface CheckoutResult {
  checkout_url: string
}

// --- Usage-/Feedback-Flywheel (ADR-0038) ---------------------------------
// Telemetrie-Rueckkanal: Agenten melden Nutzung + Qualitaet, Kuratoren lesen das
// Aggregat. `entity_type` ist auf die drei Kern-Inhaltselemente beschraenkt.
export type FeedbackTarget = 'persona' | 'playbook' | 'resource'
// Posteingangs-Typ inkl. zielloses System-/MCP-Feedback ('system' = Problem an
// der Plattform selbst, ohne Inhalts-Bezug).
export type FeedbackEntityType = FeedbackTarget | 'system'
export type UsageOutcome = 'applied' | 'skipped' | 'error'
export type FeedbackSignal = 'helpful' | 'outdated' | 'incorrect' | 'unclear'
// Kategorie eines System-/MCP-Problems (liegt bei System-Feedback im signal-Feld).
export type SystemFeedbackCategory = 'technical' | 'mcp' | 'performance' | 'other'

// Eingabe von `POST /system-feedback` (Mensch via UI, Agent via MCP).
export interface SystemFeedbackInput {
  category: SystemFeedbackCategory
  note: string
}
// Eingabe von `POST /feedback` (Inhalts-Feedback, spiegelt Backend `FeedbackCreate`).
export interface FeedbackInput {
  entity_type: FeedbackTarget
  entity_id: string
  version?: number
  signal: FeedbackSignal
  note?: string
}
// Triage-Status eines Feedback-Eintrags (ADR-0038, append-only).
export type FeedbackResolution = 'addressed' | 'in_progress' | 'dismissed'

// Ein einzelnes Feedback im Aggregat: id + aktueller Triage-Status — damit
// (auch MCP-)Konsumenten offene Signale gezielt schliessen koennen.
export interface FeedbackSummaryItem {
  id: string
  signal: FeedbackSignal | SystemFeedbackCategory
  note: string | null
  // Aktueller Triage-Status (juengstes Resolution-Event) oder null = offen.
  resolution: FeedbackResolution | null
  created_at: string
}

// Aggregat fuer das Detail-Panel (`GET …/feedback/{type}/{id}`).
export interface FeedbackSummary {
  entity_type: FeedbackTarget
  entity_id: string
  usage_count: number
  by_outcome: Partial<Record<UsageOutcome, number>>
  by_signal: Partial<Record<FeedbackSignal, number>>
  recent_notes: string[]
  // Additiv (juengste Einzel-Feedbacks inkl. id/resolution); optional, damit
  // Bestands-Payloads/Mocks ohne das Feld weiterhin valide sind.
  recent_feedback?: FeedbackSummaryItem[]
}

// Einzel-Ereignisse (Drill-down, `GET …/feedback/{type}/{id}/events`).
export interface AgentFeedback {
  id: string
  entity_type: FeedbackTarget
  entity_id: string
  version: number | null
  signal: FeedbackSignal
  note: string | null
  agent_id: string | null
  created_at: string
  // Aktueller Triage-Status (juengstes Resolution-Event) oder null.
  resolution: FeedbackResolution | null
}

export interface FeedbackResolutionInput {
  resolution: FeedbackResolution
  note?: string
}

// Ein einzelnes Triage-Ereignis der Historie (append-only, aeltestes zuerst).
export interface FeedbackResolutionEvent {
  resolution: FeedbackResolution
  actor_id: string | null
  note: string | null
  created_at: string
}

// Detailsicht auf EIN Feedback (`GET …/feedback/{feedbackId}`): alle Felder aus
// FeedbackItem + menschlicher Absender (actor_id) + vollstaendige Triage-Historie
// (aelteste→juengste). Datengrundlage der Einzel-Feedback-Detailseite.
export interface FeedbackDetail {
  id: string
  entity_type: FeedbackEntityType
  entity_id: string | null
  name: string
  version: number | null
  signal: FeedbackSignal | SystemFeedbackCategory
  note: string | null
  agent_id: string | null
  actor_id: string | null
  created_at: string
  resolution: FeedbackResolution | null
  history: FeedbackResolutionEvent[]
}

// Ein Feedback workspace-weit, angereichert um den Element-Namen — Ruckgrat des
// zentralen Posteingangs (`GET …/feedback-items`).
export interface FeedbackItem {
  id: string
  // 'system' = zielloses Plattform-/MCP-Feedback (entity_id null, signal traegt
  // eine SystemFeedbackCategory, name = "System").
  entity_type: FeedbackEntityType
  entity_id: string | null
  name: string
  version: number | null
  signal: FeedbackSignal | SystemFeedbackCategory
  note: string | null
  agent_id: string | null
  created_at: string
  resolution: FeedbackResolution | null
}

export interface FeedbackItemCounts {
  open: number
  in_progress: number
  addressed: number
  dismissed: number
}

export interface FeedbackItems {
  items: FeedbackItem[]
  counts: FeedbackItemCounts
}

export interface UsageEvent {
  id: string
  entity_type: FeedbackTarget
  entity_id: string
  version: number | null
  outcome: UsageOutcome | null
  agent_id: string | null
  created_at: string
}

export interface FeedbackEvents {
  entity_type: FeedbackTarget
  entity_id: string
  feedback: AgentFeedback[]
  usage: UsageEvent[]
}

// Workspace-weite Kurations-Uebersicht (`GET …/feedback-overview`).
export interface FeedbackOverviewItem {
  entity_type: FeedbackTarget
  entity_id: string
  name: string
  usage_count: number
  feedback_count: number
  negative_count: number
  helpful_count: number
  last_activity_at: string | null
}

export interface FeedbackOverview {
  items: FeedbackOverviewItem[]
}

// Veroeffentlichte, aber ungenutzte Elemente (`GET …/feedback-unused`): aktive
// Version vorhanden, aber kein einziges Usage-/Feedback-Ereignis (Stale).
export interface FeedbackUnusedItem {
  entity_type: FeedbackTarget
  entity_id: string
  name: string
}

export interface FeedbackUnused {
  items: FeedbackUnusedItem[]
}

// ---------------------------------------------------------------------------
// Agenten-Arbeitsbereich + Knowledge Base (ADR-0047). Spiegelt
// `packages/models/src/who2be_models/{workarea,kb}.py`. Beide Subsysteme sind
// UNVERSIONIERT (kein draft/review/active, kein Draft-Lock) — sie stehen NEBEN
// der Resource-Achse, nicht darin. Die Web-UI liest sie; geschrieben werden
// Inhalte von Agenten ueber MCP (Ausnahme: Artifact loeschen).
// ---------------------------------------------------------------------------

// „privat" heisst privat gegenueber anderen AGENTEN — Menschen ab Rolle editor
// lesen auch fremde private Areas (User-Entscheidung 5). Viewer sehen nur
// `shared`. Genau eine private Area pro Agent, auto-angelegt beim ersten Zugriff.
export type WorkAreaScope = 'private' | 'shared'
export type WorkAreaGrantLevel = 'read' | 'write'
export type ArtifactType = 'doc' | 'table' | 'blob'
// `occurred_at` ist serverseitig Pflicht ohne now()-Fallback; der bewusste
// Ausweg bei unbekanntem Zeitpunkt ist `unknown` (Timeline-Sonderbucket).
export type OccurredPrecision = 'day' | 'minute' | 'unknown'
export type Sensitivity = 'general' | 'sensitive'

export interface WorkArea {
  id: string
  workspace_id: string
  scope: WorkAreaScope
  // Nur bei `scope='private'` gesetzt (CHECK-Constraint in Migration 0073).
  owner_agent_id: string | null
  name: string
  // null = unbegrenzt (Default); sonst raeumt der Retention-Sweep aelteres ab.
  retention_days: number | null
  created_at: string
  updated_at: string
}

export interface WorkAreaGrant {
  area_id: string
  agent_id: string
  level: WorkAreaGrantLevel
  created_at: string
}

export interface WorkAreaCreateInput {
  name: string
  retention_days?: number | null
}

export interface WorkAreaGrantInput {
  level: WorkAreaGrantLevel
}

// Metadaten-Zeile eines Artifacts (`GET .../work-areas/{id}/artifacts`).
// `blocks` liefert nur der MCP-Pfad; die Web-Lese-Ansicht nimmt das gerenderte
// Markdown aus `ArtifactMarkdown`, deshalb hier bewusst nicht getragen.
export interface WaArtifact {
  id: string
  area_id: string
  workspace_id: string
  type: ArtifactType
  title: string
  // Optimistische Revision — steigt bei jedem append/patch.
  rev: number
  occurred_at: string
  occurred_precision: OccurredPrecision
  sensitivity: Sensitivity
  source_system: string | null
  source_url: string | null
  fetched_at: string | null
  blob_sha256: string | null
  content_ref: string | null
  created_at: string
  updated_at: string
  // Akteur-Kennung `agent:<id>` | `user:<id>`.
  updated_by: string | null
}

// `GET .../wa-artifacts/{id}` — Markdown mit `[#block_id]`-Anker-Annotationen
// (ADR-0021). Traegt bewusst KEINE Metadaten; die kommen aus der Area-Liste.
export interface ArtifactMarkdown {
  artifact_id: string
  title: string
  rev: number
  markdown: string
}

// Suchtreffer der WorkArea-Suche — Anker + Snippet, nie das ganze Dokument.
// `anchor` ist `<artifact_id>#<block_id>` und direkt aufloesbar.
export interface WorkAreaSearchHit {
  anchor: string
  artifact_id: string
  block_id: string
  title: string
  snippet: string
  score: number
  area_id: string
}

// Geordnete Vertrauensleiter: hypothesis < derived < verified. Das Heben auf
// `verified` ist bewusst kein Agenten-Recht (P2-UI-Thema).
export type NodeTier = 'verified' | 'derived' | 'hypothesis'
// `stale` setzt nur der (noch nicht gebaute) P1-Verfalls-Sweep.
export type NodeStatus = 'live' | 'stale'
export type SourceRefKind = 'blob' | 'url' | 'artifact'
export type EdgeType =
  | 'supports'
  | 'contradicts'
  | 'supersedes'
  | 'derived_from'
  | 'belongs_to'
  | 'co_occurs_with'

export interface KbNode {
  id: string
  workspace_id: string
  tier: NodeTier
  // Die Aussage selbst.
  content: string
  // Optionaler Herkunfts-Anker des Aussage-TEXTS.
  content_ref: string | null
  // Pflicht-Beleg (Belegpflicht, ADR-0047): `sha256:<h>` | `url:<u>` |
  // `artifact:<uuid>[#block]`. `source_ref_kind` leitet der Server daraus ab.
  source_ref: string
  source_ref_kind: SourceRefKind
  ttl_expires_at: string | null
  status: NodeStatus
  // Laenge der `derived_from`-Kette ab Roh-Beleg (P1: Drift-Grenze).
  derivation_depth: number
  sensitivity: Sensitivity
  occurred_at: string
  occurred_precision: OccurredPrecision
  created_by: string | null
  created_at: string
  updated_at: string
}

// Nachbar aus `GET .../kb/neighbors`. `co_n` traegt bei `co_occurs_with` IMMER
// die Fallzahl mit — eine Korrelation ohne Fallzahl waere eine Behauptung.
export interface KbNeighbor {
  node: KbNode
  edge_type: EdgeType
  direction: 'in' | 'out'
  co_n: number | null
}

// KB-Treffer; `anchor` ist `node:<uuid>`. Eigener Index — die KB-Suche liefert
// per Konstruktion nie WorkArea-Rohmaterial.
export interface KbSearchHit {
  node_id: string
  anchor: string
  snippet: string
  tier: NodeTier
  status: NodeStatus
  score: number
}

// ---------------------------------------------------------------------------
// Tabellen-Store (ADR-0049). Spiegelt
// `packages/models/src/who2be_models/tables.py`. Eine Tabelle liegt als
// SQLite-Datei je WorkArea; Postgres traegt nur den Katalog (`schema_json`).
// Wire-Feld heisst `schema` (Python-Alias fuer `schema_`, weil `.schema`
// bei Pydantic-Modellen belegt ist) — hier direkt als `schema` typisiert.
// ---------------------------------------------------------------------------

// Typen-Allowlist der Tabellen-Spalten — bewusst klein (kein blob/json).
export type TableColumnType = 'text' | 'integer' | 'numeric' | 'date' | 'timestamp' | 'boolean'

export interface TableColumn {
  // SQL-sicherer Identifier (`^[a-z][a-z0-9_]*$`) — geht verbatim in DDL ein.
  name: string
  type: TableColumnType
  nullable: boolean
}

export interface TableSchema {
  columns: TableColumn[]
  // Spalten fuer den idempotenten Zeilen-Import (Dedupe-Hash).
  dedupe_columns: string[]
  // Kategorisierungs-Eingang (Regel-Matching).
  match_column: string | null
  // Kategorisierungs-Ziel.
  category_column: string | null
}

// Eine Tabelle im aktuellen Stand (`GET .../work-areas/{id}/tables` |
// `wa_table`). `row_count` ist im Listen-Pfad null; der describe-Pfad
// (`TableDescription`) befuellt die Zeilenzahl separat.
export interface WaTable {
  id: string
  workspace_id: string
  area_id: string
  name: string
  schema: TableSchema
  row_count: number | null
  created_at: string
  updated_at: string
}

// Quell-Konvention (Einheiten, Notation, Dezimal-/Datumsformat einer
// Importquelle) — Pflicht, sobald ein Import `source_name` setzt.
export interface SourceConvention {
  id: string
  area_id: string
  source_name: string
  convention: Record<string, unknown>
  // Mensch, der die Konvention gesetzt hat (null = System-Seed).
  created_by: string | null
  created_at: string
  updated_at: string
}

// Antwort von `GET .../wa-tables/{id}` (describe) — Kontext fuer Agenten und
// die UI, ohne Rohdaten-Dump. `column_stats` liefert pro Spalte
// Wertebereiche/Verteilung (z. B. min, max, distinct) aus der SQLite-Datei.
export interface TableDescription {
  schema: TableSchema
  row_count: number
  column_stats: Record<string, Record<string, unknown>>
  conventions: SourceConvention[]
}

// Ausgabeformat einer Tabellen-Query (agentengerecht).
export type TableQueryFormat = 'json' | 'markdown' | 'csv'

// Eingabe fuer `POST .../wa-tables/{id}/query` — read-only SQL. `format`
// default `json` serverseitig, `limit` default 200 (Zeilen-Cap).
export interface TableQueryInput {
  sql: string
  format?: TableQueryFormat
  limit?: number
}

// Ergebnis einer Tabellen-Query. `rows` ist bei `format='json'` gefuellt,
// `rendered` bei markdown/csv — genau eine der beiden Darstellungen.
// `truncated` zeigt an, dass das Zeilen-Cap (`limit`) das Ergebnis
// beschnitten hat.
export interface TableQueryResult {
  columns: string[]
  rows: unknown[][] | null
  rendered: string | null
  row_count: number
  truncated: boolean
}

// Export-Formate fuer Tabellen- bzw. Artifact-Downloads (Binaer-/Text-Blob,
// naechste Backend-Welle — Client-Methoden existieren bereits).
export type TableExportFormat = 'csv' | 'xlsx'
export type ArtifactExportFormat = 'markdown' | 'html'
