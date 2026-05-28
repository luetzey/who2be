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

export interface MeWorkspaceMembership {
  id: string
  name: string
  slug: string
  role: 'admin' | 'editor' | 'viewer'
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
