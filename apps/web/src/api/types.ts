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
  created_at: string
  updated_at: string
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
  created_at: string
  updated_at: string
  // Track A8 — abgeleitet: hat Kinder in playbook_composition.
  is_composite?: boolean
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
}

export interface Token {
  id: string
  workspace_id: string
  name: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
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
}

export interface WorkspaceInput {
  name: string
  slug: string
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

export interface Resource {
  id: string
  workspace_id: string
  owner_id: string
  name: string
  current_version: number
  current_status?: VersionStatus
  has_pending_draft?: boolean
  content: ResourceContent
  created_at: string
  updated_at: string
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
}

// Phase-3-Fixes Track 4: ein Playbook→Resource-Link kann entweder das
// ganze Dokument referenzieren ('resource') oder einen Heading-Anker
// ('block'). Default im Backend ist 'block' — der optionale Feldwert
// bleibt zur Wire-Backward-Compat optional.
export type ResourceLinkScope = 'resource' | 'block'

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

export interface ResourceLinkItemInput {
  resource_id: string
  block_id: string | null
  position: number
  link_scope: ResourceLinkScope
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
}

// Eingabe-Item fuer PUT .../sub_resources. Default-Scope ist 'resource'
// (Volldokument-Referenz); Block-Anker analog ResourceLinkItemInput.
export interface SubResourceLinkInput {
  child_id: string
  block_id: string | null
  position: number
  link_scope: ResourceLinkScope
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
  created_at: string
  updated_at: string
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
}

// Phase 3 Runde 3 Track 3 — Agent-Aggregat (Top-Level-Konfig, keine Versions).
export type AgentStatus = 'enabled' | 'disabled'

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
  created_at: string
  updated_at: string
}

export interface AgentInput {
  name: string
  description?: string
  // Optional: ohne Refs entsteht eine leere Huelle.
  persona_id?: string | null
  system_prompt_template_id?: string | null
  status?: AgentStatus
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
