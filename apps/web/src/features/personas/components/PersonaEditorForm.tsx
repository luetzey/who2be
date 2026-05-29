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
import { Textarea } from '@/components/ui/textarea'
import { ResourceEditor } from '@/features/resources/components/ResourceEditor'

import type { PersonaEditorValues } from '../hooks/usePersonaForm'

interface PersonaEditorFormProps {
  form: UseFormReturn<PersonaEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

const PROFILE_EXAMPLE_SNIPPET = `Rolle: Senior-Customer-Support-Coach.
Tonfall: ruhig, empathisch, direkt — kein Marketing-Geschwurbel.
Beispiele: "Reset-Mail beantworten" → freundlich begruessen, Schritte als Liste.
Ausnahmen: kein Rabattversprechen ohne Freigabe.`

export function PersonaEditorForm({ form, onSubmit, saveError }: PersonaEditorFormProps) {
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
                description={'Wie die Persona heißt und wofür sie zuständig ist. Beispiel: „Coach Carla — moderiert 1:1-Feedback-Gespräche".'}
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
                description="Rolle, Tonfall, Beispiele und Ausnahmen. Der Agent leitet daraus ab, wie er antworten soll — strukturierte Beispiele schlagen Bullet-Listen."
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
                <details className="rounded-md border bg-muted/30 p-3 text-sm">
                  <summary className="cursor-pointer font-medium text-foreground">
                    Beispiel anzeigen
                  </summary>
                  <pre className="mt-2 font-mono text-xs whitespace-pre-wrap text-muted-foreground">
                    {PROFILE_EXAMPLE_SNIPPET}
                  </pre>
                </details>
              </FormSection>

              <FormSection
                title="System-Prompt"
                description="Technischer Prompt — wird wörtlich an das LLM geschickt. Hier landet die operative Anweisung, nicht die Erklärung."
                footer="Tipp: Halte den Prompt kurz und imperativ. Beispiele und Personality gehören ins Profil oben."
              >
                <FormField
                  control={form.control}
                  name="systemPrompt"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>System-Prompt</FormLabel>
                      <FormControl>
                        <Textarea
                          required
                          rows={6}
                          placeholder="z. B. Du bist ein 1:1-Coach. Stelle erst Klärungsfragen, bevor du Empfehlungen gibst."
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </FormSection>

              <FormSection
                title="Tags"
                description={'Stichwörter zur Suche und Gruppierung. Beispiel: „coaching, feedback, leadership".'}
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
