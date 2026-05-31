import { type UseFormReturn } from 'react-hook-form'

import type { PlaybookType, ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { TagInput } from '@/components/ui/tag-input'
import { ResourceEditor } from '@/features/resources/components/ResourceEditor'

import { PLAYBOOK_TYPES, type PlaybookEditorValues } from '../hooks/usePlaybookForm'

interface PlaybookEditorFormProps {
  form: UseFormReturn<PlaybookEditorValues>
  // Render-Identitaet fuer die BlockNote-Insel. Wechselt der Key, wird der
  // ProseMirror-State remountet — sonst bleibt der Editor auf dem alten
  // `initialContent` haengen (useCreateBlockNote initialisiert nur einmal).
  formKey: string
  // Initial-Snapshot der Body-Bloecke aus dem playbook-Prop (siehe
  // usePlaybookForm) — `field.value` wuerde den alten Form-State zeigen,
  // weil form.reset erst im Effect nach dem Mount laeuft.
  initialBodyBlocks: ResourceBlock[]
}

interface TypeOption {
  value: PlaybookType
  label: string
  hint: string
}

const TYPE_OPTIONS: readonly TypeOption[] = [
  {
    value: 'prompt',
    label: 'Prompt',
    hint: 'Ein Einzel-Prompt mit klarem Outcome — z. B. „Fasse den Anruf in 3 Bullets zusammen".',
  },
  {
    value: 'instructions',
    label: 'Instructions',
    hint: 'Mehrteilige Handlungsanweisung mit Schritt-Reihenfolge — z. B. Onboarding-Flow eines Agenten.',
  },
  {
    value: 'snippet',
    label: 'Snippet',
    hint: 'Kurze, wiederverwendbare Textbausteine — z. B. Standard-Begruessung oder rechtliche Fussnote.',
  },
  {
    value: 'workflow',
    label: 'Workflow',
    hint: 'Mehrstufiger Prozess mit Verzweigungen — z. B. Eskalation, wenn der Kunde unzufrieden bleibt.',
  },
  {
    value: 'checklist',
    label: 'Checklist',
    hint: 'Pruefliste — z. B. „Pre-Flight vor dem Versand einer Kampagne".',
  },
  {
    value: 'faq',
    label: 'FAQ',
    hint: 'Frage-Antwort-Sammlung — z. B. die Top-10-Support-Fragen einer Produkt-Linie.',
  },
]

export function PlaybookEditorForm({
  form,
  formKey,
  initialBodyBlocks,
}: PlaybookEditorFormProps) {
  // Viewer dürfen nur lesen (ADR-0023) — Auto-Save deaktiviert sich auf
  // Detail-Page-Ebene.
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const api = useApi()
  const currentType = form.watch('type')
  const currentHint =
    TYPE_OPTIONS.find((option) => option.value === currentType)?.hint ?? null

  return (
    <Card>
      <CardContent className="pt-6">
        <Form {...form}>
          <form
            className="flex flex-col gap-6"
            onSubmit={(event) => event.preventDefault()}
          >
              <FormSection
                title="Identität"
                description="Wie das Playbook heißt, welcher Typ es ist und worum es geht."
                help={
                  <div className="space-y-2">
                    <p>
                      Beispiel: <em>„Reset-Mail beantworten"</em> als Workflow.
                    </p>
                    <p className="text-xs font-medium text-foreground">Typen</p>
                    <ul className="list-disc space-y-1 pl-4 text-xs">
                      {TYPE_OPTIONS.map((option) => (
                        <li key={option.value}>
                          <strong>{option.label}:</strong> {option.hint}
                        </li>
                      ))}
                    </ul>
                  </div>
                }
              >
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name</FormLabel>
                      <FormControl>
                        <Input
                          required
                          placeholder="z. B. Reset-Mail beantworten"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Typ</FormLabel>
                      <FormControl>
                        <Select required {...field}>
                          {PLAYBOOK_TYPES.map((option) => {
                            const meta = TYPE_OPTIONS.find((entry) => entry.value === option)
                            return (
                              <option key={option} value={option}>
                                {meta?.label ?? option}
                              </option>
                            )
                          })}
                        </Select>
                      </FormControl>
                      {currentHint !== null ? (
                        <p className="text-xs text-muted-foreground">{currentHint}</p>
                      ) : null}
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
                          placeholder="z. B. Antwortet auf Passwort-Reset-Anfragen mit klarem nächsten Schritt"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </FormSection>

              <FormSection
                title="Inhalt"
                description="Das eigentliche Playbook und seine Auslöser."
                help={
                  <p>
                    Beispiel: Schritt 1 — Kunde begrüßen; Schritt 2 — Identität
                    verifizieren; Schritt 3 — Reset-Link versenden. Änderungen
                    erzeugen eine neue Version; alte Versionen bleiben erhalten.
                  </p>
                }
              >
                <FormField
                  control={form.control}
                  name="bodyBlocks"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Inhalt</FormLabel>
                      <FormControl>
                        <ResourceEditor
                          key={formKey}
                          initialBlocks={initialBodyBlocks}
                          editable={!isViewer}
                          onChange={(blocks: ResourceBlock[]) => field.onChange(blocks)}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
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
                          loadSuggestions={api.listPlaybookTags}
                          ariaLabelledby={`${field.name}-label`}
                          placeholder="Tag eingeben und Enter drücken"
                          disabled={isViewer}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="triggers"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel id={`${field.name}-label`}>Trigger</FormLabel>
                      <FormControl>
                        <TagInput
                          value={field.value}
                          onChange={field.onChange}
                          ariaLabelledby={`${field.name}-label`}
                          placeholder="Trigger eingeben und Enter drücken"
                          disabled={isViewer}
                        />
                      </FormControl>
                      <p className="text-xs text-muted-foreground">
                        Enter zum Anlegen, Klick zum Entfernen.
                      </p>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </FormSection>

          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
