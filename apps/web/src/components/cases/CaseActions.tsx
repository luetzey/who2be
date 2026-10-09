import { ChevronDown, MoreHorizontal } from 'lucide-react'
import { useEffect, useId, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { ApiError, type Api } from '@/api/client'
import type {
  Agent,
  CaseDetail,
  CaseElementInput,
  CaseTarget,
  VersionStatus,
  VersionedEntityType,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { ErrorAlert } from '@/components/data/ErrorAlert'
import { TestCaseForm } from '@/components/testcases/TestCaseForm'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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
import { Select } from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Textarea } from '@/components/ui/textarea'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { type CaseAction, nextStep, versionedElements } from '@/lib/caseNextStep'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

// Begruendung bei Verwerfen/Wieder oeffnen: Spec S8 „≥ 10 Zeichen“, Deckel
// wie `CASE_NOTE_MAX_LENGTH` im Modell.
const REASON_MIN = 10
const NOTE_MAX = 2_000

// Gruppen im Zuordnen-Dialog (Spec S8 „Zuordnen“), in dieser Reihenfolge.
// `tool_policy` und `model_limit` tragen keine `entity_id`.
const ENTITY_GROUPS = [
  'persona',
  'playbook',
  'resource',
  'external_tool',
  'system_prompt_template',
  'memory',
] as const satisfies readonly CaseTarget[]
type EntityGroup = (typeof ENTITY_GROUPS)[number]

function problemOf(cause: unknown): { reason: string | null; params: Record<string, unknown> } {
  if (!(cause instanceof ApiError)) return { reason: null, params: {} }
  const body = cause.body as { reason?: unknown; params?: unknown } | null
  return {
    reason: typeof body?.reason === 'string' ? body.reason : null,
    params:
      body?.params !== null && typeof body?.params === 'object'
        ? (body.params as Record<string, unknown>)
        : {},
  }
}

function messageOf(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause)
}

const FOOTER = 'flex flex-col-reverse gap-2 sm:flex-row sm:justify-end'
const ACTION = 'min-h-11 md:min-h-10'

/**
 * Dialog ab `md`, darunter Bottom-Sheet mit fixierter Knopfleiste (Spec S8,
 * 390 px). Beides ist Radix-Dialog: Fokusfalle, Escape, Fokus zurueck.
 */
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
            <div className={cn(FOOTER, 'border-t bg-background px-4 py-3')}>{footer}</div>
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
}: {
  busy: boolean
  submitLabel: string
  onCancel: () => void
  destructive?: boolean
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
        disabled={busy}
        aria-busy={busy || undefined}
      >
        {submitLabel}
      </Button>
    </>
  )
}

// --- Zuordnen --------------------------------------------------------------

interface Option {
  id: string
  label: string
}

type Options = Record<EntityGroup, Option[]>

const EMPTY_OPTIONS: Options = {
  persona: [],
  playbook: [],
  resource: [],
  external_tool: [],
  system_prompt_template: [],
  memory: [],
}

const keyOf = (target: CaseTarget, id: string | null) => `${target}:${id ?? ''}`

