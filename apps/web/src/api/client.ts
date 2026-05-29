import { config } from '../config'
import type {
  DashboardData,
  Invitation,
  InvitationAcceptResult,
  InvitationInput,
  Me,
  Member,
  MemberUpdateInput,
  Persona,
  PersonaInput,
  PersonaVersion,
  Playbook,
  PlaybookInput,
  PlaybookVersion,
  Resource,
  ResourceInput,
  ResourceLink,
  ResourceLinkItemInput,
  ResourceVersion,
  Token,
  TokenCreated,
  TokenInput,
  VersionStatus,
} from './types'

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(token: string, path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string> | undefined),
  }
  // Kein leerer Bearer-Header, wenn (noch) kein Token vorliegt.
  if (token !== '') {
    headers.Authorization = `Bearer ${token}`
  }
  let response: Response
  try {
    response = await fetch(`${config.apiBaseUrl}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'Who2Be-API nicht erreichbar.')
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

async function readErrorMessage(response: Response): Promise<string> {
  const fallback = `Who2Be-API-Fehler (${response.status}).`
  if (!response.headers.get('content-type')?.includes('application/json')) {
    return fallback
  }
  try {
    const body = (await response.json()) as { detail?: unknown }
    return typeof body.detail === 'string' && body.detail.length > 0
      ? body.detail
      : fallback
  } catch {
    return fallback
  }
}

// Tenant-weiter Read — Workspace-Resolution beim Bootstrap, vor `createApi`.
export function fetchMe(token: string): Promise<Me> {
  return request<Me>(token, '/v1/me')
}

// Invitation-Annahme ist bewusst NICHT workspace-scoped: der Einladende kennt
// den Ziel-Workspace, der Eingeladene noch nicht. Der Pfad traegt nur den
// Klartext-Token; die Response liefert den Workspace, in den man eingetreten ist.
export function acceptInvitation(
  token: string,
  invitationToken: string,
): Promise<InvitationAcceptResult> {
  return request<InvitationAcceptResult>(
    token,
    `/v1/invitations/${invitationToken}/accept`,
    { method: 'POST' },
  )
}

export interface Api {
  listPersonas: () => Promise<Persona[]>
  getPersona: (id: string) => Promise<Persona>
  createPersona: (input: PersonaInput) => Promise<Persona>
  updatePersona: (id: string, input: PersonaInput) => Promise<Persona>
  listPersonaVersions: (id: string) => Promise<PersonaVersion[]>
  listPersonaPlaybooks: (id: string) => Promise<Playbook[]>
  setPersonaPlaybooks: (id: string, playbookIds: string[]) => Promise<Playbook[]>
  listPlaybooks: (filters?: { tag?: string; trigger?: string }) => Promise<Playbook[]>
  getPlaybook: (id: string) => Promise<Playbook>
  createPlaybook: (input: PlaybookInput) => Promise<Playbook>
  updatePlaybook: (id: string, input: PlaybookInput) => Promise<Playbook>
  listPlaybookVersions: (id: string) => Promise<PlaybookVersion[]>
  // Phase 3-B — DISTINCT-Tag-Vorschlag fuer den `TagInput`. Backend
  // liefert das Endpoint mit Track A; bis dahin antwortet es 404 — der
  // TagInput-Konsument faengt das als leeres Vorschlag-Set ab.
  listPlaybookTags: () => Promise<string[]>
  listTokens: () => Promise<Token[]>
  createToken: (input: TokenInput) => Promise<TokenCreated>
  revokeToken: (id: string) => Promise<void>
  getDashboard: () => Promise<DashboardData>
  transitionPersonaVersion: (
    id: string,
    version: number,
    to: VersionStatus,
  ) => Promise<PersonaVersion>
  transitionPlaybookVersion: (
    id: string,
    version: number,
    to: VersionStatus,
  ) => Promise<PlaybookVersion>
  listResources: () => Promise<Resource[]>
  getResource: (id: string) => Promise<Resource>
  createResource: (input: ResourceInput) => Promise<Resource>
  updateResource: (id: string, input: ResourceInput) => Promise<Resource>
  listResourceVersions: (id: string) => Promise<ResourceVersion[]>
  transitionResourceVersion: (
    id: string,
    version: number,
    to: VersionStatus,
  ) => Promise<ResourceVersion>
  listPlaybookResourceLinks: (playbookId: string) => Promise<ResourceLink[]>
  setPlaybookResourceLinks: (
    playbookId: string,
    links: ResourceLinkItemInput[],
  ) => Promise<ResourceLink[]>
  listMembers: () => Promise<Member[]>
  updateMemberRole: (userId: string, input: MemberUpdateInput) => Promise<Member>
  removeMember: (userId: string) => Promise<void>
  listInvitations: () => Promise<Invitation[]>
  createInvitation: (input: InvitationInput) => Promise<Invitation>
  revokeInvitation: (id: string) => Promise<void>
}

export function createApi(token: string, workspaceId: string): Api {
  const ws = `/v1/workspaces/${workspaceId}`
  return {
    listPersonas: () => request<Persona[]>(token, `${ws}/personas`),
    getPersona: (id) => request<Persona>(token, `${ws}/personas/${id}`),
    createPersona: (input) =>
      request<Persona>(token, `${ws}/personas`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updatePersona: (id, input) =>
      request<Persona>(token, `${ws}/personas/${id}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    listPersonaVersions: (id) =>
      request<PersonaVersion[]>(token, `${ws}/personas/${id}/versions`),
    listPersonaPlaybooks: (id) =>
      request<Playbook[]>(token, `${ws}/personas/${id}/playbooks`),
    setPersonaPlaybooks: (id, playbookIds) =>
      request<Playbook[]>(token, `${ws}/personas/${id}/playbooks`, {
        method: 'PUT',
        body: JSON.stringify({ playbook_ids: playbookIds }),
      }),
    listPlaybooks: (filters) => {
      const params = new URLSearchParams()
      if (filters?.tag) params.set('tag', filters.tag)
      if (filters?.trigger) params.set('trigger', filters.trigger)
      const query = params.toString()
      return request<Playbook[]>(token, `${ws}/playbooks${query ? `?${query}` : ''}`)
    },
    getPlaybook: (id) => request<Playbook>(token, `${ws}/playbooks/${id}`),
    createPlaybook: (input) =>
      request<Playbook>(token, `${ws}/playbooks`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updatePlaybook: (id, input) =>
      request<Playbook>(token, `${ws}/playbooks/${id}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    listPlaybookVersions: (id) =>
      request<PlaybookVersion[]>(token, `${ws}/playbooks/${id}/versions`),
    listPlaybookTags: () => request<string[]>(token, `${ws}/playbooks/tags`),
    listTokens: () => request<Token[]>(token, `${ws}/tokens`),
    createToken: (input) =>
      request<TokenCreated>(token, `${ws}/tokens`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    revokeToken: (id) =>
      request<void>(token, `${ws}/tokens/${id}`, { method: 'DELETE' }),
    getDashboard: () => request<DashboardData>(token, `${ws}/dashboard`),
    transitionPersonaVersion: (id, version, to) =>
      request<PersonaVersion>(
        token,
        `${ws}/personas/${id}/versions/${version}/transition`,
        { method: 'POST', body: JSON.stringify({ to }) },
      ),
    transitionPlaybookVersion: (id, version, to) =>
      request<PlaybookVersion>(
        token,
        `${ws}/playbooks/${id}/versions/${version}/transition`,
        { method: 'POST', body: JSON.stringify({ to }) },
      ),
    listResources: () => request<Resource[]>(token, `${ws}/resources`),
    getResource: (id) => request<Resource>(token, `${ws}/resources/${id}`),
    createResource: (input) =>
      request<Resource>(token, `${ws}/resources`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updateResource: (id, input) =>
      request<Resource>(token, `${ws}/resources/${id}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    listResourceVersions: (id) =>
      request<ResourceVersion[]>(token, `${ws}/resources/${id}/versions`),
    transitionResourceVersion: (id, version, to) =>
      request<ResourceVersion>(
        token,
        `${ws}/resources/${id}/versions/${version}/transition`,
        { method: 'POST', body: JSON.stringify({ to }) },
      ),
    listPlaybookResourceLinks: (playbookId) =>
      request<ResourceLink[]>(token, `${ws}/playbooks/${playbookId}/resource_links`),
    setPlaybookResourceLinks: (playbookId, links) =>
      request<ResourceLink[]>(token, `${ws}/playbooks/${playbookId}/resource_links`, {
        method: 'PUT',
        body: JSON.stringify({ links }),
      }),
    listMembers: () => request<Member[]>(token, `${ws}/members`),
    updateMemberRole: (userId, input) =>
      request<Member>(token, `${ws}/members/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    removeMember: (userId) =>
      request<void>(token, `${ws}/members/${userId}`, { method: 'DELETE' }),
    listInvitations: () => request<Invitation[]>(token, `${ws}/invitations`),
    createInvitation: (input) =>
      request<Invitation>(token, `${ws}/invitations`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    revokeInvitation: (id) =>
      request<void>(token, `${ws}/invitations/${id}`, { method: 'DELETE' }),
  }
}
