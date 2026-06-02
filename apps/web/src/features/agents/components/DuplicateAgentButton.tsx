import { Copy } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { Agent } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

import { isAgentShell } from '../lib/shell'

interface DuplicateAgentButtonProps {
  agent: Agent
}

/**
 * Dupliziert einen Agent ueber `POST /agents/{id}/copy` und navigiert zur
 * Kopie. Ausgegraut, solange der Agent eine unvollstaendige Huelle ist
 * (Backend antwortet sonst 409) oder der User nur Viewer ist.
 */
export function DuplicateAgentButton({ agent }: DuplicateAgentButtonProps) {
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const shell = isAgentShell(agent)
  const [busy, setBusy] = useState(false)

  const disabled = isViewer || shell || busy
  const title = shell
    ? 'Unvollständige Hülle kann nicht dupliziert werden — erst Persona und Systemprompt zuweisen.'
    : isViewer
      ? 'Viewer können Agents nur ansehen'
      : undefined

  const onCopy = async () => {
    setBusy(true)
    try {
      const created = await api.copyAgent(agent.id)
      notify.success('Agent dupliziert.')
      navigate(wsPath(`/agents/${created.id}`))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : 'Duplizieren fehlgeschlagen.')
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
      Duplizieren
    </Button>
  )
}