/** Elemente des Agenten je Gruppe. Scheitert eine Quelle, bleibt sie leer. */
function useAssignOptions(api: Api, agent: Agent | null, open: boolean) {
  const [loaded, setLoaded] = useState<Options | null>(null)
  useEffect(() => {
    if (!open || agent === null) return
    let cancelled = false
    const safe = <T,>(job: Promise<T>, fallback: T) => job.catch(() => fallback)
    void Promise.all([
      agent.persona_id !== null
        ? safe(api.getPersona(agent.persona_id).then((p) => [{ id: p.id, label: p.name }]), [])
        : Promise.resolve([] as Option[]),
      safe(
        api.listPlaybooks({ agent: agent.id }).then((list) => list.map((p) => ({ id: p.id, label: p.name }))),
        [],
      ),
      safe(
        api.listResources({ agent: agent.id }).then((list) => list.map((r) => ({ id: r.id, label: r.name }))),
        [],
      ),
      safe(
        api.listExternalTools().then((list) => list.map((tool) => ({ id: tool.id, label: tool.name }))),
        [],
      ),
      agent.system_prompt_template_id !== null
        ? safe(
            api
              .getSystemPromptTemplate(agent.system_prompt_template_id)
              .then((tpl) => [{ id: tpl.id, label: tpl.name }]),
            [],
          )
        : Promise.resolve([] as Option[]),
      safe(
        api
          .listAgentMemories(agent.id, 'active')
          .then((list) => list.map((memory) => ({ id: memory.id, label: memory.fact }))),
        [],
      ),
    ]).then(([persona, playbook, resource, externalTool, template, memory]) => {
      if (cancelled) return
      setLoaded({
        persona,
        playbook,
        resource,
        external_tool: externalTool,
        system_prompt_template: template,
        memory,
      })
    })
    return () => {
      cancelled = true
    }
  }, [api, agent, open])
  // Der Dialog wird je Oeffnung neu gemountet, `loaded` startet also leer.
  return { options: loaded ?? EMPTY_OPTIONS, loading: open && agent !== null && loaded === null }
}

