import { MoreHorizontal } from 'lucide-react'
import {
  type FormEvent,
  type ReactNode,
  type RefObject,
  useEffect,
  useId,
  useRef,
  useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError, type Api } from '@/api/client'
import type {
  CaseRead,
  MeasureRead,
  MeasureVerdict,
  VersionStatus,
  VersionedEntityType,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select } from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { isClosedState } from '@/features/evolution/lib/followUp'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { notify } from '@/lib/feedback'
import { roleLabel } from '@/lib/roles'
import { cn } from '@/lib/utils'

// Aktionen an einer Aenderung (Neuschnitt §1, §4; E5-Delta §0.3, §4.2, §4.3,
// §8): Entwurf verknuepfen, „Hat es gewirkt?“ und Zurueckziehen. Nur editor
// und admin; die Web-UI laeuft immer als Mensch (6.6, F-W7).
//
// Je Zustand hoechstens eine `brand`-Aktion, der Rest unter „Weitere
// Aktionen“. Endzustaende haben keine Leiste. Es gibt KEINEN Knopf, der
// Rueckmeldungen direkt auf `in_progress` oder `verified` setzt (W-E2 a,
// PM-5): Folgen fuer die Rueckmeldungen entstehen nur ueber die Antwort auf
// „Hat es gewirkt?“ bzw. das Zurueckziehen, beides rechnet der Server.

const NOTE_MIN = 10
const NOTE_MAX = 2_000
const VERDICTS: readonly MeasureVerdict[] = ['effective', 'ineffective', 'not_measurable']

const ACTION = 'min-h-11 w-full md:min-h-10 md:w-auto'
const FOOTER = 'flex flex-col-reverse gap-2 sm:flex-row sm:justify-end'

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

function reasonOf(cause: unknown): string | null {
  if (!(cause instanceof ApiError)) return null
  const body = cause.body as { reason?: unknown } | null
  return typeof body?.reason === 'string' ? body.reason : null
}

interface VersionOption {
  id: string
  version: number
  status?: VersionStatus
}

function listVersions(api: Api, type: VersionedEntityType, id: string): Promise<VersionOption[]> {
  switch (type) {
    case 'persona':
      return api.listPersonaVersions(id)
    case 'playbook':
      return api.listPlaybookVersions(id)
    case 'resource':
      return api.listResourceVersions(id)
    case 'external_tool':
      return api.listExternalToolVersions(id)
    case 'system_prompt_template':
      return api.listSystemPromptTemplateVersions(id)
  }
}

/**
 * Fehler einer Aktion als Text (E5-Delta §4.3). `null` = erledigt ohne Text
 * (die Aenderung gibt es nicht mehr: Sheet zu, Toast ueber `onGone`).
 */
function useRefusal(onChanged: () => void, onGone: () => void) {
  const { t } = useTranslation(['sessions', 'learning'])
  return (cause: unknown): string | null => {
    const reason = reasonOf(cause)
    if (reason === 'measure_not_found') {
      onGone()
      return null
    }
    if (reason === 'test_subject_version_not_found') return t('sessions:error.versionNotFound')
    if (reason === 'measure_transition_forbidden' || (cause instanceof ApiError && cause.status === 409)) {
      // QE3 a: der Stand hat sich geaendert — neu laden, dann erklaeren.
      onChanged()
      return t('sessions:error.conflict')
    }
    if (reason === 'missing_capability' || (cause instanceof ApiError && cause.status === 403)) {
      return t('learning:approval.forbidden', { role: roleLabel('editor') })
    }
    return messageOf(cause)
  }
}

