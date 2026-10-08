import { ChevronRight, Info, LoaderCircle, MessageSquareWarning } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '@/api/client'
import type { CaseCreate, CaseSeverity, FeedbackSignal } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { ReadOnlyField } from '@/components/ui/read-only-field'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { toast } from '@/components/ui/sonner'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

// Laengen-Deckel aus `who2be_models.case` (CHECKs der Migration 0100, ADR-0053
// 3.3). Clientseitig nur Vorab-Pruefung; die Quelle der Wahrheit ist der Server.
const LIMITS = {
  situation: 4_000,
  behavior: 4_000,
  expected: 2_000,
  impact: 2_000,
  sourceRef: 500,
} as const

// Der Zaehler erscheint ab 80 % der Grenze (Delta-Spec S6, „Grenzen“).
const COUNTER_FROM = 0.8

// Reihenfolge der Art-Chips wie in Spec S6; „Lief gut“ zuletzt.
const KINDS: readonly FeedbackSignal[] = ['incorrect', 'outdated', 'unclear', 'helpful']
const SEVERITIES: readonly CaseSeverity[] = ['low', 'medium', 'high']

type TextField = keyof typeof LIMITS
// Reihenfolge, in der der Fokus das erste Fehlerfeld sucht (Lesefolge).
const FIELD_ORDER: readonly TextField[] = ['situation', 'behavior', 'expected', 'impact', 'sourceRef']
const REQUIRED: ReadonlySet<TextField> = new Set(['situation', 'behavior', 'expected'])

type Values = Record<TextField, string> & {
  signal: FeedbackSignal | null
  severity: CaseSeverity
}
type Errors = Partial<Record<TextField, string>>

const EMPTY: Values = {
  situation: '',
  behavior: '',
  expected: '',
  impact: '',
  sourceRef: '',
  signal: null,
  severity: 'medium',
}

function isDirty(values: Values): boolean {
  return (
    FIELD_ORDER.some((key) => values[key].trim() !== '') ||
    values.signal !== null ||
    values.severity !== EMPTY.severity
  )
}

function problemReason(cause: unknown): string | null {
  if (!(cause instanceof ApiError)) return null
  const body = cause.body as { reason?: unknown } | null
  return typeof body?.reason === 'string' ? body.reason : null
}

interface ReportCaseDialogProps {
  /** Fester Agent (Einstieg Agent-Detail, D6a). */
  agent: { id: string; name: string }
}

/**
 * „Fall melden“ (Delta-Spec S6, ADR-0053 3.3): Ausloeser plus Dialog. Ab
 * viewer; der Server prueft das Recht. Melden und Einordnen sind getrennt
 * (Q2), deshalb fragt der Dialog nicht nach einer vermuteten Ursache.
 *
 * Unter `md` oeffnet der Ausloeser bis D6c ebenfalls diesen Dialog (unter `sm`
 * im Vollbild); die eigene Melden-Seite kommt mit D6c.
 */
export function ReportCaseDialog({ agent }: ReportCaseDialogProps) {
  const { t } = useTranslation('feedback')
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button type="button" variant="outline" onClick={() => setOpen(true)}>
        <MessageSquareWarning aria-hidden="true" />
        {t('cases.report.title')}
      </Button>
      {open ? <ReportCaseModal agent={agent} onClose={() => setOpen(false)} /> : null}
    </>
  )
}