function AssignPanel({
  open,
  onOpenChange,
  detail,
  agent,
  names,
  onChanged,
  onTransitionRefused,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  detail: CaseDetail
  agent: Agent | null
  names: Record<string, string>
  onChanged: (transitioned: boolean) => void
  onTransitionRefused: (cause: unknown) => string
}) {
  const { t } = useTranslation(['feedback', 'common'])
  const api = useApi()
  const mobile = useIsMobile()
  const caseId = detail.case.id
  const offerTriage = detail.case.status === 'open' || detail.case.status === 'reopened'
  const { options, loading } = useAssignOptions(api, agent, open)
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(detail.elements.map((element) => keyOf(element.target, element.entity_id))),
  )
  const [alsoTriage, setAlsoTriage] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<EntityGroup>>(
    () => new Set(detail.elements.map((element) => element.target as EntityGroup)),
  )
  const baseId = useId()

  // Optionen plus bereits zugeordnete Elemente, die der Agent nicht (mehr) fuehrt.
  const groups = useMemo(() => {
    const result: { group: EntityGroup; items: Option[] }[] = []
    for (const group of ENTITY_GROUPS) {
      const items = [...options[group]]
      for (const element of detail.elements) {
        if (element.target !== group || element.entity_id === null) continue
        if (items.some((item) => item.id === element.entity_id)) continue
        items.push({
          id: element.entity_id,
          label: names[keyOf(group, element.entity_id)] ?? t(`feedback:cases.target.${group}`),
        })
      }
      if (items.length > 0) result.push({ group, items })
    }
    return result
  }, [options, detail.elements, names, t])

  const toggle = (key: string) => {
    setError(null)
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const submit = async () => {
    const triage = offerTriage && alsoTriage
    if (triage && selected.size === 0) {
      setError(t('feedback:cases.assign.required'))
      return
    }
    const elements: CaseElementInput[] = [...selected].map((key) => {
      const [target, id] = key.split(':') as [CaseTarget, string]
      return id === '' ? { target } : { target, entity_id: id }
    })
    setBusy(true)
    setError(null)
    try {
      await api.putCaseElements(caseId, elements)
    } catch (cause: unknown) {
      setError(messageOf(cause))
      setBusy(false)
      return
    }
    if (!triage) {
      setBusy(false)
      onOpenChange(false)
      onChanged(false)
      return
    }
    try {
      await api.transitionCase(caseId, { to: 'triaged' })
      setBusy(false)
      onOpenChange(false)
      onChanged(true)
    } catch (cause: unknown) {
      // Die Zuordnung ist gespeichert; der Fehler bleibt im Dialog.
      setError(onTransitionRefused(cause))
      setBusy(false)
      onChanged(false)
    }
  }

  const checkbox = (key: string, label: ReactNode, help?: string) => {
    const id = `${baseId}-${key}`
    return (
      <div key={key} className="flex min-w-0 items-start gap-3 py-1">
        <Checkbox
          id={id}
          className="mt-0.5"
          checked={selected.has(key)}
          onChange={() => toggle(key)}
          aria-describedby={help ? `${id}-help` : undefined}
        />
        <div className="flex min-w-0 flex-col gap-0.5">
          <Label htmlFor={id} className="leading-snug font-normal wrap-anywhere">
            {label}
          </Label>
          {help ? (
            <p id={`${id}-help`} className="text-xs text-muted-foreground">
              {help}
            </p>
          ) : null}
        </div>
      </div>
    )
  }

  const toggleGroup = (group: EntityGroup) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(group)) next.delete(group)
      else next.add(group)
      return next
    })

  const legend = 'text-sm font-medium'
  return (
    <ActionPanel
      open={open}
      onOpenChange={onOpenChange}
      title={t('feedback:cases.assign.title')}
      description={t('feedback:cases.assign.intro')}
      testId="case-assign-dialog"
      busy={busy}
      onSubmit={() => void submit()}
      footer={
        <PanelFooter
          busy={busy}
          submitLabel={t('feedback:cases.assign.save')}
          onCancel={() => onOpenChange(false)}
        />
      }
    >
      {error !== null ? <ErrorAlert message={error} /> : null}
      {loading ? (
        <p className="text-sm text-muted-foreground" aria-live="polite">
          {t('common:loading')}
        </p>
      ) : null}
      {groups.map(({ group, items }) => {
        const contentId = `${baseId}-${group}-items`
        // Unter `md` sind die Gruppen Akkordeons (Spec S8, 390 px).
        const shown = !mobile || expanded.has(group)
        return (
          <fieldset key={group} className="flex min-w-0 flex-col gap-1" data-testid={`case-assign-group-${group}`}>
            <legend className={cn(legend, 'w-full')}>
              {mobile ? (
                <Button
                  type="button"
                  variant="ghost"
                  className="min-h-11 w-full justify-between px-0 text-left font-medium hover:bg-transparent"
                  aria-expanded={shown}
                  aria-controls={contentId}
                  onClick={() => toggleGroup(group)}
                >
                  {group === 'memory'
                    ? t('feedback:cases.assign.memory')
                    : t(`feedback:cases.assign.group.${group}`)}
                  <ChevronDown
                    className={cn('size-4 shrink-0 transition-transform', shown && 'rotate-180')}
                    aria-hidden="true"
                  />
                </Button>
              ) : group === 'memory' ? (
                t('feedback:cases.assign.memory')
              ) : (
                t(`feedback:cases.assign.group.${group}`)
              )}
            </legend>
            <div id={contentId} className={cn('flex min-w-0 flex-col', !shown && 'hidden')}>
              {items.map((item) =>
                checkbox(
                  keyOf(group, item.id),
                  group === 'memory' ? <span className="line-clamp-2">{item.label}</span> : item.label,
                ),
              )}
            </div>
          </fieldset>
        )
      })}
      <fieldset className="flex min-w-0 flex-col gap-1" data-testid="case-assign-group-tool_policy">
        <legend className={legend}>{t('feedback:cases.target.tool_policy')}</legend>
        {checkbox(keyOf('tool_policy', null), t('feedback:cases.assign.tool_policy'))}
      </fieldset>
      <fieldset
        className="flex min-w-0 flex-col gap-1 border-t pt-4"
        data-testid="case-assign-group-model_limit"
      >
        <legend className={cn(legend, 'float-left mb-1 w-full')}>
          {t('feedback:cases.target.model_limit')}
        </legend>
        {checkbox(
          keyOf('model_limit', null),
          t('feedback:cases.assign.model_limit'),
          t('feedback:cases.assign.model_limitHelp'),
        )}
      </fieldset>
      {offerTriage ? (
        <div className="flex items-center gap-3 border-t pt-4">
          <Checkbox
            id={`${baseId}-also-triage`}
            checked={alsoTriage}
            onChange={(event) => setAlsoTriage(event.target.checked)}
          />
          <Label htmlFor={`${baseId}-also-triage`} className="font-normal">
            {t('feedback:cases.assign.alsoTriage')}
          </Label>
        </div>
      ) : null}
    </ActionPanel>
  )
}

