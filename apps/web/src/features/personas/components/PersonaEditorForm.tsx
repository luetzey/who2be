import { type BaseSyntheticEvent, useMemo } from 'react'
import { type UseFormReturn } from 'react-hook-form'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { BlockNoteEditor } from '@/components/editor/BlockNoteEditor'
import { blocksToPlainText, plainTextToBlocks } from '@/components/editor/plaintext'
import { FormSection } from '@/components/layout/FormSection'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { TagInput } from '@/components/ui/tag-input'
import { ResourceEditor } from '@/features/resources/components/ResourceEditor'

import type { PersonaEditorValues } from '../hooks/usePersonaForm'

interface PersonaEditorFormProps {
  form: UseFormReturn<PersonaEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
  // Render-Identitaet fuer die BlockNote-Inseln. Wechselt der Key, wird der
  // ProseMirror-State remountet — sonst bleibt der Editor auf dem alten
  // `initialContent` haengen (useCreateBlockNote initialisiert nur einmal).
  formKey: string
  // Initial-Snapshot direkt aus dem persona-Prop. Wir koennen NICHT
  // `field.value` als initialBlocks nutzen, weil form.reset erst im Effect
  // nach dem Mount laeuft — der frische Editor wuerde sonst den alten
  // Form-State sehen. Pattern parallel zu ResourceDetailPage.
  initialProfileBlocks: ResourceBlock[]
  initialSystemPrompt: string
}

const PROFILE_EXAMPLE_SNIPPET = `Rolle: Senior-Customer-Support-Coach.
Tonfall: ruhig, empathisch, direkt — kein Marketing-Geschwurbel.
Beispiele: "Reset-Mail beantworten" → freundlich begruessen, Schritte als Liste.
Ausnahmen: kein Rabattversprechen ohne Freigabe.`

export function PersonaEditorForm({
  form,
  onSubmit,
  saveError,
  formKey,
  initialProfileBlocks,
  initialSystemPrompt,
}: PersonaEditorFormProps) {
  // Viewer dürfen nur lesen (ADR-0023) — Save bleibt gesperrt.
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const api = useApi()
  return (
    <>
      {saveError !== null ? <ErrorAlert message={saveError} /> : null}
      <Card>
        <CardContent className="pt-6">
          <Form {...form}>
            <form onSubmit={onSubmit} className="flex flex-col gap-6">
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
                title="System-Prompt"
                description="Technischer Prompt — wird wörtlich an das LLM geschickt."
                help={
                  <p>
                    Hier landet die operative Anweisung, nicht die Erklärung.
                    Halte den Prompt kurz und imperativ — Beispiele und Personality
                    gehören ins Profil oben.
                  </p>
                }
              >
                <FormField
                  control={form.control}
                  name="systemPrompt"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>System-Prompt</FormLabel>
                      <FormControl>
                        <SystemPromptEditor
                          key={formKey}
                          initialValue={initialSystemPrompt}
                          editable={!isViewer}
                          onChange={field.onChange}
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

              <div className="flex justify-end">
                <Button
                  type="submit"
                  variant="brand"
                  disabled={form.formState.isSubmitting || isViewer}
                  title={isViewer ? 'Viewer können Inhalte nur ansehen' : undefined}
                >
                  Neue Version speichern
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </>
  )
}

interface SystemPromptEditorProps {
  initialValue: string
  editable: boolean
  onChange: (value: string) => void
}

// Plaintext-Bruecke: das Form-Feld bleibt `string` (Backend-Vertrag), aber die
// Eingabe laeuft durch den geteilten BlockNote-Editor — damit auch der
// System-Prompt das gleiche Slash-/Side-Menue bekommt wie Profil und Body.
// `initialValue` wird einmal pro Mount in Bloecke uebersetzt; Rehydration
// nach Save laeuft ueber den `formKey`-Wechsel im Parent.
function SystemPromptEditor({ initialValue, editable, onChange }: SystemPromptEditorProps) {
  const initialBlocks = useMemo(() => plainTextToBlocks(initialValue), [initialValue])
  return (
    <BlockNoteEditor
      initialBlocks={initialBlocks}
      editable={editable}
      onChange={(blocks: ResourceBlock[]) => onChange(blocksToPlainText(blocks))}
    />
  )
}
