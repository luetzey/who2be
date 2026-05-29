// TypeScript-Spiegel der Pydantic-Modelle aus packages/models. Handgepflegt —
// es gibt bewusst keinen Cross-Language-Typgenerator.

// Phase 2.1b — wird vom Backend pro Version gefuehrt. Bis 2.1b-A/B gemergt
// ist, fehlen die Felder in der Response; alle UI-Branches lesen sie optional.
export type VersionStatus = 'draft' | 'review' | 'active' | 'inactive'

export interface PersonaContent {
  description: string
  system_prompt: string
  traits: string[]
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

// Curated Set fuer `playbook.type` (Track 0). UI-Selects beziehen ihre
// Optionen daraus; Backend setzt CHECK-Constraint.
export type PlaybookType =
  | 'prompt'
  | 'instructions'
  | 'snippet'
  | 'workflow'
  | 'checklist'
  | 'faq'

export interface PlaybookContent {
  description: string
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
  // liefert sie (Join auf auth.users); fehlt sie, faellt die UI auf user_id.
  email: string
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

// Dashboard-Endpoint (Phase 2.1b §2.1.E). Felder folgen dem Plan-Beispiel
// in `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`. Backend
// implementiert das in Phase 2.1b-A/B — bis dahin darf der Endpoint 404
// oder ein leeres Objekt zurueckgeben.
export type DashboardEntityType = 'persona' | 'playbook'

export interface DashboardKpis {
  active_personas: number
  active_playbooks: number
  pending_reviews: number
}

export interface DashboardActor {
  user_id: string
  display_name?: string | null
}

export interface DashboardActivity {
  ts: string
  actor: DashboardActor
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
}

export interface DashboardData {
  kpis: DashboardKpis
  activity: DashboardActivity[]
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

// Track A erweitert das Backend um `available_in` (siehe Phase-3-Plan
// §Track-A.3). Bis das gemerged ist, liefert das Backend nur `available`
// — das neue Feld bleibt optional, das UI fragt es defensiv ab.
export interface ResourceLink {
  resource_id: string
  resource_name: string
  block_id: string
  position: number
  available: boolean
  available_in?: 'active' | 'draft' | null
  preview: string | null
}

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
  block_id: string
  position: number
}
