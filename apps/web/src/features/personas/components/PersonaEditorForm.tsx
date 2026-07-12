import { ChevronRight } from 'lucide-react'
import { type FormEvent, type ReactNode } from 'react'
import { useWatch, type Control, type UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import type { ResourceBlock } from '@/api/types'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Form } from '@/components/ui/form'
import { cn } from '@/lib/utils'

import type { PersonaEditorValues } from '../hooks/usePersonaForm'
import { PersonaModesEditor } from './PersonaModesEditor'
import { MODES_SECTION_ID, PersonaProfileFields } from './PersonaProfileFields'

interface PersonaModesDisclosureProps {
  control: Control<PersonaEditorValues>
  disabled: boolean
}

/**
 * Disclosure-Wrapper um den `PersonaModesEditor` fuer den Single-Form-Modus
 * der New-Page (kein Tab-Set). Auf der Detail-Page liegt der Modi-Editor in
 * einem eigenen „Modi"-Tab; dort wird diese Disclosure NICHT gerendert.
 *
 * Native `<details>`/`<summary>` ist a11y-konform und braucht keine eigene
 * Open/Close-State-Maschine (das macht der Browser).
 */
function PersonaModesDisclosure({ control, disabled }: PersonaModesDisclosureProps) {
  const { t } = useTranslation('personas')
  const modes = useWatch({ control, name: 'modes' })
  const hasModes = modes !== undefined && modes.length > 0
  return (
    <details id={MODES_SECTION_ID} className="group rounded-lg border bg-card" open={hasModes}>
      <summary
        className={cn(
          'flex cursor-pointer list-none items-center justify-between gap-2 rounded-lg px-4 py-3',
          'text-sm font-medium hover:bg-muted/40',
          'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
          '[&::-webkit-details-marker]:hidden',
        )}
      >
        <span className="flex items-center gap-2">
          <ChevronRight className="size-4 transition-transform group-open:rotate-90" />
          <span>{t('editor.modes.disclosure.title')}</span>
          {hasModes ? (
            <Badge variant="secondary" className="ml-1">
              {modes.length}
            </Badge>
          ) : null}
        </span>
        <span className="text-xs font-normal text-muted-foreground">
          {t('editor.modes.disclosure.subtitle')}
        </span>
      </summary>
      <div className="border-t px-4 py-4">
        <PersonaModesEditor control={control} disabled={disabled} />
      </div>
    </details>
  )
}

interface PersonaEditorFormProps {
  form: UseFormReturn<PersonaEditorValues>
  // Render-Identitaet fuer die BlockNote-Insel. Wechselt der Key, wird der
  // ProseMirror-State remountet — sonst bleibt der Editor auf dem alten
  // `initialContent` haengen (useCreateBlockNote initialisiert nur einmal).
  formKey: string
  // Initial-Snapshot direkt aus dem persona-Prop. Wir koennen NICHT
  // `field.value` als initialBlocks nutzen, weil form.reset erst im Effect
  // nach dem Mount laeuft — der frische Editor wuerde sonst den alten
  // Form-State sehen. Pattern parallel zu ResourceDetailPage.
  initialProfileBlocks: ResourceBlock[]
  /**
   * ID der bearbeiteten Persona — fuer die Pill-Vorschau im Profil-Editor
   * (Katalog-/Persona-Pills loesen sonst ohne Persona-Kontext nicht auf).
   * Fehlt auf der New-Page (Persona noch nicht gespeichert).
   */
  personaId?: string
  /**
   * Bestehender Persona-eigener System-Prompt. Mit Phase 3 Runde 3 Track 3
   * wandert der System-Prompt ins Agent-Template; die UI versteckt das Feld
   * und zeigt fuer Bestandsdaten lediglich eine Read-Only-Hinweis-Box.
   */
  legacySystemPrompt?: string
  /**
   * Optionaler onSubmit-Handler. Fehlt er, wird das Standard-preventDefault
   * genutzt (Auto-Save-Modus). Wird er angegeben, uebernimmt die Parent-Page
   * die Submit-Logik (New-Page-Modus).
   */
  onSubmit?: (e: FormEvent<HTMLFormElement>) => void
  /**
   * Optionaler Actions-Slot. Wird am Ende des <form>-Elements gerendert.
   * Typisch: Submit-Button + ErrorAlert auf der New-Page.
   */
  actions?: ReactNode
  /**
   * Vom System verwaltet (Builder): Editor read-only wie fuer Viewer. Das
   * Backend sperrt Mutationen ohnehin (403 managed_aggregate).
   */
  locked?: boolean
}

/**
 * Single-Form-Editor der New-Page: Profil-Felder + Modi-Disclosure + Actions
 * in EINEM `<form>`. Die Detail-Page nutzt diesen Wrapper NICHT — sie rendert
 * `PersonaProfileFields` im „Bearbeiten"-Tab und `PersonaModesEditor` im
 * „Modi"-Tab unter einem gemeinsamen `<Form>`-Provider (ein Save fuer beide).
 */
export function PersonaEditorForm({
  form,
  formKey,
  initialProfileBlocks,
  personaId,
  legacySystemPrompt,
  onSubmit,
  actions,
  locked = false,
}: PersonaEditorFormProps) {
  // Viewer dürfen nur lesen (ADR-0023) — Auto-Save bleibt gesperrt. `locked`
  // (vom System verwaltet) verhaelt sich identisch.
  const isViewer = useCurrentWorkspaceRole() === 'viewer' || locked
  return (
    <Card>
      <CardContent className="pt-6">
        <Form {...form}>
          <form
            className="flex flex-col gap-6"
            onSubmit={onSubmit ?? ((event) => event.preventDefault())}
          >
            <PersonaProfileFields
              form={form}
              formKey={formKey}
              initialProfileBlocks={initialProfileBlocks}
              personaId={personaId}
              legacySystemPrompt={legacySystemPrompt}
              locked={locked}
            />

            <PersonaModesDisclosure control={form.control} disabled={isViewer} />

            {actions !== undefined ? actions : null}
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
