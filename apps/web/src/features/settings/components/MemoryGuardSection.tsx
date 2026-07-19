import { AlertTriangle } from 'lucide-react'
import { useCallback, useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { MemoryGuardConfig, MemoryGuardMode } from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { FormSection } from '@/components/layout/FormSection'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { TagInput } from '@/components/ui/tag-input'
import { notify } from '@/lib/feedback'

// ADR-0044-Addendum — Workspace-Einstellung "Memory-Wächter": Modus des
// eingebauten save_memory-Injection-Filters + optionale eigene Phrasen-Regeln
// (Stufe B, literale Phrasen statt Regex). Nur admin sichtbar/editierbar; der
// Parent (WorkspaceSettingsPage) rendert diese Sektion ausschliesslich fuer
// Admins — der GET-Endpoint antwortet fuer editor/viewer ohnehin mit 403.

const MODES: MemoryGuardMode[] = ['standard', 'custom', 'off']
const PHRASE_MIN_LENGTH = 2
const PHRASE_MAX_LENGTH = 100
const PHRASE_MAX_COUNT = 50

const DEFAULT_CONFIG: MemoryGuardConfig = {
  mode: 'standard',
  allow_phrases: [],
  block_phrases: [],
}

function describeError(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback
}

interface PhraseEditorProps {
  label: string
  description: string
  value: string[]
  onChange: (next: string[]) => void
  disabled?: boolean
}

// Chip-Editor fuer Ausnahme-/Block-Phrasen. Der TagInput-Primitive uebernimmt
// Chips + Enter/Komma-zum-Hinzufuegen + Entfernen-Buttons; hier kommt nur die
// Grenzen-Validierung (2-100 Zeichen, max. 50 Eintraege) dazu, die der Server
// ohnehin hart durchsetzt.
function PhraseEditor({ label, description, value, onChange, disabled = false }: PhraseEditorProps) {
  const { t } = useTranslation('settings')
  const inputId = useId()
  const [error, setError] = useState<string | null>(null)

  const handleChange = useCallback(
    (next: string[]) => {
      // Entfernen (next kuerzer oder gleich lang) ist immer erlaubt.
      if (next.length <= value.length) {
        setError(null)
        onChange(next)
        return
      }
      const added = next[next.length - 1] ?? ''
      if (added.length < PHRASE_MIN_LENGTH || added.length > PHRASE_MAX_LENGTH) {
        setError(t('workspace.memoryGuard.phraseLengthError'))
        return
      }
      if (value.length >= PHRASE_MAX_COUNT) {
        setError(t('workspace.memoryGuard.phraseLimitError'))
        return
      }
      setError(null)
      onChange(next)
    },
    [value, onChange, t],
  )

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <Label htmlFor={inputId}>{label}</Label>
        <span className="text-xs text-muted-foreground">
          {value.length}/{PHRASE_MAX_COUNT}
        </span>
      </div>
      <p className="text-sm text-muted-foreground">{description}</p>
      <TagInput
        id={inputId}
        value={value}
        onChange={handleChange}
        disabled={disabled}
        placeholder={t('workspace.memoryGuard.phrasePlaceholder')}
      />
      {error !== null ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}

export function MemoryGuardSection() {
  const { t } = useTranslation('settings')
  const api = useApi()

  const [config, setConfig] = useState<MemoryGuardConfig>(DEFAULT_CONFIG)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const next = await api.getMemoryGuard()
      setConfig(next)
    } catch (cause) {
      setLoadError(describeError(cause, t('workspace.memoryGuard.loadError')))
    } finally {
      setLoading(false)
    }
  }, [api, t])

  useEffect(() => {
    void load()
  }, [load])

  async function onSave() {
    setSaving(true)
    try {
      // Server ist die kanonische Quelle (kann z. B. trimmen/normalisieren) —
      // die Antwort ersetzt den lokalen Stand direkt, statt einen weiteren
      // GET-Roundtrip zu erzwingen.
      const saved = await api.updateMemoryGuard(config)
      setConfig(saved)
      notify.success(t('workspace.memoryGuard.savedToast'))
    } catch (cause) {
      notify.error(describeError(cause, t('workspace.memoryGuard.saveError')))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('workspace.memoryGuard.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? <LoadingState rows={3} /> : null}
        {!loading && loadError !== null ? <ErrorAlert message={loadError} /> : null}
        {!loading && loadError === null ? (
          <FormSection
            title={t('workspace.memoryGuard.formTitle')}
            description={t('workspace.memoryGuard.formDescription')}
          >
            <RadioGroup
              value={config.mode}
              onValueChange={(value) =>
                setConfig((prev) => ({ ...prev, mode: value as MemoryGuardMode }))
              }
              disabled={saving}
              aria-label={t('workspace.memoryGuard.modeLabel')}
            >
              {MODES.map((mode) => {
                const optionId = `memory-guard-mode-${mode}`
                return (
                  <div key={mode} className="flex items-start gap-3 rounded-md border p-3">
                    <RadioGroupItem value={mode} id={optionId} className="mt-1" />
                    <div className="flex flex-col gap-1">
                      <Label htmlFor={optionId} className="font-normal">
                        {t(`workspace.memoryGuard.modes.${mode}.label`)}
                      </Label>
                      <p className="text-sm text-muted-foreground">
                        {t(`workspace.memoryGuard.modes.${mode}.description`)}
                      </p>
                    </div>
                  </div>
                )
              })}
            </RadioGroup>

            {config.mode === 'off' ? (
              <Alert variant="destructive">
                <AlertTriangle />
                <AlertTitle>{t('workspace.memoryGuard.offWarningTitle')}</AlertTitle>
                <AlertDescription>
                  {t('workspace.memoryGuard.offWarningDescription')}
                </AlertDescription>
              </Alert>
            ) : null}

            {config.mode === 'custom' ? (
              <div className="flex flex-col gap-6">
                <PhraseEditor
                  label={t('workspace.memoryGuard.allowPhrases.label')}
                  description={t('workspace.memoryGuard.allowPhrases.description')}
                  value={config.allow_phrases}
                  onChange={(next) => setConfig((prev) => ({ ...prev, allow_phrases: next }))}
                  disabled={saving}
                />
                <PhraseEditor
                  label={t('workspace.memoryGuard.blockPhrases.label')}
                  description={t('workspace.memoryGuard.blockPhrases.description')}
                  value={config.block_phrases}
                  onChange={(next) => setConfig((prev) => ({ ...prev, block_phrases: next }))}
                  disabled={saving}
                />
              </div>
            ) : null}

            <div className="flex justify-end">
              <Button type="button" variant="brand" disabled={saving} onClick={() => void onSave()}>
                {t('workspace.memoryGuard.saveButton')}
              </Button>
            </div>
          </FormSection>
        ) : null}
      </CardContent>
    </Card>
  )
}
