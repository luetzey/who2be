import { Bot, ExternalLink, History, User } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'

import type { FeedbackResolution, FeedbackTarget } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DetailHeader } from '@/components/data'
import { DataView } from '@/components/data/DataView'
import { DeleteFeedbackButton } from '@/components/feedback/DeleteFeedbackButton'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

import { ResolutionSegments } from '../components/ResolutionSegments'
import { useFeedbackDetail } from '../hooks/useFeedbackDetail'
import { DETAIL_SEGMENT, entityMeta } from '../lib/entityMeta'

// Negative Inhalts-Signale + jedes System-Feedback tragen den destructive-Ton.
const NEGATIVE: readonly string[] = ['outdated', 'incorrect', 'unclear']

// Punkt-Tinte je Triage-Status (nie alleiniges Signal — immer mit Text-Label,
// Design-Language §11). Werte aus den Pill-Tokens in globals.css.
const STATUS_DOT: Record<FeedbackResolution | 'open', string> = {
  open: 'bg-muted-foreground/40',
  in_progress: 'bg-pill-date-fg',
  addressed: 'bg-pill-resource-fg',
  dismissed: 'bg-muted-foreground/50',
}

// StatusBadge-artiger Chip fuer den aktuellen Triage-Stand eines Feedbacks.
function ResolutionChip({
  resolution,
  label,
}: {
  resolution: FeedbackResolution | 'open'
  label: string
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/40 px-2 py-0.5 text-xs font-medium text-muted-foreground">
      <span className={cn('inline-block size-2 rounded-full', STATUS_DOT[resolution])} aria-hidden="true" />
      {label}
    </span>
  )
}

// Eine Zeile der „Bezug"-Definitionsliste (Label links, Wert rechts).
function DefRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="flex-none text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right font-medium">{children}</dd>
    </div>
  )
}

/**
 * Detailseite eines EINZELNEN Feedbacks (ADR-0038-Folge): worauf es sich
 * bezieht, wie es verlinkt wurde, Signal + Notiz, aktueller Triage-Status und
 * der vollstaendige Verlauf. Datenquelle ist `useFeedbackDetail`
 * (`GET …/feedback/{feedbackId}`); Triage/Delete laufen ueber `useApi()` und
 * laden das Detail neu, damit der Verlauf das neue Ereignis spiegelt.
 */
