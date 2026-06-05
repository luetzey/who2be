import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'
import { extractMissingFields, formatMissingFields } from '@/lib/promoteError'

import { canTransition } from '../lib/status'

interface StatusActionBarProps {
  personaId: string
  version: number
  status: VersionStatus
  onTransitioned: () => void
}

// Aktionen pro Status laut §2.1.F. Reihenfolge: Promote (primary) vor
// Submit (secondary) vor Reject (destructive). Buttons werden nur
// gerendert wenn der Uebergang aus dem aktuellen Status erlaubt ist —
// dadurch faellt die Bar bei active/inactive automatisch weg.
export function StatusActionBar({
  personaId,
  version,
  status,
  onTransitioned,
}: StatusActionBarProps) {
  const { t } = useTranslation('personas')
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const [busy, setBusy] = useState<VersionStatus | null>(null)
  const [promoteError, setPromoteError] = useState<string | null>(null)

  const transition = async (to: VersionStatus, success: string) => {
    setBusy(to)
    setPromoteError(null)
    try {
      await api.transitionPersonaVersion(personaId, version, to)
      notify.success(success)
      onTransitioned()
    } catch (cause: unknown) {
      // 409 Promote-Validation-Fail: Feldnamen inline anzeigen (Welle 4).
      const missing = extractMissingFields(cause)
      if (missing !== null) {
        setPromoteError(
          t('statusBar.error.promoteFill', { fields: formatMissingFields(missing) }),
        )
      } else {
        const message = cause instanceof Error ? cause.message : t('statusBar.fallback')
        notify.error(message)
      }
    } finally {
      setBusy(null)
    }
  }

  const showSubmit = canTransition(status, 'review')
  const showPromote = canTransition(status, 'active')
  const showReject = status === 'review' && canTransition(status, 'draft')
  const showReactivate = status === 'inactive' && canTransition(status, 'draft')

  if (!showSubmit && !showPromote && !showReject && !showReactivate) {
    return null
  }

  // Promote (Review → Active) ist Admin-only (ADR-0023, Reviewer-Rolle).
  const canPromote = role === 'admin'

  return (
    <div className="flex flex-col gap-2">
      <div
        className="flex flex-wrap items-center gap-2"
        role="toolbar"
        aria-label={t('statusBar.ariaLabel')}
      >
        {showPromote ? (
          <Button
            type="button"
            variant="brand"
            onClick={() => void transition('active', t('statusBar.toast.activated'))}
            disabled={busy !== null || !canPromote}
            title={canPromote ? undefined : t('statusBar.adminOnly')}
          >
            {t('statusBar.promote')}
          </Button>
        ) : null}
        {showSubmit ? (
          <Button
            type="button"
            variant="default"
            onClick={() => void transition('review', t('statusBar.toast.submitted'))}
            disabled={busy !== null}
          >
            {t('statusBar.submit')}
          </Button>
        ) : null}
        {showReject ? (
          <Button
            type="button"
            variant="destructive"
            onClick={() => void transition('draft', t('statusBar.toast.rejected'))}
            disabled={busy !== null}
          >
            {t('statusBar.reject')}
          </Button>
        ) : null}
        {showReactivate ? (
          <Button
            type="button"
            variant="outline"
            onClick={() => void transition('draft', t('statusBar.toast.reactivated'))}
            disabled={busy !== null}
          >
            {t('statusBar.reactivate')}
          </Button>
        ) : null}
      </div>
      {promoteError !== null ? (
        <ErrorAlert message={promoteError} title={t('statusBar.error.promoteTitle')} />
      ) : null}
    </div>
  )
}
