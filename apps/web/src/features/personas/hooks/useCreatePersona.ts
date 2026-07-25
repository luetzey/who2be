import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

// Welle 4: Create ist immer erlaubt. `name` ist die einzige clientseitige
// Pflicht (Spec: "Anlegen geht immer"). Body, Description duerfen leer sein.
// Schema spiegelt `usePersonaForm.editorSchema`, damit `PersonaEditorForm`
// mit beiden Hooks funktioniert.
// Track C5: modes hinzugefuegt.
const modeSchema = z.object({
  name: z.string(),
  trigger: z.string().nullable().optional(),
  is_default: z.boolean(),
  // PR-A: Block-Dokumente statt Plain-Strings.
  identity_add: z.array(z.custom<ResourceBlock>()),
  output_style_override: z.array(z.custom<ResourceBlock>()),
  anti_patterns: z.array(z.custom<ResourceBlock>()),
  playbook_id: z.string().nullable().optional(),
  playbook_name: z.string().optional(),
})

const skillSchema = z.object({
  name: z.string(),
  note: z.string(),
})

const createSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string(),
  profileBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
  modes: z.array(modeSchema),
  skills: z.array(skillSchema),
})

export type PersonaCreateValues = z.infer<typeof createSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UseCreatePersonaResult {
  form: UseFormReturn<PersonaCreateValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function useCreatePersona(
  onCreated: (id: string) => void,
  // Ein Element, eine Sprache (ADR-0045): einzelne Sprache statt der
  // frueheren Multi-Auswahl. `undefined` laesst das Backend auf die
  // Workspace-Content-Sprache defaulten. Wird als Page-State gehalten, damit
  // das geteilte `PersonaEditorForm`-Schema unveraendert bleibt.
  locale?: string,
): UseCreatePersonaResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<PersonaCreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: {
      name: '',
      description: '',
      profileBlocks: [],
      tags: [],
      modes: [],
      skills: [],
    },
  })

  const onSubmit = form.handleSubmit(async (values) => {
    setSaveError(null)
    try {
      const created = await api.createPersona({
        name: values.name,
        content: {
          description: values.description,
          system_prompt: '',
          traits: [],
          tags: values.tags,
          content: { description: '', blocks: values.profileBlocks },
          modes: values.modes,
          skills: values.skills,
        },
        locale,
      })
      notify.success('Persona angelegt.')
      onCreated(created.id)
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