export function FeedbackItemDetailPage() {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const navigate = useNavigate()
  const api = useApi()
  const { feedbackId } = useParams<{ feedbackId: string }>()

  const { detail, loading, error, reload } = useFeedbackDetail(feedbackId)

  if (feedbackId === undefined) {
    return <Navigate to={wsPath('/feedback')} replace />
  }

  const onResolution = async (value: FeedbackResolution) => {
    try {
      await api.setFeedbackResolution(feedbackId, { resolution: value })
      reload()
    } catch {
      notify.error(t('resolution.error'))
    }
  }

  const onDelete = async () => {
    await api.deleteFeedback(feedbackId)
    navigate(wsPath('/feedback'))
  }

  // Ableitungen erst berechnen, wenn das Detail geladen ist.
  const isSystem = detail?.entity_type === 'system'
  const meta = detail !== null ? entityMeta(detail.entity_type) : entityMeta('system')
  const typeLabel = detail !== null ? t(`overview.type.${detail.entity_type}`) : ''
  const signalLabel =
    detail !== null
      ? isSystem
        ? t(`systemCategory.${detail.signal}`)
        : t(`signal.${detail.signal}`)
      : ''
  const isNegative = detail !== null && (NEGATIVE.includes(detail.signal) || isSystem)
  const elementPath =
    detail !== null && detail.entity_id !== null && !isSystem
      ? wsPath(`/${DETAIL_SEGMENT[detail.entity_type as FeedbackTarget]}/${detail.entity_id}`)
      : null
  const currentStatus: FeedbackResolution | 'open' = detail?.resolution ?? 'open'
  const title =
    detail !== null ? t('itemDetail.title', { signal: signalLabel, name: detail.name }) : ''

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6">
      <DetailHeader
        icon={meta.icon}
        iconTone={meta.tone}
        title={title !== '' ? title : t('itemDetail.fallbackTitle')}
        backHref={wsPath('/feedback')}
        backLabel={t('overview.title')}
        description={t('itemDetail.description')}
        badges={
          detail !== null ? (
            <span className="flex flex-wrap items-center gap-2">
              <Badge variant={isNegative ? 'destructive' : 'secondary'}>
                <span
                  className="mr-1 inline-block size-1.5 rounded-full bg-current"
                  aria-hidden="true"
                />
                {signalLabel}
              </Badge>
              <ResolutionChip
                resolution={currentStatus}
                label={t(`inbox.status.${currentStatus}`)}
              />
            </span>
          ) : undefined
        }
        actions={
          detail !== null ? (
            <>
              {elementPath !== null ? (
                <Button asChild variant="outline">
                  <Link to={elementPath}>
                    <ExternalLink />
                    {t('itemDetail.openElement')}
                  </Link>
                </Button>
              ) : null}
              <DeleteFeedbackButton entityName={detail.name} onConfirm={onDelete} />
            </>
          ) : undefined
        }
      />

      <DataView loading={loading && detail === null} error={error}>
        {detail !== null ? (
          <div className="flex flex-col gap-6">
            <div className="grid gap-6 md:grid-cols-2">
              {/* Bezug — worauf sich das Feedback bezieht und wie es verlinkt ist. */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('itemDetail.bezugTitle')}</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="flex flex-col gap-3 text-sm">
                    <DefRow label={t('itemDetail.type')}>{typeLabel}</DefRow>
                    <DefRow label={t('itemDetail.element')}>
                      {elementPath !== null ? (
                        <Link to={elementPath} className="text-brand hover:underline">
                          {detail.name}
                        </Link>
                      ) : isSystem ? (
                        <span className="text-muted-foreground">{t('itemDetail.noElement')}</span>
                      ) : (
                        detail.name
                      )}
                    </DefRow>
                    <DefRow label={t('itemDetail.version')}>
                      {detail.version !== null ? `v${detail.version}` : '—'}
                    </DefRow>
                    <DefRow label={t('itemDetail.source')}>
                      <span className="inline-flex items-center gap-1.5">
                        {detail.agent_id !== null ? (
                          <Bot className="size-3.5 text-muted-foreground" aria-hidden="true" />
                        ) : (
                          <User className="size-3.5 text-muted-foreground" aria-hidden="true" />
                        )}
                        {detail.agent_id !== null ? t('panel.agent') : t('panel.human')}
                      </span>
                    </DefRow>
                    <DefRow label={t('itemDetail.submitted')}>
                      {new Date(detail.created_at).toLocaleString()}
                    </DefRow>
                  </dl>
                </CardContent>
              </Card>

              {/* Signal & Notiz — das gemeldete Signal und der Absender-Text. */}
              <Card>
                <CardHeader>
                  <CardTitle>{t('itemDetail.signalTitle')}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                      {t('itemDetail.signalLabel')}
                    </span>
                    <Badge variant={isNegative ? 'destructive' : 'secondary'}>{signalLabel}</Badge>
                  </div>
                  {detail.note !== null && detail.note !== '' ? (
                    <p className="border-l-2 border-border pl-3 text-sm text-foreground/90">
                      {detail.note}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">{t('itemDetail.noteEmpty')}</p>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Status & Triage — Bearbeitungsstand aendern. */}
            <Card>
              <CardHeader>
                <CardTitle>{t('itemDetail.statusTitle')}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                    {t('itemDetail.statusCurrent')}
                  </span>
                  <ResolutionSegments
                    name={detail.name}
                    value={detail.resolution}
                    onChange={(r) => void onResolution(r)}
                  />
                </div>
                <p className="text-xs text-muted-foreground">{t('itemDetail.statusHint')}</p>
              </CardContent>
            </Card>

            {/* Verlauf — WANN es bearbeitet/erledigt wurde (neueste zuerst). */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <History className="size-4 text-muted-foreground" aria-hidden="true" />
                  {t('itemDetail.historyTitle')}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <DataView empty={detail.history.length === 0} emptyTitle={t('itemDetail.historyEmpty')}>
                  {detail.history.length > 0 ? (
                    <ul className="flex flex-col divide-y">
                      {[...detail.history].reverse().map((ev, index) => {
                        const actorLabel =
                          ev.actor_id !== null
                            ? t('itemDetail.history.actorHuman')
                            : t('itemDetail.history.actorSystem')
                        return (
                          <li
                            key={`${ev.created_at}-${index}`}
                            className="flex flex-col gap-2 py-4 first:pt-0 last:pb-0"
                          >
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                              <ResolutionChip
                                resolution={ev.resolution}
                                label={t(`inbox.status.${ev.resolution}`)}
                              />
                              <span className="text-xs text-muted-foreground">{actorLabel}</span>
                              <span className="ml-auto text-xs text-muted-foreground">
                                {new Date(ev.created_at).toLocaleString()}
                              </span>
                            </div>
                            {ev.note !== null && ev.note !== '' ? (
                              <p className="border-l-2 border-border pl-3 text-sm text-foreground/90">
                                {ev.note}
                              </p>
                            ) : null}
                          </li>
                        )
                      })}
                    </ul>
                  ) : null}
                </DataView>
              </CardContent>
            </Card>
          </div>
        ) : null}
      </DataView>
    </div>
  )
}
