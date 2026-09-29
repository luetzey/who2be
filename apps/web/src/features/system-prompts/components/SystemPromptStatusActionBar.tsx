import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { VersionStatus } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useNeedsMfaForPublish } from '@/auth/session-context'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { Button } from '@/components/ui/button'
import { MfaPublishNotice, ViewChangesLink } from '@/components/version/StatusActionBar'
import { notify } from '@/lib/feedback'

interface SystemPromptStatusActionBarProps {
  templateId: string
  version: number
  status: VersionStatus
  onTransitioned: () => void
  // Audit E1 = A: im Status „In review" verlinkt die Leiste den Diff dieser
  // Version (`?tab=versions&diff=<n>`, gleicher Pfad) — wie die zentrale
  // `StatusActionBar`. Ohne Wert entfaellt der Link.
  diffVersion?: number
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
  diffVersion,
}: SystemPromptStatusActionBarProps) {
  const { t } = useTranslation('systemPrompts')
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const needsMfa = useNeedsMfaForPublish()
  const [busy, setBusy] = useState<VersionStatus | null>(null)

  const transition = async (to: VersionStatus, success: string) => {
    setBusy(to)
    try {
      await api.transitionSystemPromptTemplateVersion(templateId, version, to)
      notify.success(success)
      onTransitioned()
    } catch (cause: unknown) {
      const message =
        cause instanceof Error ? cause.message : t('statusBar.toast.actionFailed')
      notify.error(message)
    } finally {
      setBusy(null)
    }
  }

  const canPromote = role === 'admin'
  // Audit A1: dieselbe MFA-Vorankuendigung wie die zentrale StatusActionBar.
  const promoteNeedsMfa = canPromote && needsMfa
  // State-Machine: draft → review; review → active|draft; inactive → draft.
  if (status === 'draft') {
    return (
      <div role="toolbar" aria-label={t('statusBar.ariaLabel')} className="flex gap-2">
        <Button
          type="button"
          variant="default"
          disabled={busy !== null}
          onClick={() => void transition('review', t('statusBar.toast.submittedForReview'))}
        >
          {t('statusBar.submitForReview')}
        </Button>
      </div>
    )
  }
  if (status === 'review') {
    return (
      <div role="toolbar" aria-label={t('statusBar.ariaLabel')} className="flex flex-wrap items-center gap-2">
        {promoteNeedsMfa ? (
          <MfaPublishNotice />
        ) : (
          <Button
            type="button"
            variant="brand"
            disabled={busy !== null || !canPromote}
            title={canPromote ? undefined : t('statusBar.adminOnlyTooltip')}
            onClick={() => void transition('active', t('statusBar.toast.activated'))}
          >
            {t('statusBar.activate')}
          </Button>
        )}
        {/* Audit A2: umkehrbar, nicht destruktiv (design-language §9.1). */}
        <Button
          type="button"
          variant="outline"
          disabled={busy !== null}
          onClick={() => void transition('draft', t('statusBar.toast.backToDraft'))}
        >
          {t('statusBar.backToDraft')}
        </Button>
        {diffVersion !== undefined ? <ViewChangesLink version={diffVersion} /> : null}
      </div>
    )
  }
  if (status === 'inactive') {
    return (
      <div role="toolbar" aria-label={t('statusBar.ariaLabel')} className="flex gap-2">
        <Button
          type="button"
          variant="default"
          disabled={busy !== null}
          onClick={() => void transition('draft', t('statusBar.toast.reactivatedAsDraft'))}
        >
          {t('statusBar.reactivateAsDraft')}
        </Button>
      </div>
    )
  }
  return null
}
