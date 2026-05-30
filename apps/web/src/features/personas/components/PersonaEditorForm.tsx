import { type BaseSyntheticEvent } from 'react'
import { type UseFormReturn } from 'react-hook-form'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
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
  /**
   * Bestehender Persona-eigener System-Prompt. Mit Phase 3 Runde 3 Track 3
   * wandert der System-Prompt ins Agent-Template; die UI versteckt das Feld
   * und zeigt fuer Bestandsdaten lediglich eine Read-Only-Hinweis-Box.
   */
  legacySystemPrompt?: string
}

const PROFILE_EXAMPLE_SNIPPET = `Rolle: Senior-Customer-Support-Coach.
Tonfall: ruhig, empathisch, direkt — kein Marketing-Geschwurbel.
Beispiele: "Reset-Mail beantworten" → freundlich begruessen, Schritte als Liste.
Ausnahmen: kein Rabattversprechen ohne Freigabe.`

export function PersonaEditorForm({
  form,
  onSubmit,
  saveError,
  legacySystemPrompt,
}: PersonaEditorFormProps) {
  // Viewer dürfen nur lesen (ADR-0023) — Save bleibt gesperrt.
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const api = useApi()
  const showLegacyHint =
    legacySystemPrompt !== undefined && legacySystemPrompt.trim() !== ''
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
                          initialBlocks={field.value}
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
