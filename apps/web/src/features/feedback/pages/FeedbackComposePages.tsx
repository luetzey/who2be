import { ArrowLeft } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import type { FeedbackTarget } from '@/api/types'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ReportCaseFlow, type ReportCaseState } from '@/components/cases/ReportCaseForm'
import {
  GiveFeedbackForm,
  type FeedbackComposeState,
} from '@/components/feedback/GiveFeedbackDialog'
import { Container } from '@/components/layout/Container'
import { PageHeader } from '@/components/layout/PageHeader'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { useGiveFeedbackForm, useReportProblemForm } from '@/hooks/useFeedbackForms'

import { ReportProblemForm } from '../components/ReportProblemDialog'
import { DETAIL_SEGMENT } from '../lib/entityMeta'

// Mobil-Spec W4=b (R-P3): „Feedback geben“ und „Problem melden“ unterhalb
// `md` als eigene Vollbildseite statt Dialog; „Fall melden“ ebenso (Delta-Spec
// S6 „390 px“, D6c′). Ab `md` oeffnen die Ausloeser
// weiter den Dialog; die Routen selbst funktionieren auf jeder Breite
// (Deep-Link, Drehen des Geraets).
//
// Zurueck-Fluss: Kam der Nutzer ueber den Ausloeser (`state.from` gesetzt),
// geht Zurueck/Abbrechen/Absenden einen Schritt in der History zurueck —
// genau wie der Browser-Zurueck-Knopf, mit erhaltener Query (`?tab=`) und
// ohne doppelten History-Eintrag. Ohne `state.from` (Deep-Link, Reload in
// neuem Tab) ersetzt die Seite sich durch das Fallback-Ziel.

function useLeave(fallback: string): () => void {
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as FeedbackComposeState | null)?.from
  return () => {
    if (from !== undefined) navigate(-1)
    else navigate(fallback, { replace: true })
  }
}

function PageFooter({ children }: { children: ReactNode }) {
  return <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">{children}</div>
}

interface ComposeShellProps {
  title: string
  description?: string
  onLeave: () => void
  children: ReactNode
}

function ComposeShell({ title, description, onLeave, children }: ComposeShellProps) {
  const { t } = useTranslation('common')
  return (
    <Container>
      <Stack gap="md">
        <Button
          type="button"
          variant="ghost"
          className="w-fit gap-2 text-muted-foreground"
          onClick={onLeave}
          data-testid="feedback-compose-back"
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          {t('actions.back')}
        </Button>
        <PageHeader title={title} description={description} />
        {children}
      </Stack>
    </Container>
  )
}

function isFeedbackTarget(value: string | undefined): value is FeedbackTarget {
  return value !== undefined && Object.hasOwn(DETAIL_SEGMENT, value)
}

/** Vollbildseite „Feedback geben“ (`/feedback/give/:entityType/:entityId`). */
export function GiveFeedbackPage() {
  const { entityType, entityId } = useParams<{ entityType: string; entityId: string }>()
  const wsPath = useWorkspacePath()
  if (!isFeedbackTarget(entityType) || entityId === undefined) {
    return <Navigate to={wsPath('/feedback')} replace />
  }
  return <GiveFeedbackPageBody entityType={entityType} entityId={entityId} />
}

function GiveFeedbackPageBody({
  entityType,
  entityId,
}: {
  entityType: FeedbackTarget
  entityId: string
}) {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const location = useLocation()
  const [params] = useSearchParams()
  const name = (location.state as FeedbackComposeState | null)?.name
  const rawVersion = Number(params.get('version'))
  const version = Number.isInteger(rawVersion) && rawVersion > 0 ? rawVersion : undefined
  const leave = useLeave(wsPath(`/${DETAIL_SEGMENT[entityType]}/${entityId}`))
  const form = useGiveFeedbackForm({ entityType, entityId, version }, leave)

  return (
    <ComposeShell
      title={t('give.title')}
      // Ohne Namen (Deep-Link) keine Beschreibung statt einer UUID im Satz.
      description={name === undefined ? undefined : t('give.description', { name })}
      onLeave={leave}
    >
      <GiveFeedbackForm
        form={form}
        Footer={PageFooter}
        cancel={
          <Button type="button" variant="outline" disabled={form.busy} onClick={leave}>
            {t('common:actions.cancel')}
          </Button>
        }
      />
    </ComposeShell>
  )
}

/** Vollbildseite „Problem melden“ (`/feedback/report`). */
export function ReportProblemPage() {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const leave = useLeave(wsPath('/feedback'))
  const form = useReportProblemForm(leave)

  return (
    <ComposeShell
      title={t('report.dialogTitle')}
      description={t('report.dialogDescription')}
      onLeave={leave}
    >
      <ReportProblemForm
        form={form}
        Footer={PageFooter}
        cancel={
          <Button type="button" variant="outline" disabled={form.busy} onClick={leave}>
            {t('common:actions.cancel')}
          </Button>
        }
      />
    </ComposeShell>
  )
}

// Knopfleiste der Melden-Seite unten fixiert (Delta-Spec S6 „390 px“): bleibt
// beim Scrollen durch lange Felder erreichbar; Abstand fuer die Home-Leiste.
function StickyFooter({ children }: { children: ReactNode }) {
  return (
    <div
      data-testid="report-case-footer"
      className="sticky bottom-0 z-10 flex flex-col-reverse gap-2 border-t bg-background pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:flex-row sm:justify-end"
    >
      {children}
    </div>
  )
}

/**
 * Vollbildseite „Fall melden“ (`/feedback/cases/new?agent=<id>`, Delta-Spec
 * S6 „390 px“, D6c′). Ausloeser ist `ReportCaseDialog` unter `md`. Kommt der
 * Name des Agenten ueber den Navigations-State, ist er fest (Einstieg
 * Agent-Detail); bei einem Deep-Link ist `?agent=` nur eine Vorauswahl.
 * Zurueck, Abbrechen und Erfolg verlassen die Seite wie die anderen
 * Vollbildseiten; ohne Herkunft geht es zur Fall-Liste.
 */
export function ReportCasePage() {
  const { t } = useTranslation('feedback')
  const wsPath = useWorkspacePath()
  const location = useLocation()
  const [params] = useSearchParams()
  const agentId = params.get('agent') ?? undefined
  const agentName = (location.state as ReportCaseState | null)?.agentName
  const leave = useLeave(wsPath('/feedback?tab=cases'))
  const fixed =
    agentId !== undefined && agentName !== undefined ? { id: agentId, name: agentName } : undefined

  return (
    <ReportCaseFlow
      agent={fixed}
      presetAgentId={fixed === undefined ? agentId : undefined}
      onClose={leave}
      Footer={StickyFooter}
      frame={({ body, discard, requestClose }) => (
        <ComposeShell
          title={t('cases.report.title')}
          description={t('cases.report.intro')}
          onLeave={requestClose}
        >
          {body}
          {discard}
        </ComposeShell>
      )}
    />
  )
}
