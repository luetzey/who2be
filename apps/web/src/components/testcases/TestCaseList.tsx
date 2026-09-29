import { Archive, ClipboardCheck, FilePlus2, MoreHorizontal, Plus } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError } from '@/api/client'
import type { Agent, TestCaseRead, VersionedEntityType } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { EmptyState } from '@/components/data/EmptyState'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { LoadingState } from '@/components/data/LoadingState'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { notify } from '@/lib/feedback'

import { TestCaseForm } from './TestCaseForm'

interface TestCaseListProps {
  /**
   * Aufrufort Agent-Detail: alle Prueffaelle dieses Agenten (eigene plus die
   * an seinen Elementen), gruppiert nach Bezug.
   */
  agentId?: string
  /**
   * Aufrufort Element-Detail: die direkt an diesem Element gebundenen
   * Prueffaelle, gruppiert nach Agent.
   */
  entity?: { type: VersionedEntityType; id: string }
  /**
   * Agenten des Workspaces — fuer Gruppen-Ueberschriften und die Agent-
   * Auswahl beim Anlegen am Element. Ohne: Kurz-ID statt Name.
   */
  agents?: readonly Agent[]
  /** Anzeigename des Aufruforts ("Playbook „Implement“") fuer den Kopf. */
  subjectLabel?: string
}

type LoadError = { kind: 'forbidden' } | { kind: 'message'; message: string }

interface Group {
  key: string
  label: string
  cases: TestCaseRead[]
}

function shortId(id: string): string {
  return id.slice(0, 8)
}

/**
 * Prueffaelle je Agent bzw. Element (Spec S10, Lernschleife B4).
 *
 * Prueffaelle sind unveraenderlich (ADR-0053 3.2): statt "Bearbeiten" gibt es
 * "Neue Fassung anlegen" (neuer Prueffall mit `supersedes_id`, der alte wird
 * serverseitig archiviert). Archivieren statt Loeschen — archivierte Faelle
 * bleiben ueber "Archivierte anzeigen" sichtbar.
 *
 * Lesen und Schreiben verlangen serverseitig `editor`; `viewer` sieht einen
 * Rechte-Hinweis statt der Liste, ohne dass ein 403 provoziert wird.
 */
