import { zodResolver } from '@hookform/resolvers/zod'
import { type BaseSyntheticEvent, useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Persona, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { notify } from '@/lib/feedback'

// Pflichtfelder werden via Zod validiert; `profileBlocks` und `tags`
// kommen als reine Passthrough-Felder mit ins Schema, damit der Resolver
// die Werte nicht stripped und die Form-Typen aus `useForm` und
// `zodResolver` zusammenpassen.
const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  systemPrompt: z.string().min(1, 'System-Prompt erforderlich.'),
  profileBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
})

export type PersonaEditorValues = z.infer<typeof editorSchema>

function describeError(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'Unbekannter Fehler.'
}

export interface UsePersonaFormResult {
  form: UseFormReturn<PersonaEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

/**
 * Editor-Form fuer Persona-Update. Wartet bis `persona` geladen ist,
 * resettet dann die Defaults. Submit ruft updatePersona, zeigt Toast
 * und triggert das uebergebene `onSaved` (typisch: reload).
 */
export function usePersonaForm(
  persona: Persona | null,
  onSaved: () => void,
): UsePersonaFormResult {
  const api = useApi()
  const [saveError, setSaveError] = useState<string | null>(null)
  const form = useForm<PersonaEditorValues>({
    resolver: zodResolver(editorSchema),
    defaultValues: {
      name: '',
      description: '',
      systemPrompt: '',
      profileBlocks: [],
      tags: [],
    },
  })

  useEffect(() => {
    if (persona !== null) {
      form.reset({
        name: persona.name,
        description: persona.content.description,
        systemPrompt: persona.content.system_prompt,
        profileBlocks: persona.content.content?.blocks ?? [],
        tags: persona.content.tags ?? [],
      })
    }
  }, [persona, form])

  const onSubmit = form.handleSubmit(async (values) => {
    if (persona === null) {
      return
    }
    setSaveError(null)
    try {
      await api.updatePersona(persona.id, {
        name: values.name,
        content: {
          description: values.description,
          system_prompt: values.systemPrompt,
          // `traits` ist deprecated (Phase 3-0). Wir senden weiterhin ein
          // leeres Array, damit der Schema-Default beim Backend greift —
          // auch wenn Server jetzt selbst einen Default haetten.
          traits: [],
          tags: values.tags,
          content: { description: '', blocks: values.profileBlocks },
        },
      })
      notify.success('Gespeichert — neue Version erstellt.')
      onSaved()
    } catch (cause) {
      setSaveError(describeError(cause))
    }
  })

  return { form, onSubmit, saveError }
}
