import { useState, type FormEvent, type ReactNode } from 'react'
import { type UseFormReturn } from 'react-hook-form'

import type {
  Playbook,
  PlaybookType,
  ResourceBlock,
  ResourceLink,
  SystemPromptBodyFormat,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { TagInput } from '@/components/ui/tag-input'
import { ResourceEditor } from '@/features/resources/components/ResourceEditor'

import { PLAYBOOK_TYPES, type PlaybookEditorValues } from '../hooks/usePlaybookForm'
import { blockPlainText } from '../lib/blockText'
import { buildMigratedBody } from '../lib/bodyMigration'

import { PlaybookBodyEditor, type PlaybookBodyBlock } from './PlaybookBodyEditor'

// Plain-Text-Snapshot der aktuellen Bloecke — fuer den Migrate-Pfad, damit
// der bestehende Plain-Body in BlockNote-Paragraphen ueberfuehrt werden kann.
function blocksToPlainText(blocks: ResourceBlock[]): string {
  return blocks
    .map((block) => blockPlainText(block).trim())
    .filter((text) => text.length > 0)
    .join('\n\n')
}

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
  // Initial-Body-Format aus dem playbook-Prop (analog zu initialBodyBlocks).
  // Defaults auf 'plain' fuer die Neu-Page, weil form-default ebenfalls 'plain'
  // ist und es dort noch kein gespeichertes Playbook gibt.
  initialBodyFormat?: SystemPromptBodyFormat
  // Detail-Page nutzt Auto-Save, dort bleibt der Default (preventDefault).
  // Neu-Page reicht einen handleSubmit-Callback durch.
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void
  // Optionaler Slot fuer Submit-/Cancel-Buttons (nur Neu-Page).
  actions?: ReactNode
  // Bestehende Relationen (nur Detail-Page) — werden vom Migrate-Button als
  // Pills in den Body gehoben, damit der set-replace-Sync sie nicht loescht.
  // Sind sie undefined (Neu-Page), wird der Migrate-Button ohne Backfill
  // gerendert (es gibt dort noch keine Relationen).
  composesChildren?: Playbook[]
  resourceLinks?: ResourceLink[]
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
  initialBodyFormat = 'plain',
  onSubmit,
  actions,
  composesChildren,
  resourceLinks,
}: PlaybookEditorFormProps) {
  // Viewer dürfen nur lesen (ADR-0023) — Auto-Save deaktiviert sich auf
  // Detail-Page-Ebene.
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const api = useApi()
  const currentType = form.watch('type')
  // form.watch('body_format') ist auf dem ersten Render noch der Form-
  // Default ('plain') — form.reset im usePlaybookForm-Effect laeuft erst NACH
  // dem Mount. Solange der User das Format nicht aktiv geaendert hat (Migrate-
  // Button → setValue(..., {shouldDirty: true})), trauen wir dem aus dem
  // playbook-Prop abgeleiteten initialBodyFormat. Andernfalls landet ein
  // blocknote-Body mit Placeholder-Pills im default-schema-ResourceEditor
  // und stuerzt mit "node type placeholder not found" ab.
  const watchedBodyFormat = form.watch('body_format')
  const formatDirty = form.formState.dirtyFields.body_format === true
  const bodyFormat: SystemPromptBodyFormat = formatDirty
    ? watchedBodyFormat
    : initialBodyFormat
  const currentHint =
    TYPE_OPTIONS.find((option) => option.value === currentType)?.hint ?? null

  // Seed-Bloecke + Remount-Key fuer die BlockNote-Insel. Beim ersten Mount
  // sind das die `initialBodyBlocks` (aus dem playbook-Prop). Nach einer
  // Migration setzen wir den Seed auf die migrierten Bloecke und bumpen den
  // Key, damit `useCreateBlockNote` mit dem neuen `initialContent` remountet.
  const [bodySeed, setBodySeed] = useState<{
    blocks: PlaybookBodyBlock[]
    key: number
  }>({ blocks: initialBodyBlocks as PlaybookBodyBlock[], key: 0 })

  // BlockNote-onChange: das aktuelle Dokument (inkl. Pills) in `bodyBlocks`
  // schreiben. `toInput` serialisiert es bei `body_format='blocknote'` via
  // JSON.stringify.
  const handleBlockNoteChange = (blocks: PlaybookBodyBlock[]) => {
    form.setValue('bodyBlocks', blocks as unknown as ResourceBlock[], {
      shouldDirty: true,
    })
  }

  // Migrate-Pfad (KRITISCH gegen Datenverlust): Plain-Body → BlockNote +
  // bestehende Relationen als Pills voranstellen. Ohne dieses Backfill wuerde
  // der erste blocknote-Save (set-replace) die Composes/Resource-Links
  // loeschen. Die bestehenden Bloecke (aus dem Editor-State) werden in
  // Plain-Text zurueckgewandelt und neu als BlockNote-Paragraphen aufgebaut.
  const handleMigrateToBlockNote = () => {
    const plainBody = blocksToPlainText(form.getValues('bodyBlocks'))
    const migrated = buildMigratedBody(
      plainBody,
      composesChildren ?? [],
      resourceLinks ?? [],
    )
    // Seed setzen, damit die BlockNote-Insel mit den migrierten Pills mountet.
    setBodySeed((prev) => ({
      blocks: migrated as PlaybookBodyBlock[],
      key: prev.key + 1,
    }))
    form.setValue('bodyBlocks', migrated, { shouldDirty: true })
    form.setValue('body_format', 'blocknote', { shouldDirty: true })
  }

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
                {bodyFormat === 'blocknote' ? (
                  <FormField
                    control={form.control}
                    name="bodyBlocks"
                    render={() => (
                      <FormItem>
                        <FormLabel>Inhalt</FormLabel>
                        <FormControl>
                          <PlaybookBodyEditor
                            key={`${formKey}-blocknote-${bodySeed.key}`}
                            initialBlocks={bodySeed.blocks}
                            editable={!isViewer}
                            onChange={handleBlockNoteChange}
                          />
                        </FormControl>
                        <p className="text-xs text-muted-foreground">
                          Tippe <code>/</code> im Editor, um Playbook- oder
                          Resource-Pills einzufügen. Verlinkte Relationen leben
                          ab jetzt im Body.
                        </p>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                ) : (
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

              {actions !== undefined ? actions : null}
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