export function TestCaseList({ agentId, entity, agents, subjectLabel }: TestCaseListProps) {
  const { t, i18n } = useTranslation('learning')
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const isViewer = role === 'viewer'
  const [cases, setCases] = useState<TestCaseRead[]>([])
  const [loading, setLoading] = useState(!isViewer)
  const [error, setError] = useState<LoadError | null>(null)
  const [showRetired, setShowRetired] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [supersedes, setSupersedes] = useState<TestCaseRead | null>(null)
  const [retireTarget, setRetireTarget] = useState<TestCaseRead | null>(null)
  const [retiring, setRetiring] = useState(false)
  const headingRef = useRef<HTMLHeadingElement>(null)

  const entityType = entity?.type
  const entityId = entity?.id

  const fetchCases = useCallback(() => {
    // setState nur in Promise-Callbacks — der Effekt unten startet den Abruf,
    // `load` (Ausloeser: Nutzeraktion) setzt zusaetzlich den Ladezustand.
    api
      .listTestCases({ agent_id: agentId, entity_type: entityType, entity_id: entityId })
      .then((data) => {
        setCases(data)
        setError(null)
      })
      .catch((cause: unknown) => {
        if (cause instanceof ApiError && cause.status === 403) {
          setError({ kind: 'forbidden' })
        } else {
          setError({
            kind: 'message',
            message: cause instanceof Error ? cause.message : t('common:errors.unknown'),
          })
        }
      })
      .finally(() => setLoading(false))
  }, [api, agentId, entityType, entityId, t])

  useEffect(() => {
    if (!isViewer) fetchCases()
  }, [fetchCases, isViewer])

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchCases()
  }, [fetchCases])

  const agentName = useCallback(
    (id: string) => agents?.find((agent) => agent.id === id)?.name ?? shortId(id),
    [agents],
  )

  const active = cases.filter((c) => c.status === 'active')
  const retiredCount = cases.length - active.length
  const visible = showRetired ? cases : active

  const groups = useMemo<Group[]>(() => {
    const byKey = new Map<string, Group>()
    for (const testCase of visible) {
      let key: string
      let label: string
      if (entity) {
        // Am Element: gruppiert nach Agent, fuer den der Prueffall laeuft.
        key = testCase.agent_id
        label = t('testCases.group.agent', { name: agentName(testCase.agent_id) })
      } else if (testCase.entity_type && testCase.entity_id) {
        key = `${testCase.entity_type}:${testCase.entity_id}`
        label = t('testCases.group.entity', {
          type: t(`testCases.entityType.${testCase.entity_type}`),
          id: shortId(testCase.entity_id),
        })
      } else {
        key = 'agent'
        label = t('testCases.group.agentItself')
      }
      const group = byKey.get(key) ?? { key, label, cases: [] }
      group.cases.push(testCase)
      byKey.set(key, group)
    }
    return [...byKey.values()]
  }, [visible, entity, agentName, t])

  const canWrite = role !== null && role !== 'viewer'
  const dateFormat = useMemo(
    () => new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium' }),
    [i18n.language],
  )

  const openCreate = () => {
    setSupersedes(null)
    setFormOpen(true)
  }

  const openSupersede = (testCase: TestCaseRead) => {
    setSupersedes(testCase)
    setFormOpen(true)
  }

  const onRetire = async () => {
    if (!retireTarget) return
    setRetiring(true)
    try {
      await api.retireTestCase(retireTarget.id)
      notify.success(t('testCases.retire.success'))
      setRetireTarget(null)
      load()
      // Fokus nie auf `body` fallen lassen (Spec §1 A11y): zurueck zum
      // Listenkopf, die Zeile verschwindet aus der aktiven Liste.
      headingRef.current?.focus()
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('testCases.retire.error'))
    } finally {
      setRetiring(false)
    }
  }

  const createButton = canWrite ? (
    <Button type="button" variant="brand" onClick={openCreate} className="w-full sm:w-auto">
      <Plus className="h-4 w-4" aria-hidden="true" />
      {t('testCases.create')}
    </Button>
  ) : null

  let body
  if (isViewer || error?.kind === 'forbidden') {
    body = <ErrorAlert title={t('testCases.forbidden.title')} message={t('testCases.forbidden.body', { role: t('testCases.forbidden.role') })} />
  } else if (loading && cases.length === 0) {
    body = <LoadingState rows={3} />
  } else if (error?.kind === 'message') {
    body = (
      <div className="flex flex-col items-start gap-3">
        <ErrorAlert message={error.message} />
        <Button type="button" variant="outline" onClick={load}>
          {t('common:actions.retry')}
        </Button>
      </div>
    )
  } else if (active.length === 0 && !showRetired) {
    body = (
      <div className="flex flex-col gap-3">
        <EmptyState
          icon={ClipboardCheck}
          title={t('testCases.empty.title')}
          description={t('testCases.empty.body')}
          action={createButton}
        />
        {retiredCount > 0 ? (
          <RetiredToggle
            count={retiredCount}
            showRetired={showRetired}
            onToggle={() => setShowRetired((prev) => !prev)}
          />
        ) : null}
      </div>
    )
  } else {
    body = (
      <div className="flex flex-col gap-4">
        {groups.map((group) => (
          <section key={group.key} aria-label={group.label} className="flex flex-col gap-2">
            {groups.length > 1 || entity === undefined ? (
              <h4 className="text-sm font-medium text-muted-foreground">{group.label}</h4>
            ) : null}
            <ul className="flex flex-col divide-y rounded-lg border">
              {group.cases.map((testCase) => (
                <TestCaseRow
                  key={testCase.id}
                  testCase={testCase}
                  canWrite={canWrite}
                  createdAt={dateFormat.format(new Date(testCase.created_at))}
                  onSupersede={() => openSupersede(testCase)}
                  onRetire={() => setRetireTarget(testCase)}
                />
              ))}
            </ul>
          </section>
        ))}
        {retiredCount > 0 ? (
          <RetiredToggle
            count={retiredCount}
            showRetired={showRetired}
            onToggle={() => setShowRetired((prev) => !prev)}
          />
        ) : null}
      </div>
    )
  }

  return (
    <section className="flex min-w-0 flex-col gap-4" data-testid="test-case-list" aria-busy={loading || undefined}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h3 ref={headingRef} tabIndex={-1} className="text-lg font-semibold break-words outline-none">
            {subjectLabel
              ? t('testCases.titleFor', { subject: subjectLabel })
              : t('testCases.title')}
          </h3>
          {!isViewer && !error && !loading && active.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              {t(entity ? 'testCases.summaryEntity' : 'testCases.summaryAgent', {
                count: active.length,
              })}
            </p>
          ) : null}
        </div>
        {!isViewer && !error && active.length > 0 ? createButton : null}
      </div>

      {body}

      {canWrite ? (
        <TestCaseForm
          open={formOpen}
          onOpenChange={setFormOpen}
          agentId={agentId}
          agents={agents}
          entity={entity}
          supersedes={supersedes}
          onSaved={() => load()}
        />
      ) : null}

      <Dialog
        open={retireTarget !== null}
        onOpenChange={(open) => {
          if (!open && !retiring) setRetireTarget(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('testCases.retire.title')}</DialogTitle>
            <DialogDescription>{t('testCases.retire.question')}</DialogDescription>
          </DialogHeader>
          {retireTarget ? (
            <p className="text-sm font-medium break-words">{retireTarget.title}</p>
          ) : null}
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={retiring}>
                {t('common:actions.cancel')}
              </Button>
            </DialogClose>
            <Button
              type="button"
              variant="destructive"
              disabled={retiring}
              aria-busy={retiring || undefined}
              onClick={() => void onRetire()}
            >
              {t('testCases.retire.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  )
}

function RetiredToggle({
  count,
  showRetired,
  onToggle,
}: {
  count: number
  showRetired: boolean
  onToggle: () => void
}) {
  const { t } = useTranslation('learning')
  return (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="min-h-10 self-start md:min-h-0"
      aria-pressed={showRetired}
      onClick={onToggle}
    >
      <Archive className="h-4 w-4" aria-hidden="true" />
      {showRetired
        ? t('testCases.retired.hide')
        : t('testCases.retired.show', { count })}
    </Button>
  )
}

interface TestCaseRowProps {
  testCase: TestCaseRead
  canWrite: boolean
  createdAt: string
  onSupersede: () => void
  onRetire: () => void
}

function TestCaseRow({ testCase, canWrite, createdAt, onSupersede, onRetire }: TestCaseRowProps) {
  const { t } = useTranslation('learning')
  const retired = testCase.status === 'retired'
  return (
    <li
      className="flex min-w-0 items-start justify-between gap-3 p-4"
      data-testid="test-case-row"
      data-status={testCase.status}
    >
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="font-medium break-words">{testCase.title}</p>
          <span className="inline-flex items-center gap-2 rounded-full border px-2.5 py-0.5 text-xs text-muted-foreground">
            <span
              className="inline-block size-2 rounded-full"
              style={{ backgroundColor: `var(--status-${retired ? 'inactive' : 'active'})` }}
              aria-hidden="true"
            />
            {t(`testCases.status.${testCase.status}`)}
          </span>
          {testCase.origin_case_id ? (
            <span className="text-xs text-muted-foreground">
              {t('testCases.row.fromCase', { id: shortId(testCase.origin_case_id) })}
            </span>
          ) : null}
        </div>
        <p className="text-sm break-words whitespace-pre-wrap">
          <span className="text-muted-foreground">{t('testCases.row.expected')} </span>
          {testCase.expected_behavior}
        </p>
        <p className="text-xs text-muted-foreground">
          {t('testCases.row.meta', {
            checkKind: t(`testCases.checkKind.${testCase.check_kind}`),
            date: createdAt,
          })}
          {testCase.created_by_kind === 'agent' ? ` · ${t('testCases.row.byAgent')}` : ''}
          {testCase.supersedes_id ? ` · ${t('testCases.row.revision')}` : ''}
        </p>
      </div>
      {canWrite && !retired ? (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="min-h-10 shrink-0 md:min-h-0"
              aria-label={t('testCases.row.actions', { title: testCase.title })}
            >
              <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={onSupersede}>
              <FilePlus2 aria-hidden="true" />
              {t('testCases.supersede')}
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={onRetire}>
              <Archive aria-hidden="true" />
              {t('testCases.retire.action')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
    </li>
  )
}