/** Dialog ab `md`, darunter Bottom-Sheet; beides Radix (Fokusfalle, Escape). */
function ActionPanel({
  open,
  onOpenChange,
  title,
  description,
  testId,
  busy,
  onSubmit,
  footer,
  children,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string
  testId: string
  busy: boolean
  onSubmit: () => void
  footer: ReactNode
  children: ReactNode
}) {
  const mobile = useIsMobile()
  const change = (next: boolean) => (busy ? undefined : onOpenChange(next))
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit()
  }
  if (mobile) {
    return (
      <Sheet open={open} onOpenChange={change}>
        <SheetContent
          side="bottom"
          data-testid={testId}
          className="flex max-h-[90svh] flex-col gap-0 overflow-hidden p-0"
        >
          <SheetHeader className="px-4 pt-5 pr-12 pb-3 text-left">
            <SheetTitle>{title}</SheetTitle>
            {description ? <SheetDescription>{description}</SheetDescription> : null}
          </SheetHeader>
          <form className="flex min-h-0 flex-1 flex-col" noValidate onSubmit={submit}>
            <div
              className="flex min-h-0 min-w-0 flex-1 flex-col gap-4 overflow-x-hidden overflow-y-auto overscroll-contain px-4 pb-4"
              data-testid={`${testId}-body`}
            >
              {children}
            </div>
            <div className={cn(FOOTER, 'border-t bg-background px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]')}>
              {footer}
            </div>
          </form>
        </SheetContent>
      </Sheet>
    )
  }
  return (
    <Dialog open={open} onOpenChange={change}>
      <DialogContent data-testid={testId} className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>
        <form className="flex min-w-0 flex-col gap-4" noValidate onSubmit={submit}>
          <div className="flex min-w-0 flex-col gap-4" data-testid={`${testId}-body`}>
            {children}
          </div>
          <div className={FOOTER}>{footer}</div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PanelFooter({
  busy,
  submitLabel,
  onCancel,
  destructive = false,
  disabled = false,
}: {
  busy: boolean
  submitLabel: string
  onCancel: () => void
  destructive?: boolean
  disabled?: boolean
}) {
  const { t } = useTranslation('common')
  return (
    <>
      <Button type="button" variant="outline" className={ACTION} disabled={busy} onClick={onCancel}>
        {t('actions.cancel')}
      </Button>
      <Button
        type="submit"
        variant={destructive ? 'destructive' : 'brand'}
        className={ACTION}
        disabled={busy || disabled}
        aria-busy={busy || undefined}
      >
        {submitLabel}
      </Button>
    </>
  )
}

// --- Entwurf verknuepfen ----------------------------------------------------

function LinkDraftPanel({
  open,
  onOpenChange,
  measure,
  type,
  element,
  elementPath,
  onDone,
  refuse,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  measure: MeasureRead
  type: VersionedEntityType
  element: string
  elementPath: string | null
  onDone: () => void
  refuse: (cause: unknown) => string | null
}) {
  const { t } = useTranslation(['sessions', 'common'])
  const api = useApi()
  const baseId = useId()
  const [versions, setVersions] = useState<VersionOption[] | null>(null)
  const [nonce, setNonce] = useState(0)
  const [version, setVersion] = useState('')
  const [missing, setMissing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const entityId = measure.entity_id

  // Nur Entwurf und Zur Freigabe, neueste zuerst (E5-Delta §4.2): aktiv
  // wird eine Version erst im Review, dann entsteht `activated` (3.6, F3 a).
  useEffect(() => {
    if (!open || entityId === null) return
    let cancelled = false
    listVersions(api, type, entityId).then(
      (list) => {
        if (cancelled) return
        setVersions(
          list
            .filter((row) => row.status === 'draft' || row.status === 'review')
            .sort((a, b) => b.version - a.version),
        )
      },
      (cause: unknown) => {
        if (cancelled) return
        setVersions([])
        setError(messageOf(cause))
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, type, entityId, open, nonce])

  const submit = async () => {
    if (version === '') {
      setMissing(true)
      document.getElementById(`${baseId}-version`)?.focus()
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.linkMeasureDraft(measure.id, { version_entity_type: type, version_id: version })
      setBusy(false)
      onOpenChange(false)
      notify.success(t('sessions:linkDraft.done'))
      onDone()
    } catch (cause: unknown) {
      setBusy(false)
      const message = refuse(cause)
      if (message === null) {
        onOpenChange(false)
        return
      }
      setError(message)
      if (reasonOf(cause) === 'test_subject_version_not_found') {
        // Die Version gibt es nicht mehr: Auswahl leeren, Liste neu laden.
        setVersion('')
        setVersions(null)
        setNonce((value) => value + 1)
      }
    }
  }

  const stateWord = (status: VersionStatus | undefined) =>
    status === 'review' ? t('sessions:measure.versionState.review') : t('sessions:measure.versionState.draft')

  const fieldId = `${baseId}-version`
  const empty = versions !== null && versions.length === 0
  return (
    <ActionPanel
      open={open}
      onOpenChange={onOpenChange}
      title={t('sessions:linkDraft.title')}
      testId="change-link-draft-dialog"
      busy={busy}
      onSubmit={() => void submit()}
      footer={
        <PanelFooter
          busy={busy}
          disabled={empty}
          submitLabel={t('sessions:linkDraft.submit')}
          onCancel={() => onOpenChange(false)}
        />
      }
    >
      {error !== null ? <ErrorAlert message={error} /> : null}
      <div className="flex min-w-0 flex-col gap-1">
        <p className="text-xs font-medium text-muted-foreground">{t('sessions:linkDraft.element')}</p>
        <p className="text-sm break-words" data-testid="change-link-draft-element">
          {element}
        </p>
      </div>
      {empty ? (
        <p className="text-sm break-words" data-testid="change-link-draft-none">
          {t('sessions:linkDraft.none', { element })}{' '}
          {elementPath !== null ? (
            <Link to={elementPath} className="font-medium text-brand hover:underline">
              {t('sessions:linkDraft.open', { element })}
            </Link>
          ) : null}
        </p>
      ) : (
        <div className="flex min-w-0 flex-col gap-1">
          <Label htmlFor={fieldId}>{t('sessions:linkDraft.version')}</Label>
          <Select
            id={fieldId}
            value={version}
            disabled={versions === null}
            aria-invalid={missing || undefined}
            aria-describedby={`${fieldId}-help${missing ? ` ${fieldId}-error` : ''}`}
            onChange={(event) => {
              setVersion(event.target.value)
              setMissing(false)
            }}
          >
            <option value="">{t('sessions:linkDraft.choose')}</option>
            {(versions ?? []).map((row) => (
              <option key={row.id} value={row.id}>
                {`v${row.version} · ${stateWord(row.status)}`}
              </option>
            ))}
          </Select>
          {missing ? (
            <p id={`${fieldId}-error`} className="text-xs text-destructive">
              {t('sessions:linkDraft.versionRequired')}
            </p>
          ) : null}
          <p id={`${fieldId}-help`} className="text-xs text-muted-foreground">
            {t('sessions:linkDraft.help')}
          </p>
        </div>
      )}
    </ActionPanel>
  )
}

// --- Zurueckziehen -------------------------------------------------------

function WithdrawPanel({
  open,
  onOpenChange,
  measureId,
  onDone,
  refuse,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  measureId: string
  onDone: () => void
  refuse: (cause: unknown) => string | null
}) {
  const { t } = useTranslation(['sessions', 'feedback'])
  const api = useApi()
  const baseId = useId()
  const fieldRef = useRef<HTMLTextAreaElement>(null)
  const [reason, setReason] = useState('')
  const [invalid, setInvalid] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    const note = reason.trim()
    if (note.length < NOTE_MIN) {
      setInvalid(true)
      fieldRef.current?.focus()
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.withdrawMeasure(measureId, { note })
      setBusy(false)
      onOpenChange(false)
      notify.success(t('sessions:withdraw.done'))
      onDone()
    } catch (cause: unknown) {
      setBusy(false)
      const message = refuse(cause)
      if (message === null) onOpenChange(false)
      else setError(message)
    }
  }

  const fieldId = `${baseId}-reason`
  return (
    <ActionPanel
      open={open}
      onOpenChange={onOpenChange}
      title={t('sessions:withdraw.title')}
      description={t('sessions:withdraw.intro')}
      testId="change-withdraw-dialog"
      busy={busy}
      onSubmit={() => void submit()}
      footer={
        <PanelFooter
          busy={busy}
          destructive
          submitLabel={t('sessions:withdraw.submit')}
          onCancel={() => onOpenChange(false)}
        />
      }
    >
      {error !== null ? <ErrorAlert message={error} /> : null}
      {/* QE5: Owner 2026-10-09 „QE5a“ — der Server setzt Rueckmeldungen in
          Arbeit auf „Eingeordnet“ zurueck, sofern keine andere offene
          Aenderung sie enthaelt (`reset_cases_after_withdraw`). Der Satz
          kommt aus genau einem Key. */}
      <p className="text-sm break-words" data-testid="change-withdraw-cases">
        {t('sessions:withdraw.cases')}
      </p>
      <div className="flex min-w-0 flex-col gap-1">
        <Label htmlFor={fieldId}>{t('sessions:withdraw.reason')}</Label>
        <Textarea
          ref={fieldRef}
          id={fieldId}
          rows={4}
          maxLength={NOTE_MAX}
          value={reason}
          aria-invalid={invalid || undefined}
          aria-describedby={invalid ? `${fieldId}-error` : undefined}
          onChange={(event) => {
            setReason(event.target.value)
            setInvalid(false)
          }}
        />
        {invalid ? (
          <p id={`${fieldId}-error`} className="text-xs text-destructive">
            {t('feedback:cases.reason.tooShort', { min: NOTE_MIN })}
          </p>
        ) : null}
      </div>
    </ActionPanel>
  )
}

// --- „Hat es gewirkt?“ ----------------------------------------------------

function ReviewForm({
  formId,
  measure,
  cases,
  verdict,
  onVerdict,
  note,
  onNote,
  noteInvalid,
  noteRef,
  error,
}: {
  formId: string
  measure: MeasureRead
  cases: CaseRead[] | null
  verdict: MeasureVerdict | null
  onVerdict: (verdict: MeasureVerdict) => void
  note: string
  onNote: (note: string) => void
  noteInvalid: boolean
  noteRef: RefObject<HTMLTextAreaElement>
  error: string | null
}) {
  const { t } = useTranslation('sessions')
  const baseId = useId()
  const effectId = `${baseId}-effect`
  const hintId = `${baseId}-hint`
  const noteId = `${baseId}-note`

  // Zaehlung: Rueckmeldungen der Aenderung auf „Geaendert“ (`addressed`);
  // nur von dort fuehren die Kanten nach `verified`/`reopened` (3.3).
  // Geloeschte fehlen in `cases` (PM-6).
  const own = cases === null ? null : cases.filter((item) => measure.case_ids.includes(item.id))
  const addressed = own?.filter((item) => item.status === 'addressed').length ?? 0
  const unaffected = own === null ? 0 : own.length - addressed

  let effect: ReactNode = null
  if (verdict !== null && own !== null) {
    effect =
      verdict === 'not_measurable' ? (
        t('review.effect.not_measurable')
      ) : (
        <>
          {t(`review.effect.${verdict}`, { count: addressed })}
          {unaffected > 0 ? <> {t('review.effect.unaffected', { count: unaffected })}</> : null}
        </>
      )
  }

  return (
    <section className="flex min-w-0 flex-col gap-3" data-testid="change-review">
      <form id={formId} noValidate className="flex min-w-0 flex-col gap-3" onSubmit={(event) => event.preventDefault()}>
        <fieldset className="m-0 flex min-w-0 flex-col gap-2 border-0 p-0">
          <legend className="mb-2 text-base font-semibold">{t('review.legend')}</legend>
          <p id={hintId} className="text-xs text-muted-foreground" data-testid="change-review-human-only">
            {t('review.humanOnly')}
          </p>
          <RadioGroup
            value={verdict ?? ''}
            onValueChange={(value) => onVerdict(value as MeasureVerdict)}
            aria-describedby={`${hintId} ${effectId}`}
            className="gap-2"
          >
            {VERDICTS.map((option) => {
              const id = `${baseId}-${option}`
              return (
                <Label
                  key={option}
                  htmlFor={id}
                  className="flex min-h-11 min-w-0 cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 leading-normal has-[[data-state=checked]]:border-brand"
                  data-testid={`change-review-option-${option}`}
                >
                  <RadioGroupItem id={id} value={option} />
                  <span className="text-sm font-medium break-words">{t(`review.option.${option}`)}</span>
                </Label>
              )
            })}
          </RadioGroup>
          <p
            id={effectId}
            aria-live="polite"
            className="min-h-0 text-sm break-words text-muted-foreground"
            data-testid="change-review-effect"
          >
            {effect}
          </p>
        </fieldset>

        {verdict !== null ? (
          <div className="flex min-w-0 flex-col gap-1">
            <Label htmlFor={noteId}>
              {verdict === 'ineffective' ? t('review.note') : t('review.noteOptional')}
            </Label>
            <Textarea
              ref={noteRef}
              id={noteId}
              rows={3}
              maxLength={NOTE_MAX}
              value={note}
              aria-invalid={noteInvalid || undefined}
              aria-required={verdict === 'ineffective' || undefined}
              aria-describedby={noteInvalid ? `${noteId}-error` : undefined}
              onChange={(event) => onNote(event.target.value)}
            />
            {noteInvalid ? (
              <p id={`${noteId}-error`} className="text-xs text-destructive" data-testid="change-review-note-error">
                {t('review.noteRequired')}
              </p>
            ) : null}
          </div>
        ) : null}
        {error !== null ? <ErrorAlert message={error} /> : null}
      </form>
    </section>
  )
}

// --- Leiste -----------------------------------------------------------------

export interface ChangeActionsProps {
  measure: MeasureRead
  /** „Playbook „Name““ bzw. nur die Art. */
  element: string
  /** Versionierte Art des Ziels; `null` bei Werkzeugrechten und Gedaechtnis. */
  versionedType: VersionedEntityType | null
  /** Element-Detail (Leer-Satz im Dialog). */
  elementPath: string | null
  /** Versions-Tab des verknuepften Entwurfs („Zum Entwurf“). */
  draftPath: string | null
  /**
   * Darf jetzt geantwortet werden? Kommt vom Server (`FollowUpReport.reviewable`,
   * QE4 a / QE6 a), solange die Kennzahlen nicht da sind aus dem Zustand.
   */
  reviewable: boolean
  /** Rueckmeldungen des Review-Ergebnisses; `null` = laedt noch. */
  cases: CaseRead[] | null
  /** Nach jeder Aktion und bei Konflikt: Review-Ergebnis neu laden. */
  onChanged: () => void
  /** Die Aenderung gibt es nicht (mehr). */
  onGone: () => void
  /** Nach dem Speichern der Antwort: Fokus aufs Zustandswort. */
  onReviewed: () => void
  /** Steht zwischen der Antwort und der Leiste (Verlauf). */
  children?: ReactNode
}

type Panel = 'link' | 'withdraw' | null

/**
 * Antwort auf „Hat es gewirkt?“ (inline), Verlauf (`children`) und die
 * Aktionsleiste. viewer bekommen nichts davon, nur `children`.
 */
export function ChangeActions({
  measure,
  element,
  versionedType,
  elementPath,
  draftPath,
  reviewable,
  cases,
  onChanged,
  onGone,
  onReviewed,
  children,
}: ChangeActionsProps) {
  const { t } = useTranslation(['sessions', 'common'])
  const api = useApi()
  const wsPath = useWorkspacePath()
  const role = useCurrentWorkspaceRole()
  const formId = useId()
  const noteRef = useRef<HTMLTextAreaElement>(null)
  const refuse = useRefusal(onChanged, onGone)
  const [panel, setPanel] = useState<Panel>(null)
  const [generation, setGeneration] = useState(0)
  const [verdict, setVerdict] = useState<MeasureVerdict | null>(null)
  const [note, setNote] = useState('')
  const [noteInvalid, setNoteInvalid] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<MeasureVerdict | null>(null)

  const isEditor = role === 'editor' || role === 'admin'
  if (!isEditor) return <>{children}</>

  const closed = isClosedState(measure.state)
  // QE6: Owner 2026-10-09 „QE6a“. Eine einzige Bedingung, die der Server
  // bestimmt (`is_reviewable`): versioniert ab `activated`, ohne Versionen
  // (`tool_policy`, `memory`) ab Faelligkeit, nie nach dem Abschluss.
  const canReview = !closed && reviewable
  const linked = measure.state === 'draft_linked'
  const canLink = !closed && versionedType !== null && (measure.state === 'agreed' || linked)

  const submitReview = async () => {
    if (verdict === null || busy) return
    const text = note.trim()
    if (verdict === 'ineffective' && text.length < NOTE_MIN) {
      setNoteInvalid(true)
      noteRef.current?.focus()
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.reviewMeasure(measure.id, text === '' ? { verdict } : { verdict, note: text })
      setBusy(false)
      setDone(verdict)
      setVerdict(null)
      setNote('')
      onChanged()
      onReviewed()
    } catch (cause: unknown) {
      setBusy(false)
      setError(refuse(cause))
    }
  }

  const closePanel = (next: boolean) => {
    if (next) return
    setPanel(null)
    setGeneration((value) => value + 1)
  }

  // Primaere Aktion je Zustand (E5-Delta §4.2): hoechstens eine `brand`.
  let primary: ReactNode = null
  if (canReview) {
    primary = (
      <Button
        type="submit"
        form={formId}
        variant="brand"
        className={ACTION}
        disabled={verdict === null || busy}
        aria-busy={busy || undefined}
        onClick={(event) => {
          event.preventDefault()
          void submitReview()
        }}
      >
        {t('sessions:review.submit')}
      </Button>
    )
  } else if (canLink && !linked) {
    primary = (
      <Button type="button" variant="brand" className={ACTION} onClick={() => setPanel('link')}>
        {t('sessions:action.linkDraft')}
      </Button>
    )
  } else if (linked && draftPath !== null) {
    primary = (
      <Button asChild variant="default" className={ACTION}>
        <Link to={draftPath}>{t('sessions:action.toDraft')}</Link>
      </Button>
    )
  }

  const menu: { id: string; label: string; run: () => void }[] = []
  if (canLink && linked) {
    menu.push({ id: 'relink', label: t('sessions:action.relinkDraft'), run: () => setPanel('link') })
  }
  if (!closed) {
    menu.push({ id: 'withdraw', label: t('sessions:action.withdraw'), run: () => setPanel('withdraw') })
  }
  const noVersions = !closed && versionedType === null

  const prepareHref = wsPath(
    `/agents/${encodeURIComponent(measure.agent_id)}/reviews/prepare?cases=${measure.case_ids
      .map(encodeURIComponent)
      .join(',')}`,
  )

  return (
    <>
      {canReview ? (
        <ReviewForm
          formId={formId}
          measure={measure}
          cases={cases}
          verdict={verdict}
          onVerdict={(next) => {
            setVerdict(next)
            setNoteInvalid(false)
          }}
          note={note}
          onNote={(next) => {
            setNote(next)
            setNoteInvalid(false)
          }}
          noteInvalid={noteInvalid}
          noteRef={noteRef}
          error={error}
        />
      ) : null}

      {/* Meldung nach dem Speichern; bleibt, auch wenn die Leiste wegfaellt. */}
      <div role="status" aria-live="polite" className="flex min-w-0 flex-col gap-2 empty:hidden" data-testid="change-review-done">
        {done !== null ? (
          <>
            <p className="text-sm font-medium break-words">
              {t('sessions:review.done', { verdict: t(`sessions:measure.state.${done}`) })}
            </p>
            {done === 'ineffective' ? (
              <Link to={prepareHref} className="text-sm font-medium text-brand hover:underline" data-testid="change-new-review">
                {t('sessions:review.newSession')}
              </Link>
            ) : null}
          </>
        ) : null}
      </div>

      {children}

      {closed ? null : (
        <div
          className={cn(
            'flex min-w-0 flex-col gap-2 md:flex-row md:justify-end',
            // Unter md unten fixiert; „Weitere Aktionen“ ueber der `brand`-Aktion.
            'max-md:sticky max-md:bottom-0 max-md:z-10 max-md:-mx-4 max-md:border-t max-md:bg-background max-md:px-4 max-md:py-3',
          )}
          data-testid="change-actions"
        >
          {menu.length > 0 || noVersions ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button type="button" variant="outline" className={ACTION} data-testid="change-more">
                  <MoreHorizontal aria-hidden="true" />
                  {t('sessions:action.more')}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="max-w-[min(20rem,calc(100vw-2rem))]">
                {menu.map((item) => (
                  <DropdownMenuItem key={item.id} className="min-h-11 md:min-h-8" onSelect={item.run}>
                    {item.label}
                  </DropdownMenuItem>
                ))}
                {noVersions ? (
                  // Kein Knopf: ein Hinweis, warum „Entwurf verknüpfen“ fehlt.
                  <p
                    className="px-2 py-1.5 text-xs whitespace-normal text-muted-foreground"
                    data-testid="change-no-versions"
                  >
                    {t('sessions:action.noVersions')}
                  </p>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
          {primary}
        </div>
      )}

      {versionedType !== null ? (
        <LinkDraftPanel
          key={`link-${generation}`}
          open={panel === 'link'}
          onOpenChange={closePanel}
          measure={measure}
          type={versionedType}
          element={element}
          elementPath={elementPath}
          onDone={onChanged}
          refuse={refuse}
        />
      ) : null}
      <WithdrawPanel
        key={`withdraw-${generation}`}
        open={panel === 'withdraw'}
        onOpenChange={closePanel}
        measureId={measure.id}
        onDone={onChanged}
        refuse={refuse}
      />
    </>
  )
}
