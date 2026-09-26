import type { WorkspaceRole } from '@/api/types'

// Rollen-Hierarchie laut ADR-0023, vom maechtigsten zum schwaechsten.
export const ROLE_ORDER: readonly WorkspaceRole[] = ['admin', 'editor', 'viewer']

const ROLE_LABELS: Record<WorkspaceRole, string> = {
  admin: 'Admin',
  editor: 'Editor',
  viewer: 'Viewer',
}

export function roleLabel(role: WorkspaceRole): string {
  return ROLE_LABELS[role]
}

// Rollen, die hoechstens so maechtig sind wie `max` — fuer „kann keine Rolle
// vergeben, die ueber der eigenen liegt" (Token-Snapshot, Invite).
export function rolesAtMost(max: WorkspaceRole): WorkspaceRole[] {
  const cutoff = ROLE_ORDER.indexOf(max)
  return ROLE_ORDER.filter((_, index) => index >= cutoff)
}

// Obergrenze fuer an einen Agenten gebundene API-Tokens. Die Rolle `admin` an
// einem Maschinen-Token verschafft ihm Reichweite, die seine Tool-Policy nicht
// begrenzt; das Backend lehnt sie mit 403 `agent_bound_role_capped` ab. Hier
// nur, damit die Auswahl nicht anbietet, was der Server gleich verweigert —
// durchgesetzt wird die Grenze serverseitig, nicht von dieser Liste.
export const AGENT_BOUND_MAX_ROLE: WorkspaceRole = 'editor'

// Die Rollen, die ein agent-gebundener Token tragen darf: nie mehr als die
// eigene Rolle (`max`) UND nie mehr als die Maschinen-Obergrenze.
export function agentBoundRoleOptions(max: WorkspaceRole): WorkspaceRole[] {
  const cutoff = Math.max(ROLE_ORDER.indexOf(max), ROLE_ORDER.indexOf(AGENT_BOUND_MAX_ROLE))
  return ROLE_ORDER.filter((_, index) => index >= cutoff)
}

// True, wenn `next` schwaecher ist als `current` (Demote). `ROLE_ORDER` ist
// vom maechtigsten zum schwaechsten sortiert — hoeherer Index = weniger Rechte.
export function isDowngrade(current: WorkspaceRole, next: WorkspaceRole): boolean {
  return ROLE_ORDER.indexOf(next) > ROLE_ORDER.indexOf(current)
}