// --- Als umgesetzt markieren ----------------------------------------------

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

function AddressPanel({
  open,
  onOpenChange,
  detail,
  elementLabel,
  onDone,
  onRefused,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  detail: CaseDetail
  elementLabel: (target: CaseTarget, id: string | null) => string
  onDone: () => void
  onRefused: (cause: unknown) => string | null
}) {
  const { t } = useTranslation(['feedback', 'common'])
  const api = useApi()
  const baseId = useId()
  const candidates = versionedElements(detail.elements)
  const [element, setElement] = useState(() =>
    candidates.length === 1 ? (candidates[0].entity_id ?? '') : '',
  )
  const [version, setVersion] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [missing, setMissing] = useState<{ element?: boolean; version?: boolean }>({})

  const chosen = candidates.find((candidate) => candidate.entity_id === element) ?? null
  const chosenTarget = chosen?.target ?? null
  const chosenId = chosen?.entity_id ?? null
  // Versionen je gewaehltem Baustein; ein Wechsel setzt `version` im Handler zurueck.
  const [loaded, setLoaded] = useState<{ id: string; list: VersionOption[] } | null>(null)
  const versions = loaded !== null && loaded.id === chosenId ? loaded.list : null

  useEffect(() => {
    if (chosenTarget === null || chosenId === null) return
    let cancelled = false
    listVersions(api, chosenTarget as VersionedEntityType, chosenId).then(
      (list) => {
        if (!cancelled) setLoaded({ id: chosenId, list: [...list].sort((a, b) => b.version - a.version) })
      },
      (cause: unknown) => {
        if (!cancelled) {
          setLoaded({ id: chosenId, list: [] })
          setError(messageOf(cause))
        }
      },
    )
    return () => {
      cancelled = true
    }
  }, [api, chosenTarget, chosenId])

  const submit = async () => {
    const gaps = { element: chosen === null, version: version === '' }
    if (gaps.element || gaps.version) {
      setMissing(gaps)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.transitionCase(detail.case.id, {
        to: 'addressed',
        version_entity_type: chosen!.target as VersionedEntityType,
        version_id: version,
        note: note.trim() === '' ? null : note.trim(),
      })
      setBusy(false)
      onOpenChange(false)
      onDone()
    } catch (cause: unknown) {
      setBusy(false)
      const message = onRefused(cause)
      if (message === null) onOpenChange(false)
      else setError(message)
    }
  }

  const required = t('feedback:cases.report.validation.required')
  return (
    <ActionPanel
      open={open}
      onOpenChange={onOpenChange}
      title={t('feedback:cases.address.title')}
      description={t('feedback:cases.address.intro')}
      testId="case-address-dialog"
      busy={busy}
      onSubmit={() => void submit()}
      footer={
        <PanelFooter
          busy={busy}
          submitLabel={t('feedback:cases.address.submit')}
          onCancel={() => onOpenChange(false)}
        />
      }
    >
      {error !== null ? <ErrorAlert message={error} /> : null}
      <div className="flex min-w-0 flex-col gap-1">
        <Label htmlFor={`${baseId}-element`}>{t('feedback:cases.address.element')}</Label>
        <Select
          id={`${baseId}-element`}
          value={element}
          aria-invalid={missing.element || undefined}
          aria-describedby={missing.element ? `${baseId}-element-error` : undefined}
          onChange={(event) => {
            setElement(event.target.value)
            setVersion('')
            setMissing((prev) => ({ ...prev, element: false }))
          }}
        >
          <option value="">{t('feedback:cases.address.choose')}</option>
          {candidates.map((candidate) => (
            <option key={candidate.id} value={candidate.entity_id ?? ''}>
              {elementLabel(candidate.target, candidate.entity_id)}
            </option>
          ))}
        </Select>
        {missing.element ? (
          <p id={`${baseId}-element-error`} className="text-xs text-destructive">
            {required}
          </p>
        ) : null}
      </div>
      <div className="flex min-w-0 flex-col gap-1">
        <Label htmlFor={`${baseId}-version`}>{t('feedback:cases.address.version')}</Label>
        <Select
          id={`${baseId}-version`}
          value={version}
          disabled={chosen === null || versions === null}
          aria-invalid={missing.version || undefined}
          aria-describedby={missing.version ? `${baseId}-version-error` : undefined}
          onChange={(event) => {
            setVersion(event.target.value)
            setMissing((prev) => ({ ...prev, version: false }))
          }}
        >
          <option value="">{t('feedback:cases.address.choose')}</option>
          {(versions ?? []).map((option) => (
            <option key={option.id} value={option.id}>
              {option.status === 'active'
                ? `v${option.version} · ${t('feedback:cases.address.activeTag')}`
                : `v${option.version}`}
            </option>
          ))}
        </Select>
        {missing.version ? (
          <p id={`${baseId}-version-error`} className="text-xs text-destructive">
            {required}
          </p>
        ) : null}
      </div>
      <div className="flex min-w-0 flex-col gap-1">
        <Label htmlFor={`${baseId}-note`}>{t('feedback:cases.address.note')}</Label>
        <Textarea
          id={`${baseId}-note`}
          rows={3}
          maxLength={NOTE_MAX}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
    </ActionPanel>
  )
}

