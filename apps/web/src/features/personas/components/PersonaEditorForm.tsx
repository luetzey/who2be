import { ChevronRight } from 'lucide-react'
import { type FormEvent, type ReactNode } from 'react'
import { useFormContext, useWatch, type Control, type UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { TagInput } from '@/components/ui/tag-input'
import { cn } from '@/lib/utils'

import type { PersonaEditorValues } from '../hooks/usePersonaForm'
import { PersonaModesEditor } from './PersonaModesEditor'
import { PersonaProfileEditor } from './PersonaProfileEditor'
import { SkillsComingSoon } from './SkillsComingSoon'

const MODES_SECTION_ID = 'persona-modes-section'

/**
 * Read-Only-Info-Pill am Kopf des Profil-Editors. Zeigt Anzahl + Default-Modus
 * und scrollt beim Klick zum Modi-Bereich (Disclosure unten). So sieht der
 * Editor beim Schreiben des Profil-Body, dass Modi existieren, ohne sie inline
 * editieren zu muessen (Slash-Pill wuerde Datenmodell-Bruch erzeugen — Modi
 * sind strukturierte Felder, keine Body-Blocks).
 */
function PersonaModesInfoPill() {
  const { t } = useTranslation('personas')
  const { control } = useFormContext<PersonaEditorValues>()
  const modes = useWatch({ control, name: 'modes' })
  if (modes === undefined || modes.length === 0) {
    return null
  }
  const defaultMode = modes.find((m) => m.is_default)
  const defaultLabel = defaultMode?.name?.trim() !== '' ? defaultMode?.name : t('modes.noDefaultLabel')
  const handleJump = () => {
    const el = document.getElementById(MODES_SECTION_ID)
    if (el === null) return
    if (el instanceof HTMLDetailsElement) {
      el.open = true
    }
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={handleJump}
      className={cn(
        'h-auto self-start rounded-full border-brand/30 bg-brand/5 px-3 py-1',
        'text-xs font-normal text-foreground hover:bg-brand/10',
      )}
      data-testid="persona-modes-info-pill"
      aria-label={t('editor.modes.infoAriaLabel', { count: modes.length, defaultLabel })}
    >
      <Badge variant="secondary" className="px-1.5 py-0 text-[10px]">
        {modes.length}
      </Badge>
      <span>
        {t('editor.modes.infoPillText')} <strong className="font-semibold">{defaultLabel}</strong>
      </span>
    </Button>
  )
}

interface PersonaModesDisclosureProps {
  control: Control<PersonaEditorValues>
  disabled: boolean
}

/**
 * Disclosure-Wrapper um den `PersonaModesEditor`. Steht unmittelbar unter dem
 * Profil-Editor (statt am Form-Ende), damit der Schreib-Ort des Profils und
 * der situative Verhaltens-Layer (Modi) raeumlich zusammenliegen. Default-
 * offen, sobald mindestens ein Modus existiert — sonst eingeklappt, um den
 * Editor-Body nicht visuell zu verlaengern, wenn das Feature ungenutzt ist.
 *
 * Native `<details>`/`<summary>` ist a11y-konform und braucht keine eigene
 * Open/Close-State-Maschine (das macht der Browser).
 */
function PersonaModesDisclosure({ control, disabled }: PersonaModesDisclosureProps) {
  const { t } = useTranslation('personas')
  const modes = useWatch({ control, name: 'modes' })
  const hasModes = modes !== undefined && modes.length > 0
  return (
    <details
      id={MODES_SECTION_ID}
      className="group rounded-lg border bg-card"
      open={hasModes}
    >
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
}

const PROFILE_EXAMPLE_SNIPPET = `Rolle: Senior-Customer-Support-Coach.
Tonfall: ruhig, empathisch, direkt — kein Marketing-Geschwurbel.
Beispiele: "Reset-Mail beantworten" → freundlich begruessen, Schritte als Liste.
Ausnahmen: kein Rabattversprechen ohne Freigabe.`

export function PersonaEditorForm({
  form,
  formKey,
  initialProfileBlocks,
  personaId,
  legacySystemPrompt,
  onSubmit,
  actions,
}: PersonaEditorFormProps) {
  // Viewer dürfen nur lesen (ADR-0023) — Auto-Save bleibt gesperrt (Detail-
  // Page reicht `isReady=false` durch, falls die Rolle das Editieren
  // unterbindet).
  const { t } = useTranslation('personas')
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
              title={t('editor.identity.title')}
              description={t('editor.identity.description')}
              help={
                <p>
                  {t('editor.identity.helpExample')}
                </p>
              }
            >
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('common:fields.name')}</FormLabel>
                    <FormControl>
                      <Input required placeholder={t('editor.identity.namePlaceholder')} {...field} />
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
                    <FormLabel>{t('common:fields.description')}</FormLabel>
                    <FormControl>
                      <Input
                        required
                        placeholder={t('editor.identity.descriptionPlaceholder')}
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
                aria-label={t('editor.legacy.ariaLabel')}
                data-testid="persona-legacy-system-prompt-hint"
                className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
              >
                <p className="font-medium">{t('editor.legacy.title')}</p>
                <p className="mt-1 text-xs">
                  {t('editor.legacy.body')}
                </p>
                <pre className="mt-2 max-h-40 overflow-auto rounded bg-amber-100/60 p-2 font-mono text-xs whitespace-pre-wrap dark:bg-amber-900/40">
                  {legacySystemPrompt}
                </pre>
              </div>
            ) : null}

            <FormSection
              title={t('editor.profile.title')}
              description={t('editor.profile.description')}
              help={
                <div className="space-y-2">
                  <p>
                    {t('editor.profile.helpLine1')}
                  </p>
                  <p>
                    {t('editor.profile.helpLine2')}
                  </p>
                  <p className="text-xs font-medium text-foreground">{t('editor.profile.helpExampleLabel')}</p>
                  <pre className="rounded bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">
                    {PROFILE_EXAMPLE_SNIPPET}
                  </pre>
                </div>
              }
            >
              <PersonaModesInfoPill />
              <FormField
                control={form.control}
                name="profileBlocks"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{t('editor.profile.contentLabel')}</FormLabel>
                    <FormControl>
                      <PersonaProfileEditor
                        key={formKey}
                        initialBlocks={initialProfileBlocks}
                        editable={!isViewer}
                        personaId={personaId}
                        onChange={(blocks: ResourceBlock[]) => field.onChange(blocks)}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </FormSection>

            <PersonaModesDisclosure control={form.control} disabled={isViewer} />

            <FormSection
              title={t('editor.skills.title')}
              description={t('editor.skills.description')}
              help={
                <p>
                  {t('editor.skills.helpText')}
                </p>
              }
            >
              <SkillsComingSoon />
            </FormSection>

            <FormSection
              title={t('editor.tags.title')}
              description={t('editor.tags.description')}
              help={
                <p>
                  {t('editor.tags.helpText')}
                </p>
              }
            >
              <FormField
                control={form.control}
                name="tags"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel id={`${field.name}-label`}>{t('common:fields.tags')}</FormLabel>
                    <FormControl>
                      <TagInput
                        value={field.value}
                        onChange={field.onChange}
                        loadSuggestions={api.listPersonaTags}
                        ariaLabelledby={`${field.name}-label`}
                        placeholder={t('editor.tags.placeholder')}
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
