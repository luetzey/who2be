import { Copy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import type { SystemPromptTemplate } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

interface DuplicateSystemPromptButtonProps {
  template: SystemPromptTemplate
}

/**
 * Dupliziert eine System-Prompt-Vorlage ueber `POST
 * /system-prompts/{id}/duplicate` (Deep-Copy des Inhalts als frische Draft) und
 * navigiert zur Kopie. Ausgegraut fuer Viewer — das Backend lehnt die Mutation
 * sonst ohnehin ab (403). Muster analog `DuplicateAgentButton`.
 */
export function DuplicateSystemPromptButton({ template }: DuplicateSystemPromptButtonProps) {
  const { t } = useTranslation('systemPrompts')
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
      const created = await api.duplicateSystemPrompt(template.id)
      notify.success(t('duplicate.success'))
      navigate(wsPath(`/system-prompts/${created.id}`))
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
      data-testid="duplicate-system-prompt"
    >
      <Copy className="h-4 w-4" />
      {t('duplicate.label')}
    </Button>
  )
}