// --- Verwerfen / Wieder oeffnen -------------------------------------------

function ReasonPanel({
  mode,
  open,
  onOpenChange,
  caseId,
  initialReason,
  onDone,
  onRefused,
}: {
  mode: 'dismiss' | 'reopen'
  open: boolean
  onOpenChange: (open: boolean) => void
  caseId: string
  initialReason: string
  onDone: () => void
  onRefused: (cause: unknown) => string | null
}) {
  const { t } = useTranslation(['feedback', 'common'])
  const api = useApi()
  const baseId = useId()
  const [reason, setReason] = useState(initialReason)
  const [invalid, setInvalid] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    const note = reason.trim()
    if (note.length < REASON_MIN) {
      setInvalid(true)
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.transitionCase(caseId, { to: mode === 'dismiss' ? 'dismissed' : 'reopened', note })
      setBusy(false)
      onOpenChange(false)
      onDone()
    } catch (cause: unknown) {
      setBusy(false)
      const message = onRefused(cause)
      if (message === null) onOpenChange(false)
      else setError(message)
    }
  }

  const fieldId = `${baseId}-reason`
  return (
    <ActionPanel
      open={open}
      onOpenChange={onOpenChange}
      title={t(`feedback:cases.${mode}.title`)}
      testId={`case-${mode}-dialog`}
      busy={busy}
      onSubmit={() => void submit()}
      footer={
        <PanelFooter
          busy={busy}
          destructive={mode === 'dismiss'}
          submitLabel={t(`feedback:cases.${mode}.submit`)}
          onCancel={() => onOpenChange(false)}
        />
      }
    >
      {error !== null ? <ErrorAlert message={error} /> : null}
      <div className="flex min-w-0 flex-col gap-1">
        <Label htmlFor={fieldId}>{t(`feedback:cases.${mode}.reason`)}</Label>
        <Textarea
          id={fieldId}
          rows={4}
          maxLength={NOTE_MAX}
          value={reason}
          aria-invalid={invalid || undefined}
          aria-describedby={`${fieldId}-help${invalid ? ` ${fieldId}-error` : ''}`}
          onChange={(event) => {
            setReason(event.target.value)
            setInvalid(false)
          }}
        />
        <p id={`${fieldId}-help`} className="text-xs text-muted-foreground">
          {t('feedback:cases.dismiss.reasonHelp')}
        </p>
        {invalid ? (
          <p id={`${fieldId}-error`} className="text-xs text-destructive">
            {t('feedback:cases.reason.tooShort', { min: REASON_MIN })}
          </p>
        ) : null}
      </div>
    </ActionPanel>
  )
}