function ReportCaseModal({ agent, onClose }: ReportCaseDialogProps & { onClose: () => void }) {
  const { t } = useTranslation('feedback')
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const navigate = useNavigate()
  const wsPath = useWorkspacePath()
  const formId = useId()

  const [values, setValues] = useState<Values>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})
  const [submitted, setSubmitted] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [confirmDiscard, setConfirmDiscard] = useState(false)
  // Sperre gegen doppeltes Absenden, auch bevor React `busy` gerendert hat.
  const inFlight = useRef(false)
  // Erstes Fehlerfeld; ein neues Objekt je Absenden fokussiert erneut.
  const [focusTarget, setFocusTarget] = useState<{ key: TextField } | null>(null)

  const idOf = (key: string) => `${formId}-${key}`

  useEffect(() => {
    if (focusTarget !== null) document.getElementById(`${formId}-${focusTarget.key}`)?.focus()
  }, [focusTarget, formId])

  const validate = (next: Values): Errors => {
    const found: Errors = {}
    for (const key of FIELD_ORDER) {
      const text = next[key].trim()
      if (REQUIRED.has(key) && text === '') {
        found[key] = t('cases.report.validation.required')
      } else if (text.length > LIMITS[key]) {
        found[key] = t('cases.report.validation.tooLong', { max: LIMITS[key] })
      }
    }
    return found
  }

  const set = <K extends keyof Values>(key: K, value: Values[K]) => {
    const next = { ...values, [key]: value }
    setValues(next)
    // Validierung erst beim Absenden, danach live (Spec S6).
    if (submitted) setErrors(validate(next))
  }

  const requestClose = () => {
    if (busy) return
    if (isDirty(values)) setConfirmDiscard(true)
    else onClose()
  }

  const onSubmit = async () => {
    if (inFlight.current) return
    setSubmitted(true)
    const found = validate(values)
    setErrors(found)
    const first = FIELD_ORDER.find((key) => found[key] !== undefined)
    if (first !== undefined) {
      if (first === 'sourceRef') setMoreOpen(true)
      // Nach dem Rendern fokussieren: „Mehr angeben“ klappt ggf. erst auf.
      setFocusTarget({ key: first })
      return
    }
    const optional = (text: string) => (text.trim() === '' ? undefined : text.trim())
    const payload: CaseCreate = {
      agent_id: agent.id,
      situation: values.situation.trim(),
      behavior: values.behavior.trim(),
      expected_behavior: values.expected.trim(),
      impact: optional(values.impact),
      severity: values.severity,
      signal: values.signal ?? undefined,
      source_ref: optional(values.sourceRef),
    }
    inFlight.current = true
    setBusy(true)
    setSendError(null)
    try {
      const created = await api.createCase(payload)
      toast.success(
        role === 'viewer' ? t('cases.report.successViewer') : t('cases.report.success'),
        {
          action: {
            label: t('cases.report.successView'),
            onClick: () => navigate(wsPath(`/feedback/cases/${created.id}`)),
          },
        },
      )
      onClose()
    } catch (cause: unknown) {
      setSendError(
        problemReason(cause) === 'agent_not_found'
          ? t('cases.report.error.agentGone')
          : cause instanceof Error
            ? cause.message
            : String(cause),
      )
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }

  const keep = values.signal === 'helpful'

  const textField = (key: TextField, label: string, help: string, rows: number, multiline = true) => {
    const value = values[key]
    const limit = LIMITS[key]
    const showCounter = value.length >= limit * COUNTER_FROM
    const describedBy = [
      idOf(`${key}-help`),
      showCounter ? idOf(`${key}-count`) : null,
      errors[key] ? idOf(`${key}-error`) : null,
    ]
      .filter(Boolean)
      .join(' ')
    const common = {
      id: idOf(key),
      value,
      'aria-required': REQUIRED.has(key) || undefined,
      'aria-invalid': errors[key] ? true : undefined,
      'aria-describedby': describedBy,
    }
    return (
      <div className="flex min-w-0 flex-col gap-1">
        <Label htmlFor={idOf(key)}>
          {label}
          {REQUIRED.has(key) ? <span aria-hidden="true"> *</span> : null}
        </Label>
        <p id={idOf(`${key}-help`)} className="text-xs text-muted-foreground">
          {help}
        </p>
        {multiline ? (
          <Textarea {...common} rows={rows} onChange={(event) => set(key, event.target.value)} />
        ) : (
          <Input {...common} onChange={(event) => set(key, event.target.value)} />
        )}
        <div className="flex justify-between gap-2">
          {errors[key] ? (
            <p id={idOf(`${key}-error`)} className="text-xs text-destructive">
              {errors[key]}
            </p>
          ) : (
            <span />
          )}
          {showCounter ? (
            <p
              id={idOf(`${key}-count`)}
              className={cn(
                'shrink-0 text-xs tabular-nums',
                value.length > limit ? 'text-destructive' : 'text-muted-foreground',
              )}
            >
              {t('cases.report.counter', { length: value.length, max: limit })}
            </p>
          ) : null}
        </div>
      </div>
    )
  }

  const kindLabel = (kind: FeedbackSignal) =>
    kind === 'helpful' ? t('cases.report.kind.helpful') : t(`signal.${kind}`)

  return (
      <Dialog open onOpenChange={(next) => (next ? undefined : requestClose())}>
        <DialogContent
          // Unter `sm` Vollbild (wie `TestCaseForm`), ab `sm` zentriert, max-w-lg.
          className="h-[100dvh] max-h-[100dvh] w-screen max-w-none rounded-none sm:h-auto sm:max-h-[calc(100vh-2rem)] sm:w-[calc(100vw-2rem)] sm:max-w-lg sm:rounded-lg"
          data-testid="report-case-dialog"
        >
          <DialogHeader>
            <DialogTitle>{t('cases.report.title')}</DialogTitle>
            <DialogDescription>{t('cases.report.intro')}</DialogDescription>
          </DialogHeader>
          <form
            className="flex min-w-0 flex-col gap-4"
            noValidate
            aria-busy={busy || undefined}
            onSubmit={(event) => {
              event.preventDefault()
              void onSubmit()
            }}
          >
            {/* Agent fest (Einstieg Agent-Detail): Lesewert statt Auswahl. */}
            <ReadOnlyField label={t('cases.report.agent')} value={agent.name} />

            {textField(
              'situation',
              t('cases.report.situation'),
              t('cases.report.situationHelp'),
              3,
            )}
            {textField('behavior', t('cases.report.behavior'), t('cases.report.behaviorHelp'), 4)}
            {textField(
              'expected',
              keep ? t('cases.report.expectedKeep') : t('cases.report.expected'),
              t('cases.report.expectedHelp'),
              3,
            )}
            {textField('impact', t('cases.report.impact'), t('cases.report.impactHelp'), 2)}

            <div className="flex min-w-0 flex-col gap-2">
              <span className="text-sm font-medium" id={idOf('kind-label')}>
                {t('cases.report.kind.label')}
              </span>
              <div role="group" aria-labelledby={idOf('kind-label')} className="flex flex-wrap gap-2">
                {KINDS.map((kind) => (
                  <Button
                    key={kind}
                    type="button"
                    size="sm"
                    variant={values.signal === kind ? 'default' : 'outline'}
                    aria-pressed={values.signal === kind}
                    className="h-11 rounded-full sm:h-9"
                    onClick={() => set('signal', values.signal === kind ? null : kind)}
                  >
                    {kindLabel(kind)}
                  </Button>
                ))}
              </div>
            </div>

            <div className="flex min-w-0 flex-col gap-3">
              <Button
                type="button"
                variant="ghost"
                className="h-11 w-fit px-2 sm:h-9"
                aria-expanded={moreOpen}
                aria-controls={idOf('more')}
                onClick={() => setMoreOpen((prev) => !prev)}
              >
                <ChevronRight
                  aria-hidden="true"
                  className={cn('transition-transform', moreOpen && 'rotate-90')}
                />
                {t('cases.report.more')}
              </Button>
              <div id={idOf('more')} hidden={!moreOpen} className="flex min-w-0 flex-col gap-4">
                <fieldset className="flex min-w-0 flex-col gap-2">
                  <legend className="mb-2 text-sm font-medium">
                    {t('cases.report.severity.label')}
                  </legend>
                  <RadioGroup
                    value={values.severity}
                    onValueChange={(next) => set('severity', next as CaseSeverity)}
                    className="flex flex-wrap gap-4"
                  >
                    {SEVERITIES.map((severity) => (
                      <div key={severity} className="flex items-center gap-2">
                        <RadioGroupItem value={severity} id={idOf(`severity-${severity}`)} />
                        <Label htmlFor={idOf(`severity-${severity}`)} className="font-normal">
                          {t(`cases.report.severity.${severity}`)}
                        </Label>
                      </div>
                    ))}
                  </RadioGroup>
                </fieldset>
                {textField(
                  'sourceRef',
                  t('cases.report.sourceRef'),
                  t('cases.report.sourceRefHelp'),
                  1,
                  false,
                )}
              </div>
            </div>

            <p className="flex gap-2 text-xs text-muted-foreground">
              <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span>{t('cases.report.privacy')}</span>
            </p>

            {sendError !== null ? <ErrorAlert message={sendError} /> : null}

            <DialogFooter>
              <Button type="button" variant="outline" disabled={busy} onClick={requestClose}>
                {t('common:actions.cancel')}
              </Button>
              <Button type="submit" variant="brand" disabled={busy} aria-busy={busy || undefined}>
                {busy ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : null}
                {t('cases.report.submit')}
              </Button>
            </DialogFooter>
          </form>
          {/* Verschachtelt, damit Radix die Rueckfrage als innere Ebene fuehrt. */}
          <DiscardDialog
            open={confirmDiscard}
            onKeep={() => setConfirmDiscard(false)}
            onDiscard={() => {
              setConfirmDiscard(false)
              onClose()
            }}
          />
        </DialogContent>
      </Dialog>
  )
}

/** Rueckfrage „Eingaben verwerfen?“; ein Entwurf wird nie gespeichert (Spec S6). */
function DiscardDialog({
  open,
  onKeep,
  onDiscard,
}: {
  open: boolean
  onKeep: () => void
  onDiscard: () => void
}) {
  const { t } = useTranslation('feedback')
  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onKeep())}>
      <DialogContent data-testid="report-case-discard">
        <DialogHeader>
          <DialogTitle>{t('cases.report.discardTitle')}</DialogTitle>
          <DialogDescription>{t('cases.report.discardBody')}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onKeep}>
            {t('cases.report.discardKeep')}
          </Button>
          <Button type="button" variant="destructive" onClick={onDiscard}>
            {t('cases.report.discardConfirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
