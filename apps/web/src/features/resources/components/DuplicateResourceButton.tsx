import { Copy } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import type { Resource } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'

interface DuplicateResourceButtonProps {
  resource: Resource
}

/**
 * Dupliziert eine Resource ueber `POST /resources/{id}/duplicate` (Deep-Copy
 * inkl. Sub-Resource-Links) und navigiert zur Kopie. Fuer Viewer ausgegraut —
 * Duplizieren legt einen neuen Entwurf an und ist damit eine Schreib-Aktion.
 */
export function DuplicateResourceButton({ resource }: DuplicateResourceButtonProps) {
  const { t } = useTranslation('resources')
  const api = useApi()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const [busy, setBusy] = useState(false)

  const onCopy = async () => {
    setBusy(true)
    try {
      const created = await api.duplicateResource(resource.id)
      notify.success(t('toast.duplicated'))
      navigate(wsPath(`/resources/${created.id}`))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('toast.duplicateError'))
      setBusy(false)
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      disabled={isViewer || busy}
      title={isViewer ? t('delete.viewerReadOnly') : undefined}
      onClick={() => void onCopy()}
      data-testid="duplicate-resource"
    >
      <Copy className="h-4 w-4" />
      {t('detail.duplicate')}
    </Button>
  )
}