// --- Leiste ----------------------------------------------------------------

type Panel = 'assign' | 'address' | 'dismiss' | 'reopen' | 'testCase'

export interface CaseActionsProps {
  detail: CaseDetail
  agent: Agent | null
  /** Elementnamen je `<target>:<entity_id>` (aus dem Fall-Detail). */
  names: Record<string, string>
  /** Ziel von „Zur Version“; `null`, solange die Version nicht aufgeloest ist. */
  addressedPath: string | null
  hasTestCase: boolean
  /** Nach jeder Aenderung; `transitioned` = der Status hat gewechselt. */
  onChanged: (transitioned: boolean) => void
  onTestCaseCreated: () => void
}

/**
 * „Nächster Schritt“ und Status-Menue im Fall-Detail (Spec S8, ADR-0053
 * D6d) mit den Dialogen Zuordnen, Als umgesetzt markieren, Verwerfen und
 * Wieder öffnen sowie „Prüffall daraus anlegen“ ueber `TestCaseForm`.
 */
export function CaseActions({
  detail,
  agent,
  names,
  addressedPath,
  hasTestCase,
  onChanged,
  onTestCaseCreated,
}: CaseActionsProps) {
  const { t } = useTranslation(['feedback', 'common'])
  const api = useApi()
  const [panel, setPanelState] = useState<Panel | null>(null)
  // Jede Oeffnung bekommt einen frischen Key: die Dialoge starten mit leerem
  // Zustand, ohne Reset-Effekte (react-hooks/set-state-in-effect).
  const [generation, setGeneration] = useState(0)
  const setPanel = (next: Panel) => {
    setGeneration((value) => value + 1)
    setPanelState(next)
  }
  const closeOr = (target: Panel) => (open: boolean) => {
    if (!open) setPanelState(null)
    else setPanelState(target)
  }
  const [busy, setBusy] = useState(false)
  const item = detail.case
  const step = nextStep(item.status, detail.elements, hasTestCase)
  const modelLimit = detail.elements.some((element) => element.target === 'model_limit')

  const elementLabel = (target: CaseTarget, id: string | null): string => {
    const kind = t(`feedback:cases.target.${target}`)
    const name = id !== null ? names[`${target}:${id}`] : undefined
    return name !== undefined ? `${kind}: ${name}` : kind
  }

  // `case_transition_forbidden`: der Stand hat sich geaendert (oder die
  // Zuordnung fehlt). Spec S8 „Zustände“: Text zeigen, Seite neu laden.
  // Liefert den Text fuer einen offenen Dialog; `null` = Dialog schliessen.
  const refused = (cause: unknown, keepDialog: boolean): string | null => {
    const { reason, params } = problemOf(cause)
    if (reason === 'case_transition_forbidden') {
      if (params.missing === 'element') return t('feedback:cases.assign.required')
      onChanged(false)
      const message = t('feedback:cases.error.transitionForbidden')
      if (keepDialog) return message
      notify.error(message)
      return null
    }
    return messageOf(cause)
  }

  const triage = async () => {
    setBusy(true)
    try {
      await api.transitionCase(item.id, { to: 'triaged' })
      onChanged(true)
    } catch (cause: unknown) {
      const message = refused(cause, false)
      if (message !== null) notify.error(message)
    } finally {
      setBusy(false)
    }
  }

  const run = (action: CaseAction) => {
    switch (action) {
      case 'assign':
      case 'changeAssignment':
        setPanel('assign')
        return
      case 'triage':
        void triage()
        return
      case 'createTestCase':
        setPanel('testCase')
        return
      case 'address':
        setPanel('address')
        return
      case 'dismiss':
        setPanel('dismiss')
        return
      case 'reopen':
        setPanel('reopen')
        return
      case 'toVersion':
        return
    }
  }

  const label = (action: CaseAction) => t(`feedback:cases.action.${action}`)

  if (step.primary === null && step.menu.length === 0) return null

  const firstVersioned = versionedElements(detail.elements)[0] ?? null

  return (
    <section
      className="flex flex-col gap-3 rounded-xl border bg-card p-4 md:flex-row md:items-center md:justify-between"
      aria-labelledby="case-next-step-title"
      data-testid="case-next-step"
    >
      <h2 id="case-next-step-title" className="text-sm font-medium text-muted-foreground">
        {t('feedback:cases.detail.next')}
      </h2>
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        {step.primary === 'toVersion' ? (
          addressedPath !== null ? (
            <Button asChild variant="default" className={cn(ACTION, 'w-full md:w-auto')}>
              <Link to={addressedPath}>{label('toVersion')}</Link>
            </Button>
          ) : null
        ) : step.primary !== null ? (
          <Button
            type="button"
            variant="brand"
            className={cn(ACTION, 'w-full md:w-auto')}
            disabled={busy}
            aria-busy={busy || undefined}
            onClick={() => run(step.primary!)}
          >
            {label(step.primary)}
          </Button>
        ) : null}
        {step.menu.length > 0 || step.addressUnavailable ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                type="button"
                variant="outline"
                className={cn(ACTION, 'w-full md:w-auto')}
                data-testid="case-status-menu"
              >
                <MoreHorizontal aria-hidden="true" />
                {t('feedback:cases.detail.moreActions')}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="max-w-[min(20rem,calc(100vw-2rem))]">
              {step.menu.map((action) => (
                <DropdownMenuItem key={action} className="min-h-11 md:min-h-8" onSelect={() => run(action)}>
                  {label(action)}
                </DropdownMenuItem>
              ))}
              {step.addressUnavailable ? (
                // Kein Knopf (Spec S8): ein Hinweis, warum „Umgesetzt“ fehlt.
                <p
                  className="px-2 py-1.5 text-xs whitespace-normal text-muted-foreground"
                  data-testid="case-address-unavailable"
                >
                  {t('feedback:cases.action.addressUnavailable')}
                </p>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>

      <AssignPanel
        key={`assign-${generation}`}
        open={panel === 'assign'}
        onOpenChange={closeOr('assign')}
        detail={detail}
        agent={agent}
        names={names}
        onChanged={onChanged}
        onTransitionRefused={(cause) => refused(cause, true) ?? ''}
      />
      <AddressPanel
        key={`address-${generation}`}
        open={panel === 'address'}
        onOpenChange={closeOr('address')}
        detail={detail}
        elementLabel={elementLabel}
        onDone={() => onChanged(true)}
        onRefused={(cause) => refused(cause, false)}
      />
      <ReasonPanel
        key={`dismiss-${generation}`}
        mode="dismiss"
        open={panel === 'dismiss'}
        onOpenChange={closeOr('dismiss')}
        caseId={item.id}
        initialReason={modelLimit ? t('feedback:cases.dismiss.modelLimitDefault') : ''}
        onDone={() => onChanged(true)}
        onRefused={(cause) => refused(cause, false)}
      />
      <ReasonPanel
        key={`reopen-${generation}`}
        mode="reopen"
        open={panel === 'reopen'}
        onOpenChange={closeOr('reopen')}
        caseId={item.id}
        initialReason=""
        onDone={() => onChanged(true)}
        onRefused={(cause) => refused(cause, false)}
      />
      <TestCaseForm
        open={panel === 'testCase'}
        onOpenChange={closeOr('testCase')}
        agentId={item.agent_id}
        entity={
          firstVersioned !== null && firstVersioned.entity_id !== null
            ? { type: firstVersioned.target as VersionedEntityType, id: firstVersioned.entity_id }
            : undefined
        }
        prefill={{
          input: item.situation,
          expected: item.expected_behavior,
          originCaseId: item.id,
        }}
        onSaved={onTestCaseCreated}
      />
    </section>
  )
}
