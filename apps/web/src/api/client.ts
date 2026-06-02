import { config } from '../config'
import type {
  Agent,
  AgentInput,
  AgentRenderFormat,
  AgentRenderResult,
  AgentUpdateInput,
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
  PlaceholderPreview,
  PlaceholderPreviewInput,
  Playbook,
  ProvenanceEntry,
  PlaybookInput,
  PlaybookRef,
  PlaybookUsage,
  PlaybookVersion,
  Resource,
  ResourceInput,
  ResourceLink,
  ResourceLinkItemInput,
  ResourceUsage,
  ResourceVersion,
  SystemPromptTemplate,
  SystemPromptTemplateInput,
  SystemPromptTemplateVersion,
  Token,
  TokenCreated,
  TokenInput,
  VersionDiff,
  VersionStatus,
} from './types'

export class ApiError extends Error {
  /**
   * Rohes JSON-Body-Objekt, wenn die Antwort als `application/problem+json`
   * oder `application/json` geparst werden konnte. Damit koennen Aufrufer
   * (z. B. StatusActionBar) das `missing`-Array bei 409 auslesen.
   */
  readonly body: unknown

  constructor(
    readonly status: number,
    message: string,
    body?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
    this.body = body ?? null
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
    const { message, body } = await readErrorBody(response)
    throw new ApiError(response.status, message, body)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

async function readErrorBody(
  response: Response,
): Promise<{ message: string; body: unknown }> {
  const fallback = `Who2Be-API-Fehler (${response.status}).`
  const contentType = response.headers.get('content-type') ?? ''
  if (
    !contentType.includes('application/json') &&
    !contentType.includes('application/problem+json')
  ) {
    return { message: fallback, body: null }
  }
  try {
    const body = (await response.json()) as { detail?: unknown }
    const message =
      typeof body.detail === 'string' && body.detail.length > 0 ? body.detail : fallback
    return { message, body }
  } catch {
    return { message: fallback, body: null }
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
  // Auto-Save (Phase 3-Runde-3 Track 2): schreibt in den Draft, ohne neue
  // Version anzulegen. Active bleibt unangetastet — der explizite Submit
  // (Status-Transition draft→review) erfolgt separat.
  patchPersonaDraft: (id: string, input: PersonaInput) => Promise<Persona>
  patchPlaybookDraft: (id: string, input: PlaybookInput) => Promise<Playbook>
  patchResourceDraft: (id: string, input: ResourceInput) => Promise<Resource>
  listPersonaVersions: (id: string) => Promise<PersonaVersion[]>
  // Phase 3 — DISTINCT-Persona-Tag-Vorschlag fuer den `TagInput` im
  // Persona-Editor. Eigene Quelle (nicht `listPlaybookTags`), damit der
  // Picker zur jeweiligen Domaene passt.
  listPersonaTags: () => Promise<string[]>
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
  getPlaybookUsages: (id: string) => Promise<PlaybookUsage[]>
  getResourceUsages: (id: string) => Promise<ResourceUsage[]>
  // Track A8 — Composite-Playbook-Endpoints.
  listPlaybookComposes: (id: string) => Promise<Playbook[]>
  setPlaybookComposes: (id: string, childIds: string[]) => Promise<Playbook[]>
  listPlaybookComposedBy: (id: string) => Promise<PlaybookRef[]>
  // Track E3 — Resource-Tags.
  listResourceTags: () => Promise<string[]>
  listResourcesByTag: (tag: string) => Promise<Resource[]>
  listMembers: () => Promise<Member[]>
  updateMemberRole: (userId: string, input: MemberUpdateInput) => Promise<Member>
  removeMember: (userId: string) => Promise<void>
  listInvitations: () => Promise<Invitation[]>
  createInvitation: (input: InvitationInput) => Promise<Invitation>
  revokeInvitation: (id: string) => Promise<void>
  // Phase 3 Runde 3 Track 3 — SystemPromptTemplate + Agent.
  listSystemPromptTemplates: () => Promise<SystemPromptTemplate[]>
  getSystemPromptTemplate: (id: string) => Promise<SystemPromptTemplate>
  createSystemPromptTemplate: (
    input: SystemPromptTemplateInput,
  ) => Promise<SystemPromptTemplate>
  updateSystemPromptTemplate: (
    id: string,
    input: SystemPromptTemplateInput,
  ) => Promise<SystemPromptTemplate>
  listSystemPromptTemplateVersions: (
    id: string,
  ) => Promise<SystemPromptTemplateVersion[]>
  transitionSystemPromptTemplateVersion: (
    id: string,
    version: number,
    to: VersionStatus,
  ) => Promise<SystemPromptTemplateVersion>
  // Track A — Versionierung-Core: Restore (non-destruktiv → neue Draft),
  // Diff (gegen 'active' oder eine Versions-Nummer) und Provenance
  // (status_history-Kette einer Version, "warum aktiv").
  restorePersonaVersion: (id: string, version: number) => Promise<Persona>
  diffPersonaVersion: (id: string, version: number, against?: string) => Promise<VersionDiff>
  provenancePersonaVersion: (id: string, version: number) => Promise<ProvenanceEntry[]>
  restorePlaybookVersion: (id: string, version: number) => Promise<Playbook>
  diffPlaybookVersion: (id: string, version: number, against?: string) => Promise<VersionDiff>
  provenancePlaybookVersion: (id: string, version: number) => Promise<ProvenanceEntry[]>
  restoreResourceVersion: (id: string, version: number) => Promise<Resource>
  diffResourceVersion: (id: string, version: number, against?: string) => Promise<VersionDiff>
  provenanceResourceVersion: (id: string, version: number) => Promise<ProvenanceEntry[]>
  restoreSystemPromptTemplateVersion: (
    id: string,
    version: number,
  ) => Promise<SystemPromptTemplate>
  diffSystemPromptTemplateVersion: (
    id: string,
    version: number,
    against?: string,
  ) => Promise<VersionDiff>
  provenanceSystemPromptTemplateVersion: (
    id: string,
    version: number,
  ) => Promise<ProvenanceEntry[]>
  listAgents: () => Promise<Agent[]>
  getAgent: (id: string) => Promise<Agent>
  createAgent: (input: AgentInput) => Promise<Agent>
  updateAgent: (id: string, input: AgentUpdateInput) => Promise<Agent>
  deleteAgent: (id: string) => Promise<void>
  renderAgentPrompt: (
    id: string,
    format?: AgentRenderFormat,
  ) => Promise<AgentRenderResult>
  // Pill-Preview-Overlay: loest eine einzelne Editor-Pill zu ihrem Output auf.
  previewPlaceholder: (input: PlaceholderPreviewInput) => Promise<PlaceholderPreview>
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
    patchPersonaDraft: (id, input) =>
      request<Persona>(token, `${ws}/personas/${id}/draft`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    patchPlaybookDraft: (id, input) =>
      request<Playbook>(token, `${ws}/playbooks/${id}/draft`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    patchResourceDraft: (id, input) =>
      request<Resource>(token, `${ws}/resources/${id}/draft`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    listPersonaVersions: (id) =>
      request<PersonaVersion[]>(token, `${ws}/personas/${id}/versions`),
    listPersonaTags: () => request<string[]>(token, `${ws}/personas/tags`),
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
    getPlaybookUsages: (id) =>
      request<PlaybookUsage[]>(token, `${ws}/playbooks/${id}/usages`),
    getResourceUsages: (id) =>
      request<ResourceUsage[]>(token, `${ws}/resources/${id}/usages`),
    listPlaybookComposes: (id) =>
      request<Playbook[]>(token, `${ws}/playbooks/${id}/composes`),
    setPlaybookComposes: (id, childIds) =>
      request<Playbook[]>(token, `${ws}/playbooks/${id}/composes`, {
        method: 'PUT',
        body: JSON.stringify({ child_ids: childIds }),
      }),
    listPlaybookComposedBy: (id) =>
      request<PlaybookRef[]>(token, `${ws}/playbooks/${id}/composed_by`),
    listResourceTags: () => request<string[]>(token, `${ws}/resources/tags`),
    listResourcesByTag: (tag) => {
      const params = new URLSearchParams({ tag })
      return request<Resource[]>(token, `${ws}/resources?${params.toString()}`)
    },
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
    listSystemPromptTemplates: () =>
      request<SystemPromptTemplate[]>(token, `${ws}/system-prompts`),
    getSystemPromptTemplate: (id) =>
      request<SystemPromptTemplate>(token, `${ws}/system-prompts/${id}`),
    createSystemPromptTemplate: (input) =>
      request<SystemPromptTemplate>(token, `${ws}/system-prompts`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updateSystemPromptTemplate: (id, input) =>
      request<SystemPromptTemplate>(token, `${ws}/system-prompts/${id}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    listSystemPromptTemplateVersions: (id) =>
      request<SystemPromptTemplateVersion[]>(
        token,
        `${ws}/system-prompts/${id}/versions`,
      ),
    transitionSystemPromptTemplateVersion: (id, version, to) =>
      request<SystemPromptTemplateVersion>(
        token,
        `${ws}/system-prompts/${id}/versions/${version}/transition`,
        { method: 'POST', body: JSON.stringify({ to }) },
      ),
    restorePersonaVersion: (id, version) =>
      request<Persona>(token, `${ws}/personas/${id}/versions/${version}/restore`, {
        method: 'POST',
      }),
    diffPersonaVersion: (id, version, against = 'active') =>
      request<VersionDiff>(
        token,
        `${ws}/personas/${id}/versions/${version}/diff?against=${encodeURIComponent(against)}`,
      ),
    provenancePersonaVersion: (id, version) =>
      request<ProvenanceEntry[]>(
        token,
        `${ws}/personas/${id}/versions/${version}/provenance`,
      ),
    restorePlaybookVersion: (id, version) =>
      request<Playbook>(token, `${ws}/playbooks/${id}/versions/${version}/restore`, {
        method: 'POST',
      }),
    diffPlaybookVersion: (id, version, against = 'active') =>
      request<VersionDiff>(
        token,
        `${ws}/playbooks/${id}/versions/${version}/diff?against=${encodeURIComponent(against)}`,
      ),
    provenancePlaybookVersion: (id, version) =>
      request<ProvenanceEntry[]>(
        token,
        `${ws}/playbooks/${id}/versions/${version}/provenance`,
      ),
    restoreResourceVersion: (id, version) =>
      request<Resource>(token, `${ws}/resources/${id}/versions/${version}/restore`, {
        method: 'POST',
      }),
    diffResourceVersion: (id, version, against = 'active') =>
      request<VersionDiff>(
        token,
        `${ws}/resources/${id}/versions/${version}/diff?against=${encodeURIComponent(against)}`,
      ),
    provenanceResourceVersion: (id, version) =>
      request<ProvenanceEntry[]>(
        token,
        `${ws}/resources/${id}/versions/${version}/provenance`,
      ),
    restoreSystemPromptTemplateVersion: (id, version) =>
      request<SystemPromptTemplate>(
        token,
        `${ws}/system-prompts/${id}/versions/${version}/restore`,
        { method: 'POST' },
      ),
    diffSystemPromptTemplateVersion: (id, version, against = 'active') =>
      request<VersionDiff>(
        token,
        `${ws}/system-prompts/${id}/versions/${version}/diff` +
          `?against=${encodeURIComponent(against)}`,
      ),
    provenanceSystemPromptTemplateVersion: (id, version) =>
      request<ProvenanceEntry[]>(
        token,
        `${ws}/system-prompts/${id}/versions/${version}/provenance`,
      ),
    listAgents: () => request<Agent[]>(token, `${ws}/agents`),
    getAgent: (id) => request<Agent>(token, `${ws}/agents/${id}`),
    createAgent: (input) =>
      request<Agent>(token, `${ws}/agents`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updateAgent: (id, input) =>
      request<Agent>(token, `${ws}/agents/${id}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    deleteAgent: (id) =>
      request<void>(token, `${ws}/agents/${id}`, { method: 'DELETE' }),
    renderAgentPrompt: (id, format) => {
      const query = format !== undefined ? `?format=${format}` : ''
      return request<AgentRenderResult>(
        token,
        `${ws}/agents/${id}/render${query}`,
      )
    },
    previewPlaceholder: (input) => {
      const params = new URLSearchParams({ kind: input.kind, target_id: input.target_id })
      if (input.persona_id !== undefined) params.set('persona_id', input.persona_id)
      return request<PlaceholderPreview>(token, `${ws}/placeholders/preview?${params.toString()}`)
    },
  }
}
