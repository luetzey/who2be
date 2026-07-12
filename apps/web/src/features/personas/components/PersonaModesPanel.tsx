import { Layers } from 'lucide-react'
import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'

import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { EntityIcon } from '@/components/data/EntityIcon'
import { Card, CardContent } from '@/components/ui/card'
import { Stack } from '@/components/layout/Stack'

import type { PersonaEditorValues } from '../hooks/usePersonaForm'
import { PersonaModesEditor } from './PersonaModesEditor'

interface PersonaModesPanelProps {
  form: UseFormReturn<PersonaEditorValues>
  /** Vom System verwaltet (Builder) — read-only wie fuer Viewer. */
  locked?: boolean
}

/**
 * „Modi"-Tab der Persona-Detailseite. Situative Verhaltens-Varianten der
 * Persona. Bindet an dieselbe react-hook-form-Instanz wie der „Bearbeiten"-Tab
 * (ein gemeinsamer `<Form>`-Provider auf Page-Ebene, ein Auto-Save fuer beide).
 * Reines Re-Layout — die Modus-Controls kommen unveraendert aus
 * `PersonaModesEditor`.
 */
export function PersonaModesPanel({ form, locked = false }: PersonaModesPanelProps) {
  const { t } = useTranslation('personas')
  const disabled = useCurrentWorkspaceRole() === 'viewer' || locked

  return (
    <Stack gap="md">
      <div className="flex items-center gap-3">
        <EntityIcon icon={Layers} tone="catalog" size="sm" />
        <div className="min-w-0">
          <h2 className="text-base font-semibold tracking-tight">{t('modes.section.title')}</h2>
          <p className="text-sm text-muted-foreground">{t('modes.section.description')}</p>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          <PersonaModesEditor control={form.control} disabled={disabled} />
        </CardContent>
      </Card>
    </Stack>
  )
}
