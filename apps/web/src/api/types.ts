// TypeScript-Spiegel der Pydantic-Modelle aus packages/models. Handgepflegt —
// es gibt bewusst keinen Cross-Language-Typgenerator.

export interface PersonaContent {
  description: string
  system_prompt: string
  traits: string[]
}

export interface Persona {
  id: string
  owner_id: string
  name: string
  current_version: number
  content: PersonaContent
  created_at: string
  updated_at: string
}

export interface PersonaVersion {
  version: number
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
  owner_id: string
  name: string
  current_version: number
  type: string
  tags: string[]
  triggers: string | null
  content: PlaybookContent
  created_at: string
  updated_at: string
}

export interface PlaybookVersion {
  version: number
  content: PlaybookContent
  created_by: string
  created_at: string
}

export interface PlaybookInput {
  name: string
  content: PlaybookContent
}
