import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { useForm, type UseFormReturn } from 'react-hook-form'
import { z } from 'zod'

import type { Persona, PersonaInput, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import {
  useAutoSaveDraft,
  type UseAutoSaveDraftResult,
} from '@/hooks/useAutoSaveDraft'

// Phase 3 Runde 3 Track 3: `systemPrompt` ist deprecated — der Agent-Template
// uebernimmt den System-Prompt. Schema haelt das Feld nicht mehr; beim Auto-
// Save schicken wir `system_prompt: ''` ans Backend, damit der Pydantic-
// Default greift.
const editorSchema = z.object({
  name: z.string().min(1, 'Name erforderlich.'),
  description: z.string().min(1, 'Beschreibung erforderlich.'),
  profileBlocks: z.array(z.custom<ResourceBlock>()),
  tags: z.array(z.string()),
})

export type PersonaEditorValues = z.infer<typeof editorSchema>

export interface UsePersonaFormResult {
  form: UseFormReturn<PersonaEditorValues>
  autoSave: UseAutoSaveDraftResult
}

function toInput(values: PersonaEditorValues): PersonaInput {
  return {
    name: values.name,
    content: {
      description: values.description,
      // Track 3: System-Prompt lebt jetzt im Agent-Template; wir loeschen
      // bestehende Werte nicht aktiv, sondern senden den Default ''.
      system_prompt: '',
      // `traits` ist deprecated (Phase 3-0). Wir senden weiterhin ein
      // leeres Array, damit der Schema-Default beim Backend greift.
      traits: [],
      tags: values.tags,
      content: { description: '', blocks: values.profileBlocks },
    },
  }
}

/**
 * Editor-Form fuer Persona-Auto-Save. Wartet bis `persona` geladen ist,
 * resettet dann die Defaults und uebergibt die Werte an `useAutoSaveDraft`,
 * der mit 1500 ms Debounce in den Draft schreibt.
 */
export function usePersonaForm(persona: Persona | null): UsePersonaFormResult {
  const api = useApi()
  const form = useForm<PersonaEditorValues>({
    resolver: zodResolver(editorSchema),
    defaultValues: {
      name: '',
      description: '',
      profileBlocks: [],
      tags: [],
    },
  })

  // `formReady` flippt erst, NACHDEM `form.reset(persona)` durchgelaufen ist.
  // Sonst sieht der Auto-Save-Hook den Default-Snapshot (leerer Name etc.) als
  // "Anker" und schiesst beim ersten Re-Render mit den persona-Werten einen
  // ungewollten PATCH ab — siehe Test-Flake in PR #74.
  const [formReady, setFormReady] = useState(false)
  useEffect(() => {
    if (persona !== null) {
      form.reset({
        name: persona.name,
        description: persona.content.description,
        profileBlocks: persona.content.content?.blocks ?? [],
        tags: persona.content.tags ?? [],
      })
      setFormReady(true)
    }
  }, [persona, form])

  const values = form.watch()
  const autoSave = useAutoSaveDraft<PersonaEditorValues>({
    values,
    isReady: persona !== null && formReady,
    patchFn: async (next) => {
      if (persona === null) {
        return
      }
      await api.patchPersonaDraft(persona.id, toInput(next))
    },
  })

  return { form, autoSave }
}
