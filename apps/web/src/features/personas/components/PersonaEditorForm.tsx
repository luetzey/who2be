import { type FormEvent, type ReactNode } from 'react'
import { type UseFormReturn } from 'react-hook-form'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { TagInput } from '@/components/ui/tag-input'
import { ResourceEditor } from '@/features/resources/components/ResourceEditor'

import type { PersonaEditorValues } from '../hooks/usePersonaForm'

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
}

const PROFILE_EXAMPLE_SNIPPET = `Rolle: Senior-Customer-Support-Coach.
Tonfall: ruhig, empathisch, direkt — kein Marketing-Geschwurbel.
Beispiele: "Reset-Mail beantworten" → freundlich begruessen, Schritte als Liste.
Ausnahmen: kein Rabattversprechen ohne Freigabe.`

export function PersonaEditorForm({
  form,
  formKey,
  initialProfileBlocks,
  legacySystemPrompt,
  onSubmit,
  actions,
}: PersonaEditorFormProps) {
  // Viewer dürfen nur lesen (ADR-0023) — Auto-Save bleibt gesperrt (Detail-
  // Page reicht `isReady=false` durch, falls die Rolle das Editieren
  // unterbindet).
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const api = useApi()
  const showLegacyHint =
    legacySystemPrompt !== undefined && legacySystemPrompt.trim() !== ''
  return (
    <Card>
      <CardContent className="pt-6">
        <Form {...form}>
          <form
            className="flex flex-col gap-6"
            onSubmit={onSubmit ?? ((event) => event.preventDefault())}
          >
            <FormSection
              title="Identität"
              description="Wie die Persona heißt und wofür sie zuständig ist."
              help={
                <p>
                  Beispiel: <em>„Coach Carla — moderiert 1:1-Feedback-Gespräche"</em>.
                  Name und Beschreibung tauchen in Listen, Picker und Agent-Tools auf.
                </p>
              }
            >
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Name</FormLabel>
                    <FormControl>
                      <Input required placeholder="z. B. Coach Carla" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Beschreibung</FormLabel>
                    <FormControl>
                      <Input
                        required
                        placeholder="z. B. 1:1-Coach für Führungskräfte-Sparring"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            {showLegacyHint ? (
              <div
                role="note"
                aria-label="Veralteter System-Prompt"
                data-testid="persona-legacy-system-prompt-hint"
                className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
              >
                <p className="font-medium">Veraltet — Inhalt in Template übernehmen</p>
                <p className="mt-1 text-xs">
                  Persona-eigene System-Prompts laufen jetzt über das verknüpfte
                  Agent-Template. Übernimm den Text manuell in dein Template,
                  danach kannst du das Feld leer lassen.
                </p>
                <pre className="mt-2 max-h-40 overflow-auto rounded bg-amber-100/60 p-2 font-mono text-xs whitespace-pre-wrap dark:bg-amber-900/40">
                  {legacySystemPrompt}
                </pre>
              </div>
            ) : null}

            <FormSection
              title="Profil"
              description="Rolle, Tonfall, Beispiele und Ausnahmen."
              help={
                <div className="space-y-2">
                  <p>
                    Der Agent leitet daraus ab, wie er antworten soll —
                    strukturierte Beispiele schlagen Bullet-Listen.
                  </p>
                  <p className="text-xs font-medium text-foreground">Beispiel</p>
                  <pre className="rounded bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">
                    {PROFILE_EXAMPLE_SNIPPET}
                  </pre>
                </div>
              }
            >
              <FormField
                control={form.control}
                name="profileBlocks"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Profil-Inhalt</FormLabel>
                    <FormControl>
                      <ResourceEditor
                        key={formKey}
                        initialBlocks={initialProfileBlocks}
                        editable={!isViewer}
                        onChange={(blocks: ResourceBlock[]) => field.onChange(blocks)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            <FormSection
              title="Tags"
              description="Stichwörter zur Suche und Gruppierung."
              help={
                <p>
                  Beispiel: <em>„coaching, feedback, leadership"</em>.
                  Enter zum Anlegen, Klick auf das X zum Entfernen.
                  Vorschläge kommen aus bereits verwendeten Tags.
                </p>
              }
            >
              <FormField
                control={form.control}
                name="tags"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel id={`${field.name}-label`}>Tags</FormLabel>
                    <FormControl>
                      <TagInput
                        value={field.value}
                        onChange={field.onChange}
                        loadSuggestions={api.listPersonaTags}
                        ariaLabelledby={`${field.name}-label`}
                        placeholder="Tag eingeben und Enter drücken"
                        disabled={isViewer}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>
            {actions !== undefined ? actions : null}
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
