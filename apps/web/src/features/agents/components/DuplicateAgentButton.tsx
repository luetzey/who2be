import { Copy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

import { describeAgentMissing } from '../lib/activation'

interface DuplicateAgentButtonProps {
  agent: Agent
}

/**
 * Dupliziert einen Agent ueber `POST /agents/{id}/copy` und navigiert zur
 * Kopie. Ausgegraut, solange der Agent nicht aktivierbar ist (Persona/Template
 * fehlt ODER Persona nicht aktiv — Backend antwortet sonst 409) oder der User
 * nur Viewer ist. Der Tooltip nennt die konkreten Luecken.
 */
export function DuplicateAgentButton({ agent }: DuplicateAgentButtonProps) {
  const { t } = useTranslation('agents')
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [busy, setBusy] = useState(false)

  const disabled = isViewer || !agent.activatable || busy
  const title = !agent.activatable
    ? t('duplicate.notCopyable', { items: describeAgentMissing(agent.missing).join(', ') })
    : isViewer
      ? t('duplicate.viewerReadOnly')
      : undefined

  const onCopy = async () => {
    setBusy(true)
    try {
      const created = await api.copyAgent(agent.id)
      notify.success(t('duplicate.success'))
      navigate(wsPath(`/agents/${created.id}`))
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
      data-testid="duplicate-agent"
    >
      <Copy className="h-4 w-4" />
      {t('duplicate.label')}
    </Button>
  )
}
