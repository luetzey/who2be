import { Copy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import type { Persona } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

interface DuplicatePersonaButtonProps {
  persona: Persona
}

/**
 * Dupliziert eine Persona ueber `POST /personas/{id}/duplicate` (Deep-Copy des
 * Inhalts als frische Draft) und navigiert zur Kopie. Ausgegraut fuer Viewer —
 * das Backend lehnt die Mutation sonst ohnehin ab (403). Muster analog
 * `DuplicateAgentButton`.
 */
export function DuplicatePersonaButton({ persona }: DuplicatePersonaButtonProps) {
  const { t } = useTranslation('personas')
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [busy, setBusy] = useState(false)

  const disabled = isViewer || busy
  const title = isViewer ? t('duplicate.viewerReadOnly') : undefined

  const onCopy = async () => {
    setBusy(true)
    try {
      const created = await api.duplicatePersona(persona.id)
      notify.success(t('duplicate.success'))
      navigate(wsPath(`/personas/${created.id}`))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('duplicate.error'))
      setBusy(false)
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      disabled={disabled}
      title={title}
      onClick={() => void onCopy()}
      data-testid="duplicate-persona"
    >
      <Copy className="h-4 w-4" />
      {t('duplicate.label')}
    </Button>
  )
}
