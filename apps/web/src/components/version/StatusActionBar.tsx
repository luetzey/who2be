import { useState } from 'react'
import { ShieldAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import type { VersionStatus } from '@/api/types'
import { useNeedsMfaForPublish } from '@/auth/session-context'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import { notify } from '@/lib/feedback'
import { extractMissingFields, formatMissingFields } from '@/lib/promoteError'

import { canTransition } from './versionStatus'

// Hinweis + Weg zur Einrichtung, an der Stelle des Publish-Knopfs (Audit A1,
// Owner-Entscheidung E5 = A; Bedingung siehe `useNeedsMfaForPublish`).
// Geteilt von dieser Leiste und `SystemPromptStatusActionBar`
// (Cross-Feature-Import ist verboten, `@/components/version` ist der
// gemeinsame Ort).
export function MfaPublishNotice() {
  const { t } = useTranslation('common')
  const wsPath = useWorkspacePath()
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="publish-mfa-notice">
      <span className="flex items-center gap-1.5 text-sm text-foreground">
        <ShieldAlert className="size-4 shrink-0" aria-hidden="true" />
        {t('statusBar.mfa.notice')}
      </span>
      <Button asChild variant="outline">
        <Link to={wsPath('/settings/account')}>{t('statusBar.mfa.setup')}</Link>
      </Button>
    </div>
  )
}

// Die vier Aktionen, die diese Bar ueberhaupt kennt (siehe showSubmit/
// showPromote/showReject/showReactivate unten) — Basis fuer den optionalen
// Label-Override und fuer das Testid-Schema `branch-action-<suffix>`.
export type StatusActionKey = 'submit' | 'promote' | 'reject' | 'reactivate'

// Testid-Suffixe uebernehmen exakt das an components/data/BranchStatus.tsx
// (BranchAction.key) etablierte Schema, an das `e2e/journeys.spec.ts` bindet
// — die Promote-Aktion heisst dort historisch "publish", nicht "promote".
const TESTID_SUFFIX: Record<StatusActionKey, string> = {
  submit: 'submit',
  promote: 'publish',
  reject: 'reject',
  reactivate: 'reactivate',
}

interface StatusActionBarProps {
  status: VersionStatus
  // Promise<unknown>: die api.transition*Version-Methoden liefern teils die
  // aktualisierte Version zurueck — die Bar ignoriert den Wert.
  onTransition: (to: VersionStatus) => Promise<unknown>
  onTransitioned: () => void
  // Optionaler Label-Override je Aktion — Default bleiben die geteilten
  // `common:statusBar.*`-Texte. Aufrufer mit eigenen (historisch gewachsenen)
  // Button-Texten (z. B. Personas/Playbooks) uebergeben hier ihre Keys, ohne
  // dass sich Verhalten oder Testids aendern (Issue #391).
  labels?: Partial<Record<StatusActionKey, string>>
}

// Aktionen pro Status laut §2.1.F. Reihenfolge: Promote (primary) vor
// Submit (secondary) vor Reject (destructive). Buttons werden nur
// gerendert wenn der Uebergang aus dem aktuellen Status erlaubt ist —
// dadurch faellt die Bar bei active/inactive automatisch weg.
export function StatusActionBar({
  status,
  onTransition,
  onTransitioned,
  labels,
}: StatusActionBarProps) {
  const { t } = useTranslation('common')
  const role = useCurrentWorkspaceRole()
  const needsMfa = useNeedsMfaForPublish()
  const [busy, setBusy] = useState<VersionStatus | null>(null)
  const [promoteError, setPromoteError] = useState<string | null>(null)

  const transition = async (to: VersionStatus, success: string) => {
    setBusy(to)
    setPromoteError(null)
    try {
      await onTransition(to)
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
  // Nur wer ueberhaupt veroeffentlichen duerfte, bekommt den MFA-Hinweis —
  // ein Editor sieht weiter den gesperrten Knopf mit dem Admin-Tooltip.
  const promoteNeedsMfa = showPromote && canPromote && needsMfa

  return (
    <div className="flex flex-col gap-2">
      <div
        className="flex flex-wrap items-center gap-2"
        role="toolbar"
        aria-label={t('statusBar.ariaLabel')}
      >
        {promoteNeedsMfa ? <MfaPublishNotice /> : null}
        {showPromote && !promoteNeedsMfa ? (
          <Button
            type="button"
            variant="brand"
            data-testid={`branch-action-${TESTID_SUFFIX.promote}`}
            onClick={() => void transition('active', t('statusBar.toast.activated'))}
            disabled={busy !== null || !canPromote}
            title={canPromote ? undefined : t('statusBar.adminOnly')}
          >
            {labels?.promote ?? t('statusBar.promote')}
          </Button>
        ) : null}
        {showSubmit ? (
          <Button
            type="button"
            variant="default"
            data-testid={`branch-action-${TESTID_SUFFIX.submit}`}
            onClick={() => void transition('review', t('statusBar.toast.submitted'))}
            disabled={busy !== null}
          >
            {labels?.submit ?? t('statusBar.submit')}
          </Button>
        ) : null}
        {showReject ? (
          // Audit A2: „Zurueck zu Draft" ist jederzeit umkehrbar — keine
          // destruktive Aktion (design-language §9.1), also `outline`.
          <Button
            type="button"
            variant="outline"
            data-testid={`branch-action-${TESTID_SUFFIX.reject}`}
            onClick={() => void transition('draft', t('statusBar.toast.rejected'))}
            disabled={busy !== null}
          >
            {labels?.reject ?? t('statusBar.reject')}
          </Button>
        ) : null}
        {showReactivate ? (
          <Button
            type="button"
            variant="outline"
            data-testid={`branch-action-${TESTID_SUFFIX.reactivate}`}
            onClick={() => void transition('draft', t('statusBar.toast.reactivated'))}
            disabled={busy !== null}
          >
            {labels?.reactivate ?? t('statusBar.reactivate')}
          </Button>
        ) : null}
      </div>
      {promoteError !== null ? (
        <ErrorAlert message={promoteError} title={t('statusBar.error.promoteTitle')} />
      ) : null}
    </div>
  )
}
