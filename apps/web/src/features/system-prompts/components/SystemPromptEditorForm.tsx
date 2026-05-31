import { type BaseSyntheticEvent, useCallback } from 'react'
import { type UseFormReturn } from 'react-hook-form'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { FormSection } from '@/components/layout/FormSection'
import { SystemPromptEditor } from '@/components/editor/system-prompt/SystemPromptEditor'
import type { SystemPromptBlock } from '@/components/editor/system-prompt/SystemPromptEditor'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'

import type { SystemPromptEditorValues } from '../hooks/useSystemPromptForm'
import { liquidBodyToInline } from '../lib/liquidMigration'

import { PlaceholderHelp } from './PlaceholderHelp'

interface SystemPromptEditorFormProps {
  form: UseFormReturn<SystemPromptEditorValues>
  onSubmit: (event?: BaseSyntheticEvent) => Promise<void>
  saveError: string | null
}

export function SystemPromptEditorForm({
  form,
  onSubmit,
  saveError,
}: SystemPromptEditorFormProps) {
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const bodyFormat = form.watch('body_format')
  const bodyValue = form.watch('body')

  // Beim BlockNote-Editor: blocks → JSON-String in form.body setzen.
  const handleBlockNoteChange = useCallback(
    (blocks: SystemPromptBlock[]) => {
      form.setValue('body', JSON.stringify(blocks), { shouldDirty: true })
    },
    [form],
  )

  // Migration: plain → blocknote. Wickelt den Plain-Text in einen
  // Single-Paragraph-Block und setzt body_format auf 'blocknote'.
  // Bekannte Liquid-Tokens werden dabei direkt zu Placeholder-Pills
  // umgesetzt (persona.name / persona.description); andere Tokens (z. B.
  // playbooks/triggers/resources, denen keine BlockNote-Placeholder-Form
  // entspricht) bleiben als Text stehen — der Server-Renderer im plain-
  // Pfad expandiert sie weiter, und der User kann sie im Editor durch
  // Slash-Befehl manuell ersetzen.
  function handleMigrateToBlockNote() {
    const content = liquidBodyToInline(bodyValue)
    const singleParagraph = [
      {
        id: crypto.randomUUID(),
        type: 'paragraph',
        props: {
          textColor: 'default',
          backgroundColor: 'default',
          textAlignment: 'left',
        },
        content,
        children: [],
      },
    ]
    form.setValue('body', JSON.stringify(singleParagraph), { shouldDirty: true })
    form.setValue('body_format', 'blocknote', { shouldDirty: true })
  }

  // Initial-Bloecke fuer den BlockNote-Editor aus dem gespeicherten JSON.
  let initialBlocks: SystemPromptBlock[] | undefined
  if (bodyFormat === 'blocknote' && bodyValue !== '') {
    try {
      initialBlocks = JSON.parse(bodyValue) as SystemPromptBlock[]
    } catch {
      initialBlocks = undefined
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
      <div className="flex flex-col gap-4">
        {saveError !== null ? <ErrorAlert message={saveError} /> : null}
        <Card>
          <CardContent className="pt-6">
            <Form {...form}>
              <form onSubmit={onSubmit} className="flex flex-col gap-6">
                <FormSection
                  title="Identität"
                  description="Wie das Template heißt und wofür es genutzt wird."
                  help={
                    <p>
                      Beispiel: <em>„Customer-Support-Agent v1"</em>. Beschreibung
                      taucht in der Template-Liste und im Agent-Picker auf.
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
                          <Input required placeholder="z. B. Customer-Support-Agent" {...field} />
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
                            placeholder="z. B. Standard-Template für Support-Agenten"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </FormSection>

                <FormSection
                  title="Prompt-Body"
                  description={
                    bodyFormat === 'blocknote'
                      ? 'Schreibe deinen Prompt im Editor. Mit / fügst du Placeholder ein.'
                      : 'Legacy-Format (Plain-Text). Migriere zum BlockNote-Editor, um Placeholder zu nutzen.'
                  }
                  help={
                    bodyFormat === 'blocknote' ? (
                      <p>
                        Tippe <code>/</code> im Editor um Playbook-, Resource-, Persona-Feld-
                        oder Datum-Placeholder einzufuegen. Der Backend-Renderer expandiert
                        diese beim MCP-Read zu echtem Text.
                      </p>
                    ) : (
                      <p>
                        Dieses Template wurde im Plain-Text-Format angelegt. Klicke
                        „In BlockNote-Editor migrieren", um Placeholder nutzen zu koennen.
                      </p>
                    )
                  }
                >
                  {bodyFormat === 'blocknote' ? (
                    <FormField
                      control={form.control}
                      name="body"
                      render={() => (
                        <FormItem>
                          <FormLabel>Body</FormLabel>
                          <SystemPromptEditor
                            key={initialBlocks !== undefined ? 'loaded' : 'empty'}
                            initialBlocks={initialBlocks}
                            editable={!isViewer}
                            onChange={handleBlockNoteChange}
                          />
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  ) : (
                    <FormField
                      control={form.control}
                      name="body"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Body</FormLabel>
                          <FormControl>
                            <Textarea
                              required
                              rows={18}
                              placeholder="Du bist {{ persona.name }} — …"
                              className="font-mono text-sm"
                              disabled={isViewer}
                              {...field}
                            />
                          </FormControl>
                          {!isViewer ? (
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className="mt-2"
                              onClick={handleMigrateToBlockNote}
                              data-testid="migrate-to-blocknote-btn"
                            >
                              In BlockNote-Editor migrieren
                            </Button>
                          ) : null}
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
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
      </div>
      <aside
        aria-label="Placeholder-Hilfe"
        className="lg:sticky lg:top-4 lg:self-start"
      >
        <PlaceholderHelp compact />
      </aside>
    </div>
  )
}
