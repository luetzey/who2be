import { useFormContext, useWatch, type UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import type { ResourceBlock } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { FormSection } from '@/components/layout/FormSection'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { TagInput } from '@/components/ui/tag-input'
import { cn } from '@/lib/utils'

import type { PersonaEditorValues } from '../hooks/usePersonaForm'
import { PersonaProfileEditor } from './PersonaProfileEditor'
import { SkillsComingSoon } from './SkillsComingSoon'

// Anker-ID der Modi-Disclosure (Single-Form-Modus der New-Page). Der Info-Pill
// scrollt dorthin, wenn kein `onJumpToModes`-Callback vorliegt (Detail-Page
// wechselt stattdessen in den „Modi"-Tab).
export const MODES_SECTION_ID = 'persona-modes-section'

/**
 * Read-Only-Info-Pill am Kopf des Profil-Editors. Zeigt Anzahl + Default-Modus.
 * Beim Klick wechselt die Detail-Page in den „Modi"-Tab (`onJumpToModes`);
 * ohne Callback (New-Page, Single-Form) scrollt sie zur Modi-Disclosure. Modi
 * sind strukturierte Felder (keine Body-Blocks), daher nur Verweis, kein
 * Inline-Edit im Profil-Body.
 */
function PersonaModesInfoPill({ onJumpToModes }: { onJumpToModes?: () => void }) {
  const { t } = useTranslation('personas')
  const { control } = useFormContext<PersonaEditorValues>()
  const modes = useWatch({ control, name: 'modes' })
  if (modes === undefined || modes.length === 0) {
    return null
  }
  const defaultMode = modes.find((m) => m.is_default)
  const defaultLabel =
    defaultMode?.name?.trim() !== '' ? defaultMode?.name : t('modes.noDefaultLabel')
  const handleJump = () => {
    if (onJumpToModes !== undefined) {
      onJumpToModes()
      return
    }
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
      <Badge variant="secondary">{modes.length}</Badge>
      <span>
        {t('editor.modes.infoPillText')} <strong className="font-semibold">{defaultLabel}</strong>
      </span>
    </Button>
  )
}

const PROFILE_EXAMPLE_SNIPPET = `Rolle: Senior-Customer-Support-Coach.
Tonfall: ruhig, empathisch, direkt — kein Marketing-Geschwurbel.
Beispiele: "Reset-Mail beantworten" → freundlich begruessen, Schritte als Liste.
Ausnahmen: kein Rabattversprechen ohne Freigabe.`

interface PersonaProfileFieldsProps {
  form: UseFormReturn<PersonaEditorValues>
  formKey: string
  initialProfileBlocks: ResourceBlock[]
  personaId?: string
  legacySystemPrompt?: string
  locked?: boolean
  /**
   * Callback des Detail-Tabs: wechselt in den „Modi"-Tab. Ohne diesen Prop
   * (New-Page) scrollt der Info-Pill zur Inline-Modi-Disclosure.
   */
  onJumpToModes?: () => void
}

/**
 * Profil-Felder der Persona (Identitaet, Profil-Body + Slash-Pills, Skills,
 * Tags) — OHNE Form-/Modi-Wrapper. Wird sowohl vom Single-Form der New-Page
 * (`PersonaEditorForm`) als auch vom „Bearbeiten"-Tab der Detail-Page geteilt;
 * beide binden an dieselbe react-hook-form-Instanz. Muss innerhalb eines
 * `<Form>`-Providers stehen.
 */
export function PersonaProfileFields({
  form,
  formKey,
  initialProfileBlocks,
  personaId,
  legacySystemPrompt,
  locked = false,
  onJumpToModes,
}: PersonaProfileFieldsProps) {
  const { t } = useTranslation('personas')
  const isViewer = useCurrentWorkspaceRole() === 'viewer' || locked
  const api = useApi()
  const showLegacyHint = legacySystemPrompt !== undefined && legacySystemPrompt.trim() !== ''

  return (
    <div className="flex flex-col gap-6">
      <FormSection
        title={t('editor.identity.title')}
        description={t('editor.identity.description')}
        help={<p>{t('editor.identity.helpExample')}</p>}
      >
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t('common:fields.name')}</FormLabel>
              <FormControl>
                <Input
                  required
                  data-testid="persona-name-input"
                  placeholder={t('editor.identity.namePlaceholder')}
                  {...field}
                  disabled={isViewer}
                />
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
                  data-testid="persona-description-input"
                  placeholder={t('editor.identity.descriptionPlaceholder')}
                  {...field}
                  disabled={isViewer}
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
          <p className="mt-1 text-xs">{t('editor.legacy.body')}</p>
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
            <p>{t('editor.profile.helpLine1')}</p>
            <p>{t('editor.profile.helpLine2')}</p>
            <p className="text-xs font-medium text-foreground">
              {t('editor.profile.helpExampleLabel')}
            </p>
            <pre className="rounded bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">
              {PROFILE_EXAMPLE_SNIPPET}
            </pre>
          </div>
        }
      >
        <PersonaModesInfoPill onJumpToModes={onJumpToModes} />
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

      <FormSection
        title={t('editor.skills.title')}
        description={t('editor.skills.description')}
        help={<p>{t('editor.skills.helpText')}</p>}
      >
        <SkillsComingSoon />
      </FormSection>

      <FormSection
        title={t('editor.tags.title')}
        description={t('editor.tags.description')}
        help={<p>{t('editor.tags.helpText')}</p>}
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
    </div>
  )
}
