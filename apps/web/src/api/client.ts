import { config } from '../config'
import type {
  Persona,
  PersonaInput,
  PersonaVersion,
  Playbook,
  PlaybookInput,
  PlaybookVersion,
  Token,
  TokenCreated,
  TokenInput,
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
  listTokens: () => Promise<Token[]>
  createToken: (input: TokenInput) => Promise<TokenCreated>
  revokeToken: (id: string) => Promise<void>
}

export function createApi(token: string): Api {
  return {
    listPersonas: () => request<Persona[]>(token, '/v1/personas'),
    getPersona: (id) => request<Persona>(token, `/v1/personas/${id}`),
    createPersona: (input) =>
      request<Persona>(token, '/v1/personas', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updatePersona: (id, input) =>
      request<Persona>(token, `/v1/personas/${id}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    listPersonaVersions: (id) =>
      request<PersonaVersion[]>(token, `/v1/personas/${id}/versions`),
    listPersonaPlaybooks: (id) =>
      request<Playbook[]>(token, `/v1/personas/${id}/playbooks`),
    setPersonaPlaybooks: (id, playbookIds) =>
      request<Playbook[]>(token, `/v1/personas/${id}/playbooks`, {
        method: 'PUT',
        body: JSON.stringify({ playbook_ids: playbookIds }),
      }),
    listPlaybooks: (filters) => {
      const params = new URLSearchParams()
      if (filters?.tag) params.set('tag', filters.tag)
      if (filters?.trigger) params.set('trigger', filters.trigger)
      const query = params.toString()
      return request<Playbook[]>(token, `/v1/playbooks${query ? `?${query}` : ''}`)
    },
    getPlaybook: (id) => request<Playbook>(token, `/v1/playbooks/${id}`),
    createPlaybook: (input) =>
      request<Playbook>(token, '/v1/playbooks', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    updatePlaybook: (id, input) =>
      request<Playbook>(token, `/v1/playbooks/${id}`, {
        method: 'PUT',
        body: JSON.stringify(input),
      }),
    listPlaybookVersions: (id) =>
      request<PlaybookVersion[]>(token, `/v1/playbooks/${id}/versions`),
    listTokens: () => request<Token[]>(token, '/v1/tokens'),
    createToken: (input) =>
      request<TokenCreated>(token, '/v1/tokens', {
        method: 'POST',
        body: JSON.stringify(input),
      }),
    revokeToken: (id) =>
      request<void>(token, `/v1/tokens/${id}`, { method: 'DELETE' }),
  }
}
