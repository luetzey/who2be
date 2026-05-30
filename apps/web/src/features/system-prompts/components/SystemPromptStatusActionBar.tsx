import { useState } from 'react'

import type { VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

interface SystemPromptStatusActionBarProps {
  templateId: string
  version: number
  status: VersionStatus
  onTransitioned: () => void
}

/**
 * Status-Action-Bar fuer SystemPromptTemplate-Versionen (analog
 * `personas/StatusActionBar`). Lebt im eigenen Feature-Ordner — Cross-
 * Feature-Imports sind durch ESLint blockiert.
 */
export function SystemPromptStatusActionBar({
  templateId,
  version,
  status,
  onTransitioned,
}: SystemPromptStatusActionBarProps) {
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const [busy, setBusy] = useState<VersionStatus | null>(null)

  const transition = async (to: VersionStatus, success: string) => {
    setBusy(to)
    try {
      await api.transitionSystemPromptTemplateVersion(templateId, version, to)
      notify.success(success)
      onTransitioned()
    } catch (cause: unknown) {
      const message =
        cause instanceof Error ? cause.message : 'Aktion fehlgeschlagen.'
      notify.error(message)
    } finally {
      setBusy(null)
    }
  }

  const canPromote = role === 'admin'
  // State-Machine: draft → review; review → active|draft; inactive → draft.
  if (status === 'draft') {
    return (
      <div role="toolbar" aria-label="Status-Aktionen" className="flex gap-2">
        <Button
          type="button"
          variant="default"
          disabled={busy !== null}
          onClick={() => void transition('review', 'Zur Review eingereicht.')}
        >
          Zur Review einreichen
        </Button>
      </div>
    )
  }
  if (status === 'review') {
    return (
      <div role="toolbar" aria-label="Status-Aktionen" className="flex gap-2">
        <Button
          type="button"
          variant="brand"
          disabled={busy !== null || !canPromote}
          title={canPromote ? undefined : 'Nur Admins können aktivieren'}
          onClick={() => void transition('active', 'Version aktiviert.')}
        >
          Aktivieren
        </Button>
        <Button
          type="button"
          variant="destructive"
          disabled={busy !== null}
          onClick={() => void transition('draft', 'Zurück in den Entwurf.')}
        >
          Zurück zu Draft
        </Button>
      </div>
    )
  }
  if (status === 'inactive') {
    return (
      <div role="toolbar" aria-label="Status-Aktionen" className="flex gap-2">
        <Button
          type="button"
          variant="default"
          disabled={busy !== null}
          onClick={() => void transition('draft', 'Als Draft reaktiviert.')}
        >
          Als Draft reaktivieren
        </Button>
      </div>
    )
  }
  return null
}
