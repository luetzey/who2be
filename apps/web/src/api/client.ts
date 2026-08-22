import i18n, { DEFAULT_LOCALE } from '@/i18n'

import { config } from '../config'
import type {
  AccountDeletion,
  Agent,
  AgentCopyInput,
  AgentFeedback,
  AgentInput,
  AgentRenderFormat,
  AgentRenderResult,
  AgentUpdateInput,
  ArtifactExportFormat,
  ArtifactMarkdown,
  CheckoutInput,
  CheckoutResult,
  DashboardData,
  EntitlementInfo,
  EdgeType,
  EntityExport,
  EntityExportFormat,
  ExternalTool,
  ExternalToolInput,
  ExternalToolVersion,
  FeedbackDetail,
  FeedbackEvents,
  FeedbackInput,
  FeedbackItems,
  FeedbackOverview,
  FeedbackResolutionInput,
  FeedbackSummary,
  FeedbackTarget,
  FeedbackUnused,
  GdprExport,
  Invitation,
  InvitationAcceptResult,
  InvitationInput,
  KbNeighbor,
  KbNode,
  KbSearchHit,
  Me,
  Member,
  MemberUpdateInput,
  MemoryGuardConfig,
  MemoryRead,
  MemoryStatus,
  MemoryTriageInput,
  MemoryUpdateInput,
  Organization,
  OrganizationDeletion,
  OrganizationInput,
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
  ResourceRef,
  ResourceUsage,
  ResourceVersion,
  SubResource,
  SubResourceLinkInput,
  SystemFeedbackInput,
  SystemPromptTemplate,
  SystemPromptTemplateInput,
  SystemPromptTemplateVersion,
  TableDescription,
  TableExportFormat,
  TableQueryInput,
  TableQueryResult,
  Token,
  TokenCreated,
  TokenInput,
  TokenRenameInput,
  VersionDiff,
  VersionStatus,
  WaArtifact,
  WaTable,
  WorkArea,
  WorkAreaCreateInput,
  WorkAreaGrant,
  WorkAreaGrantInput,
  WorkAreaSearchHit,
  Workspace,
  WorkspaceInput,
  WorkspaceRenameInput,
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
    // Locale-Plumbing (D2-Koordination): die aktive UI-Sprache geht als
    // `Accept-Language` mit, damit das Backend sprachabhaengigen Content in
    // der passenden Sprache liefern kann. Aufrufer koennen den Header via
    // `init.headers` ueberschreiben.
    'Accept-Language': i18n.resolvedLanguage ?? i18n.language ?? DEFAULT_LOCALE,
    ...(init?.headers as Record<string, string> | undefined),
  }
  // Kein leerer Bearer-Header, wenn (noch) kein Token vorliegt.
  if (token !== '') {
    headers.Authorization = `Bearer ${token}`
  }
  let response: Response
  const url = `${config.apiBaseUrl}${path}`
  try {
    response = await fetch(url, { ...init, headers })
  } catch (cause) {
    // `fetch` rejectet nur bei Netzwerk-/CORS-/DNS-Fehlern (nicht bei
    // HTTP-Fehlerstatus). Die User-Message bleibt generisch, aber die echte
    // Ursache (API laeuft nicht, falsche `VITE_API_BASE_URL`, CORS) wird
    // geloggt — sonst ist „nicht erreichbar" im DevTools-Log nicht
    // diagnostizierbar.
    console.error(`Who2Be-API nicht erreichbar: ${init?.method ?? 'GET'} ${url}`, cause)
    throw new ApiError(0, i18n.t('common:errors.apiUnreachable'))
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

// Wie `request`, gibt aber den Roh-Body als Text zurueck (z. B. Markdown-Export
// mit `media_type=text/markdown` — kein JSON). Fehler-Handling identisch.
async function requestText(
  token: string,
  path: string,
  init?: RequestInit,
): Promise<string> {
  const headers: Record<string, string> = {
    'Accept-Language': i18n.resolvedLanguage ?? i18n.language ?? DEFAULT_LOCALE,
    ...(init?.headers as Record<string, string> | undefined),
  }
  if (token !== '') {
    headers.Authorization = `Bearer ${token}`
  }
  let response: Response
  const url = `${config.apiBaseUrl}${path}`
  try {
    response = await fetch(url, { ...init, headers })
  } catch (cause) {
    console.error(`Who2Be-API nicht erreichbar: ${init?.method ?? 'GET'} ${url}`, cause)
    throw new ApiError(0, i18n.t('common:errors.apiUnreachable'))
  }
  if (!response.ok) {
    const { message, body } = await readErrorBody(response)
    throw new ApiError(response.status, message, body)
  }
  return response.text()
}

// Wie `request`, gibt aber den Roh-Body als Blob zurueck — fuer Downloads,
// deren Format Binaerdaten sein kann (XLSX-Tabellen-Export). Aus
// Einheitlichkeit gilt derselbe Helper auch fuer die reinen Text-Exporte
// (CSV/Markdown/HTML): der Aufrufer (`downloadFile`) braucht nur einen Blob,
// egal ob binaer oder Text. Fehler-Handling identisch zu `request`.
async function requestBlob(token: string, path: string, init?: RequestInit): Promise<Blob> {
  const headers: Record<string, string> = {
    'Accept-Language': i18n.resolvedLanguage ?? i18n.language ?? DEFAULT_LOCALE,
    ...(init?.headers as Record<string, string> | undefined),
  }
  if (token !== '') {
    headers.Authorization = `Bearer ${token}`
  }
  let response: Response
  const url = `${config.apiBaseUrl}${path}`
  try {
    response = await fetch(url, { ...init, headers })
  } catch (cause) {
    console.error(`Who2Be-API nicht erreichbar: ${init?.method ?? 'GET'} ${url}`, cause)
    throw new ApiError(0, i18n.t('common:errors.apiUnreachable'))
  }
  if (!response.ok) {
    const { message, body } = await readErrorBody(response)
    throw new ApiError(response.status, message, body)
  }
  return response.blob()
}

// Einzel-Element-Export (Plan 2026-06-05). `json` liefert ein geparstes Objekt,
// `markdown` den Roh-Text. Der Aufrufer laedt beides als Datei herunter.
async function exportEntity(
  token: string,
  ws: string,
  entity: 'personas' | 'playbooks' | 'resources' | 'external_tools',
  id: string,
  format: EntityExportFormat,
): Promise<EntityExport | string> {
  const path = `${ws}/${entity}/${id}/export?format=${format}`
  if (format === 'markdown') {
    return requestText(token, path)
  }
  return request<EntityExport>(token, path)
}

async function readErrorBody(
  response: Response,
): Promise<{ message: string; body: unknown }> {
  const fallback = i18n.t('common:errors.apiError', { status: response.status })
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

// OAuth-Remote-MCP-Consent (ADR-0034-Folge): die eingeloggte Web-Session
// autorisiert einen LLM-Client fuer GENAU einen Agenten. Nicht workspace-scoped
// im Pfad — der signierte `request`-Blob traegt den Kontext, der Server leitet
// den Workspace aus `agent_id` ab. Response = Redirect-URL zurueck zum Client.
export interface OAuthConsentInput {
  request: string
  agent_id: string
  approve: boolean
}

export interface OAuthConsentResult {
  redirect: string
}

export function oauthConsent(
  token: string,
  input: OAuthConsentInput,
): Promise<OAuthConsentResult> {
  return request<OAuthConsentResult>(token, '/oauth/consent', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export interface Api {
  // `agent` filtert serverseitig auf die Persona des Agenten (WP-B).
  // `locale` filtert serverseitig auf die Element-Sprache (ADR-0045).
  listPersonas: (filters?: { agent?: string; locale?: string }) => Promise<Persona[]>
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
  // `agent` filtert serverseitig auf die dem Agenten zugewiesenen Playbooks
  // inkl. Composite-Closure (WP-B).
  listPlaybooks: (
    filters?: { tag?: string; trigger?: string; agent?: string; locale?: string },
  ) => Promise<Playbook[]>
  getPlaybook: (id: string) => Promise<Playbook>
  createPlaybook: (input: PlaybookInput) => Promise<Playbook>
  updatePlaybook: (id: string, input: PlaybookInput) => Promise<Playbook>
  listPlaybookVersions: (id: string) => Promise<PlaybookVersion[]>
  // Phase 3-B — DISTINCT-Tag-Vorschlag fuer den `TagInput`. Backend
  // liefert das Endpoint mit Track A; bis dahin antwortet es 404 — der
  // TagInput-Konsument faengt das als leeres Vorschlag-Set ab.
  listPlaybookTags: () => Promise<string[]>
  listTokens: (filters?: { agentId?: string }) => Promise<Token[]>
  createToken: (input: TokenInput) => Promise<TokenCreated>
  renameToken: (id: string, input: TokenRenameInput) => Promise<Token>
  rotateToken: (id: string) => Promise<TokenCreated>
  revokeToken: (id: string) => Promise<void>
  getDashboard: (page?: number) => Promise<DashboardData>
  getFeedback: (type: FeedbackTarget, id: string) => Promise<FeedbackSummary>
  getFeedbackEvents: (type: FeedbackTarget, id: string) => Promise<FeedbackEvents>
  getFeedbackOverview: () => Promise<FeedbackOverview>
  getFeedbackItems: () => Promise<FeedbackItems>
  // Detailsicht auf ein einzelnes Feedback (Absender + Triage-Historie).
  getFeedbackDetail: (feedbackId: string) => Promise<FeedbackDetail>
  getFeedbackUnused: () => Promise<FeedbackUnused>
  setFeedbackResolution: (
    feedbackId: string,
    input: FeedbackResolutionInput,
  ) => Promise<AgentFeedback>
  // Hard-Delete eines Feedback-Eintrags (editor+); 204 bei Erfolg, 404 fremd.
  deleteFeedback: (feedbackId: string) => Promise<void>
  // Inhalts-Feedback zu einem Element einreichen (editor+); 201 ohne Body-Nutzung.
  submitFeedback: (input: FeedbackInput) => Promise<void>
  // Zielloses System-/MCP-Problem melden (jede Rolle; feedback_write-No-Op).
  submitSystemFeedback: (input: SystemFeedbackInput) => Promise<void>
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
  // `agent` filtert serverseitig auf die aus den zugewiesenen Playbooks
  // erreichbaren Resources inkl. Sub-Resource-Closure (WP-B).
  listResources: (filters?: { agent?: string; locale?: string }) => Promise<Resource[]>
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
  // Einzel-Element-Hard-Delete (Plan 2026-06-05, Muster `deleteAgent`).
  // 204 bei Erfolg; 409 (referenziert) traegt die Verwender im ApiError.body;
  // 404 bei unbekannter ID.
  deletePersona: (id: string) => Promise<void>
  deletePlaybook: (id: string) => Promise<void>
  deleteResource: (id: string) => Promise<void>
  // Einzel-Element-Export (Plan 2026-06-05). `json` liefert ein Objekt,
  // `markdown` den Roh-Text — Aufrufer laedt beides als Datei herunter.
  exportPersona: (id: string, format: EntityExportFormat) => Promise<EntityExport | string>
  exportPlaybook: (id: string, format: EntityExportFormat) => Promise<EntityExport | string>
  exportResource: (id: string, format: EntityExportFormat) => Promise<EntityExport | string>
  // Track E — Sub-Resource-Composition.
  listResourceSubResources: (id: string) => Promise<SubResource[]>
  setResourceSubResources: (
    id: string,
    links: SubResourceLinkInput[],
  ) => Promise<SubResource[]>
  listResourceUsedBy: (id: string) => Promise<ResourceRef[]>
  // WP-4 (Blueprint 2026-07-18 external-tools-tool-ref): externe MCP-Server/
  // Tool-Bindings. Kein `duplicate`, `diff` oder `tags`-Endpoint — die
  // Backend-Surface (WP-1) traegt sie nicht (siehe
  // `apps/api/tests/contract/openapi_surface.json`).
  listExternalTools: (filters?: { locale?: string }) => Promise<ExternalTool[]>
  getExternalTool: (id: string) => Promise<ExternalTool>
  createExternalTool: (input: ExternalToolInput) => Promise<ExternalTool>
  updateExternalTool: (id: string, input: ExternalToolInput) => Promise<ExternalTool>
  patchExternalToolDraft: (id: string, input: ExternalToolInput) => Promise<ExternalTool>
  listExternalToolVersions: (id: string) => Promise<ExternalToolVersion[]>
  transitionExternalToolVersion: (
    id: string,
    version: number,
    to: VersionStatus,
  ) => Promise<ExternalToolVersion>
  restoreExternalToolVersion: (id: string, version: number) => Promise<ExternalTool>
  provenanceExternalToolVersion: (id: string, version: number) => Promise<ProvenanceEntry[]>
  deleteExternalTool: (id: string) => Promise<void>
  exportExternalTool: (id: string, format: EntityExportFormat) => Promise<EntityExport | string>
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
  // Track C — Tenancy-Management. NICHT workspace-scoped: Org-Routen tragen die
  // org_id im Pfad, Workspace-Mutationen die jeweilige workspace_id (kann vom
  // aktuell aktiven Workspace abweichen, z. B. beim Löschen eines anderen).
  createOrganization: (input: OrganizationInput) => Promise<Organization>
  listOrgWorkspaces: (orgId: string) => Promise<Workspace[]>
  createWorkspace: (orgId: string, input: WorkspaceInput) => Promise<Workspace>
  renameWorkspace: (workspaceId: string, input: WorkspaceRenameInput) => Promise<Workspace>
  deleteWorkspace: (workspaceId: string) => Promise<void>
  // Track O — Account-/Org-Lifecycle (Soft-Delete, 30-Tage-Grace) + GDPR-Export.
  // Bewusst NICHT workspace-scoped: Konto-/Export-Routen haengen an `/v1/me`
  // bzw. `/v1/gdpr`, die Org-Loeschung traegt die org_id im Pfad.
  deleteAccount: () => Promise<AccountDeletion>
  deleteOrganization: (orgId: string) => Promise<OrganizationDeletion>
  exportMyData: () => Promise<GdprExport>
  // Phase 3 Runde 3 Track 3 — SystemPromptTemplate + Agent.
  listSystemPromptTemplates: (filters?: { locale?: string }) => Promise<SystemPromptTemplate[]>
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
  copyAgent: (id: string, input?: AgentCopyInput) => Promise<Agent>
  // ADR-0044 — Agent-Memory (Mensch-Pfad, editor+ gated). `status` filtert
  // serverseitig; ohne Filter kommen alle Status (Triage-UI braucht pending +
  // active + rejected gleichzeitig).
  listAgentMemories: (agentId: string, status?: MemoryStatus) => Promise<MemoryRead[]>
  // Triage eines pending-Vorschlags: approve (opt. Fakt-Edition) oder reject
  // (opt. Notiz). 409, wenn der Eintrag nicht mehr pending ist.
  triageAgentMemory: (
    agentId: string,
    memoryId: string,
    input: MemoryTriageInput,
  ) => Promise<MemoryRead>
  updateAgentMemory: (
    agentId: string,
    memoryId: string,
    input: MemoryUpdateInput,
  ) => Promise<MemoryRead>
  deleteAgentMemory: (agentId: string, memoryId: string) => Promise<void>
  deleteAllAgentMemories: (agentId: string) => Promise<void>
  // ADR-0044-Addendum — Workspace-Injection-Filter-Konfiguration. Admin-only
  // (editor/viewer + Agent-Tokens 403 serverseitig).
  getMemoryGuard: () => Promise<MemoryGuardConfig>
  updateMemoryGuard: (config: MemoryGuardConfig) => Promise<MemoryGuardConfig>
  // Duplizieren (Deep-Copy des Inhalts als frische Draft, Muster `copyAgent`).
  // Der Server leitet Namen ("<Name> (Kopie)") + frischen Slug selbst ab.
  duplicatePersona: (id: string) => Promise<Persona>
  duplicateResource: (id: string) => Promise<Resource>
  duplicateSystemPrompt: (id: string) => Promise<SystemPromptTemplate>
  renderAgentPrompt: (
    id: string,
    format?: AgentRenderFormat,
  ) => Promise<AgentRenderResult>
  // Pill-Preview-Overlay: loest eine einzelne Editor-Pill zu ihrem Output auf.
  previewPlaceholder: (input: PlaceholderPreviewInput) => Promise<PlaceholderPreview>
  // ADR-0047 — Agenten-Arbeitsbereich (Lese-Ansicht + Grant-Verwaltung).
  // Alle Routen sind fuer Menschen (JWT) offen; `require_agent_bound_token`
  // greift nur bei `w2b_`-Tokens. Sichtbarkeit serverseitig: editor+ sehen
  // auch fremde private Areas, viewer nur `scope='shared'`.
  listWorkAreas: () => Promise<WorkArea[]>
  createWorkArea: (input: WorkAreaCreateInput) => Promise<WorkArea>
  // Grants gibt es nur auf SHARED Areas (private Area => 403 `area_forbidden`);
  // die Vergabe ist Menschen vorbehalten.
  listWorkAreaGrants: (areaId: string) => Promise<WorkAreaGrant[]>
  setWorkAreaGrant: (
    areaId: string,
    agentId: string,
    input: WorkAreaGrantInput,
  ) => Promise<WorkAreaGrant>
  deleteWorkAreaGrant: (areaId: string, agentId: string) => Promise<void>
  // Metadaten-Liste einer Area; der Inhalt kommt getrennt ueber
  // `readWaArtifact` (Markdown mit `[#block_id]`-Ankern).
  listWaArtifacts: (areaId: string) => Promise<WaArtifact[]>
  readWaArtifact: (artifactId: string, anchor?: string) => Promise<ArtifactMarkdown>
  deleteWaArtifact: (artifactId: string) => Promise<void>
  // Export eines einzelnen Artifacts als Datei-Download (naechste
  // Backend-Welle — Endpoint existiert im OpenAPI-Golden noch nicht).
  exportWaArtifact: (artifactId: string, format: ArtifactExportFormat) => Promise<Blob>
  // Tabellen-Store (ADR-0049): Katalog-Liste je Area, Beschreibung mit
  // Spalten-Statistik, read-only SQL-Query und Datei-Export.
  listWaTables: (areaId: string) => Promise<WaTable[]>
  describeWaTable: (tableId: string) => Promise<TableDescription>
  queryWaTable: (tableId: string, input: TableQueryInput) => Promise<TableQueryResult>
  // Export einer Tabelle als Datei-Download (naechste Backend-Welle —
  // Endpoint existiert im OpenAPI-Golden noch nicht).
  exportWaTable: (tableId: string, format: TableExportFormat) => Promise<Blob>
  // Passagen-Suche: liefert Anker + Snippet, nie ganze Dokumente. Ausserhalb
  // des Lese-Scopes ist das Ergebnis leer (kein Existenz-Orakel).
  searchWorkArea: (filters: {
    q: string
    area_id?: string
    limit?: number
  }) => Promise<WorkAreaSearchHit[]>
  // Getrennter Index — findet per Konstruktion nie WorkArea-Rohmaterial.
  searchKb: (filters: { q: string; limit?: number }) => Promise<KbSearchHit[]>
  getKbNode: (nodeId: string) => Promise<KbNode>
  kbNeighbors: (filters: {
    anchor: string
    type?: EdgeType
    depth?: number
  }) => Promise<KbNeighbor[]>
  // Track D: aufgeloestes Org-Entitlement + MCP-Verbrauch (Billing-Slot).
  getEntitlement: () => Promise<EntitlementInfo>
  // Track J: startet einen Mollie-Checkout und liefert die Hosted-Checkout-URL.
  createCheckout: (input: CheckoutInput) => Promise<CheckoutResult>
}

export function createApi(token: string, workspaceId: string): Api {
  const ws = `/v1/workspaces/${workspaceId}`
  return {
    listPersonas: (filters) => {
      const params = new URLSearchParams()
      if (filters?.agent) params.set('agent', filters.agent)
      if (filters?.locale) params.set('locale', filters.locale)
      const query = params.toString()
      return request<Persona[]>(token, `${ws}/personas${query ? `?${query}` : ''}`)
    },
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
      if (filters?.agent) params.set('agent', filters.agent)
      if (filters?.locale) params.set('locale', filters.locale)
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
    listTokens: (filters) =>
      request<Token[]>(
        token,
        `${ws}/tokens${filters?.agentId !== undefined ? `?agent_id=${filters.agentId}` : ''}`,
      ),
    createToken: (input) =>
      request<TokenCreated>(token, `${ws}/tokens`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    renameToken: (id, input) =>
      request<Token>(token, `${ws}/tokens/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    rotateToken: (id) =>
      request<TokenCreated>(token, `${ws}/tokens/${id}/rotate`, { method: 'POST' }),
    revokeToken: (id) =>
      request<void>(token, `${ws}/tokens/${id}`, { method: 'DELETE' }),
    getDashboard: (page) =>
      request<DashboardData>(
        token,
        `${ws}/dashboard${page && page > 1 ? `?page=${page}` : ''}`,
      ),
    getFeedback: (type, id) =>
      request<FeedbackSummary>(token, `${ws}/feedback/${type}/${id}`),
    getFeedbackEvents: (type, id) =>
      request<FeedbackEvents>(token, `${ws}/feedback/${type}/${id}/events`),
    getFeedbackOverview: () =>
      request<FeedbackOverview>(token, `${ws}/feedback-overview`),
    getFeedbackItems: () =>
      request<FeedbackItems>(token, `${ws}/feedback-items`),
    getFeedbackDetail: (feedbackId) =>
      request<FeedbackDetail>(token, `${ws}/feedback/${feedbackId}`),
    getFeedbackUnused: () =>
      request<FeedbackUnused>(token, `${ws}/feedback-unused`),
    setFeedbackResolution: (feedbackId, input) =>
      request<AgentFeedback>(token, `${ws}/feedback/${feedbackId}/resolution`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    deleteFeedback: (feedbackId) =>
      request<void>(token, `${ws}/feedback/${feedbackId}`, { method: 'DELETE' }),
    submitFeedback: (input) =>
      request<void>(token, `${ws}/feedback`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    submitSystemFeedback: (input) =>
      request<void>(token, `${ws}/system-feedback`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
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
    listResources: (filters) => {
      const params = new URLSearchParams()
      if (filters?.agent) params.set('agent', filters.agent)
      if (filters?.locale) params.set('locale', filters.locale)
      const query = params.toString()
      return request<Resource[]>(token, `${ws}/resources${query ? `?${query}` : ''}`)
    },
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
    deletePersona: (id) =>
      request<void>(token, `${ws}/personas/${id}`, { method: 'DELETE' }),
    deletePlaybook: (id) =>
      request<void>(token, `${ws}/playbooks/${id}`, { method: 'DELETE' }),
    deleteResource: (id) =>
      request<void>(token, `${ws}/resources/${id}`, { method: 'DELETE' }),
    exportPersona: (id, format) => exportEntity(token, ws, 'personas', id, format),
    exportPlaybook: (id, format) => exportEntity(token, ws, 'playbooks', id, format),
    exportResource: (id, format) => exportEntity(token, ws, 'resources', id, format),
    listResourceSubResources: (id) =>
      request<SubResource[]>(token, `${ws}/resources/${id}/sub_resources`),
    setResourceSubResources: (id, links) =>
      request<SubResource[]>(token, `${ws}/resources/${id}/sub_resources`, {
        method: 'PUT',
        body: JSON.stringify({ links }),
      }),
    listResourceUsedBy: (id) =>
      request<ResourceRef[]>(token, `${ws}/resources/${id}/used_by`),
    listExternalTools: (filters) => {
      const params = new URLSearchParams()
      if (filters?.locale) params.set('locale', filters.locale)
      const query = params.toString()
      return request<ExternalTool[]>(token, `${ws}/external_tools${query ? `?${query}` : ''}`)
    },
    getExternalTool: (id) => request<ExternalTool>(token, `${ws}/external_tools/${id}`),
    createExternalTool: (input) =>
      request<ExternalTool>(token, `${ws}/external_tools`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updateExternalTool: (id, input) =>
      request<ExternalTool>(token, `${ws}/external_tools/${id}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    patchExternalToolDraft: (id, input) =>
      request<ExternalTool>(token, `${ws}/external_tools/${id}/draft`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    listExternalToolVersions: (id) =>
      request<ExternalToolVersion[]>(token, `${ws}/external_tools/${id}/versions`),
    transitionExternalToolVersion: (id, version, to) =>
      request<ExternalToolVersion>(
        token,
        `${ws}/external_tools/${id}/versions/${version}/transition`,
        { method: 'POST', body: JSON.stringify({ to }) },
      ),
    restoreExternalToolVersion: (id, version) =>
      request<ExternalTool>(token, `${ws}/external_tools/${id}/versions/${version}/restore`, {
        method: 'POST',
      }),
    provenanceExternalToolVersion: (id, version) =>
      request<ProvenanceEntry[]>(
        token,
        `${ws}/external_tools/${id}/versions/${version}/provenance`,
      ),
    deleteExternalTool: (id) =>
      request<void>(token, `${ws}/external_tools/${id}`, { method: 'DELETE' }),
    exportExternalTool: (id, format) => exportEntity(token, ws, 'external_tools', id, format),
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
    createOrganization: (input) =>
      request<Organization>(token, `/v1/organizations`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    listOrgWorkspaces: (orgId) =>
      request<Workspace[]>(token, `/v1/organizations/${orgId}/workspaces`),
    createWorkspace: (orgId, input) =>
      request<Workspace>(token, `/v1/organizations/${orgId}/workspaces`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    renameWorkspace: (workspaceId, input) =>
      request<Workspace>(token, `/v1/workspaces/${workspaceId}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      }),
    deleteWorkspace: (workspaceId) =>
      request<void>(token, `/v1/workspaces/${workspaceId}`, { method: 'DELETE' }),
    deleteAccount: () => request<AccountDeletion>(token, `/v1/me`, { method: 'DELETE' }),
    deleteOrganization: (orgId) =>
      request<OrganizationDeletion>(token, `/v1/organizations/${orgId}`, { method: 'DELETE' }),
    exportMyData: () => request<GdprExport>(token, `/v1/gdpr/export`),
    listSystemPromptTemplates: (filters) => {
      const params = new URLSearchParams()
      if (filters?.locale) params.set('locale', filters.locale)
      const query = params.toString()
      return request<SystemPromptTemplate[]>(
        token,
        `${ws}/system-prompts${query ? `?${query}` : ''}`,
      )
    },
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
    copyAgent: (id, input) =>
      request<Agent>(token, `${ws}/agents/${id}/copy`, {
        method: 'POST',
        body: JSON.stringify(input ?? {}),
      }),
    listAgentMemories: (agentId, status) => {
      const query = status !== undefined ? `?status=${status}` : ''
      return request<MemoryRead[]>(token, `${ws}/agents/${agentId}/memories${query}`)
    },
    triageAgentMemory: (agentId, memoryId, input) =>
      request<MemoryRead>(token, `${ws}/agents/${agentId}/memories/${memoryId}/triage`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updateAgentMemory: (agentId, memoryId, input) =>
      request<MemoryRead>(token, `${ws}/agents/${agentId}/memories/${memoryId}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    deleteAgentMemory: (agentId, memoryId) =>
      request<void>(token, `${ws}/agents/${agentId}/memories/${memoryId}`, {
        method: 'DELETE',
      }),
    deleteAllAgentMemories: (agentId) =>
      request<void>(token, `${ws}/agents/${agentId}/memories`, { method: 'DELETE' }),
    getMemoryGuard: () => request<MemoryGuardConfig>(token, `${ws}/memory-guard`),
    updateMemoryGuard: (config) =>
      request<MemoryGuardConfig>(token, `${ws}/memory-guard`, {
        method: 'PUT',
        body: JSON.stringify(config),
      }),
    duplicatePersona: (id) =>
      request<Persona>(token, `${ws}/personas/${id}/duplicate`, { method: 'POST' }),
    duplicateResource: (id) =>
      request<Resource>(token, `${ws}/resources/${id}/duplicate`, { method: 'POST' }),
    duplicateSystemPrompt: (id) =>
      request<SystemPromptTemplate>(token, `${ws}/system-prompts/${id}/duplicate`, {
        method: 'POST',
      }),
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
    listWorkAreas: () => request<WorkArea[]>(token, `${ws}/work-areas`),
    createWorkArea: (input) =>
      request<WorkArea>(token, `${ws}/work-areas`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    listWorkAreaGrants: (areaId) =>
      request<WorkAreaGrant[]>(token, `${ws}/work-areas/${areaId}/grants`),
    setWorkAreaGrant: (areaId, agentId, input) =>
      request<WorkAreaGrant>(token, `${ws}/work-areas/${areaId}/grants/${agentId}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    deleteWorkAreaGrant: (areaId, agentId) =>
      request<void>(token, `${ws}/work-areas/${areaId}/grants/${agentId}`, {
        method: 'DELETE',
      }),
    listWaArtifacts: (areaId) =>
      request<WaArtifact[]>(token, `${ws}/work-areas/${areaId}/artifacts`),
    readWaArtifact: (artifactId, anchor) => {
      const params = new URLSearchParams()
      if (anchor !== undefined && anchor !== '') params.set('anchor', anchor)
      const query = params.toString()
      return request<ArtifactMarkdown>(
        token,
        `${ws}/wa-artifacts/${artifactId}${query ? `?${query}` : ''}`,
      )
    },
    deleteWaArtifact: (artifactId) =>
      request<void>(token, `${ws}/wa-artifacts/${artifactId}`, { method: 'DELETE' }),
    exportWaArtifact: (artifactId, format) =>
      requestBlob(token, `${ws}/wa-artifacts/${artifactId}/export?format=${format}`),
    listWaTables: (areaId) => request<WaTable[]>(token, `${ws}/work-areas/${areaId}/tables`),
    describeWaTable: (tableId) =>
      request<TableDescription>(token, `${ws}/wa-tables/${tableId}`),
    queryWaTable: (tableId, input) =>
      request<TableQueryResult>(token, `${ws}/wa-tables/${tableId}/query`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    exportWaTable: (tableId, format) =>
      requestBlob(token, `${ws}/wa-tables/${tableId}/export?format=${format}`),
    searchWorkArea: (filters) => {
      const params = new URLSearchParams({ q: filters.q })
      if (filters.area_id) params.set('area_id', filters.area_id)
      if (filters.limit !== undefined) params.set('limit', String(filters.limit))
      return request<WorkAreaSearchHit[]>(token, `${ws}/workarea-search?${params.toString()}`)
    },
    searchKb: (filters) => {
      const params = new URLSearchParams({ q: filters.q })
      if (filters.limit !== undefined) params.set('limit', String(filters.limit))
      return request<KbSearchHit[]>(token, `${ws}/kb-search?${params.toString()}`)
    },
    getKbNode: (nodeId) => request<KbNode>(token, `${ws}/kb/nodes/${nodeId}`),
    kbNeighbors: (filters) => {
      const params = new URLSearchParams({ anchor: filters.anchor })
      // Query-Alias ist `type` (der Python-Parameter heisst `edge_type`).
      if (filters.type !== undefined) params.set('type', filters.type)
      if (filters.depth !== undefined) params.set('depth', String(filters.depth))
      return request<KbNeighbor[]>(token, `${ws}/kb/neighbors?${params.toString()}`)
    },
    getEntitlement: () => request<EntitlementInfo>(token, `${ws}/billing/entitlement`),
    createCheckout: (input) =>
      request<CheckoutResult>(token, `${ws}/billing/checkout`, {
        method: 'POST',
        body: JSON.stringify(input),
      }),
  }
}
