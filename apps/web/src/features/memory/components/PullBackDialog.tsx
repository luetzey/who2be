import { useEffect, useId, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { MemoryRead } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useSession } from '@/auth/session-context'
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
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Select } from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useAgents } from '@/hooks/useAgents'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useIsMobile } from '@/hooks/useMediaQuery'
import { notify } from '@/lib/feedback'

import { countMismatchOf, visibleToMe } from '../hooks/useMemoryApi'

type Period = '24h' | '7d' | 'since'
type Scope = 'all' | 'agent'

// „Seit“ hoechstens so weit zurueck (Spec §8; verfallene Eintraege sind nach
// 30 Tagen ohnehin `expired`).
const MAX_DAYS_BACK = 90
const DAY_MS = 24 * 60 * 60 * 1000

interface Selection {
  period: Period
  sinceDate: string
  scope: Scope
  agentId: string
}

interface Preview {
  key: string
  // Der beim Zaehlen festgehaltene Zeitpunkt: die Ausfuehrung sendet genau
  // ihn, damit „Letzte 24 Stunden“ dieselbe Menge meint wie die Vorschau.
  since: string
  count: number
  hidden: number
  sample: MemoryRead[]
}

/** Lokales Datum `YYYY-MM-DD` (fuer `<input type="date">`). */
function localDate(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** Beginn des Zeitraums als ISO-Zeitpunkt, `null` bei ungueltigem Datum. */
function sinceOf(selection: Selection, now: Date): string | null {
  if (selection.period === '24h') return new Date(now.getTime() - DAY_MS).toISOString()
  if (selection.period === '7d') return new Date(now.getTime() - 7 * DAY_MS).toISOString()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(selection.sinceDate)) return null
  const start = new Date(`${selection.sinceDate}T00:00:00`)
  if (Number.isNaN(start.getTime())) return null
  const earliest = new Date(`${localDate(new Date(now.getTime() - MAX_DAYS_BACK * DAY_MS))}T00:00:00`)
  if (start > now || start < earliest) return null
  return start.toISOString()
}

/** Umfang des Not-Aus: ein Agent oder alles; Fremdes nur fuer admin. */
function scopeOf(current: Selection, admin: boolean) {
  return {
    agent_id: current.scope === 'agent' && current.agentId !== '' ? current.agentId : undefined,
    include_other_users: admin,
  }
}

export interface PullBackDialogProps {
  open: boolean
  onClose: () => void
  // Nach erfolgreicher Ruecknahme (Zaehler und Listen neu laden).
  onDone: () => void
}

/**
 * Not-Aus „Automatisch Freigegebenes zurücknehmen“ (Spec §8, ADR-0053 6.4.1).
 * Zaehlt zuerst (`dry_run`) und fuehrt nur mit `expected_count` aus. Weicht
 * die Serverzahl ab (409 `memory_batch_count_mismatch`), bleibt der Dialog
 * offen und nennt die neue Zahl — wiederholt wird nie still. Nur editor+;
 * `include_other_users` nur admin, und fremdes Nutzergedaechtnis erscheint
 * auch dann nur als Anzahl.
 */
export function PullBackDialog({ open, onClose, onDone }: PullBackDialogProps) {
  const { t } = useTranslation('learning')
  const mobile = useIsMobile()
  const role = useCurrentWorkspaceRole()
  if (role === null || role === 'viewer') return null

  const title = t('pullback.title')
  const description = t('pullback.description')
  const body = (renderButtons: (buttons: ReactNode) => ReactNode) => (
    <PullBackBody admin={role === 'admin'} onClose={onClose} onDone={onDone}>
      {renderButtons}
    </PullBackBody>
  )

  if (mobile) {
    return (
      <Sheet open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
        <SheetContent
          side="bottom"
          className="flex h-svh flex-col gap-4 rounded-t-none"
          data-testid="pullback-dialog"
        >
          <SheetHeader className="pr-8 text-left">
            <SheetTitle>{title}</SheetTitle>
            <SheetDescription>{description}</SheetDescription>
          </SheetHeader>
          {open ? body((buttons) => <SheetFooter>{buttons}</SheetFooter>) : null}
        </SheetContent>
      </Sheet>
    )
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? undefined : onClose())}>
      <DialogContent className="flex flex-col overflow-hidden" data-testid="pullback-dialog">
        <DialogHeader className="pr-8">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {open ? body((buttons) => <DialogFooter>{buttons}</DialogFooter>) : null}
      </DialogContent>
    </Dialog>
  )
}

interface PullBackBodyProps {
  admin: boolean
  onClose: () => void
  onDone: () => void
  children: (buttons: ReactNode) => ReactNode
}

function PullBackBody({ admin, onClose, onDone, children }: PullBackBodyProps) {
  const { t, i18n } = useTranslation('learning')
  const api = useApi()
  const { me } = useSession()
  const userId = me?.user_id ?? null
  const { agents } = useAgents()
  const periodId = useId()
  const scopeId = useId()
  const statusId = useId()
  const waitId = useId()

  const today = useMemo(() => new Date(), [])
  const [selection, setSelection] = useState<Selection>({
    period: '24h',
    sinceDate: localDate(today),
    scope: 'all',
    agentId: '',
  })
  const agentId = selection.agentId !== '' ? selection.agentId : (agents[0]?.id ?? '')
  // Der Agent zaehlt nur beim Umfang „Nur ein Agent“ — sonst zaehlte das
  // Nachladen der Agentenliste die Vorschau grundlos neu.
  const effective = useMemo(
    () => ({ ...selection, agentId: selection.scope === 'agent' ? agentId : '' }),
    [selection, agentId],
  )
  const key = JSON.stringify(effective)
  const debouncedKey = useDebouncedValue(key)

  const [preview, setPreview] = useState<Preview | null>(null)
  // Schluessel der Auswahl, deren Zaehlung fehlschlug (gilt nur fuer genau sie).
  const [countErrorKey, setCountErrorKey] = useState<string | null>(null)
  const [changed, setChanged] = useState(false)
  const [busy, setBusy] = useState(false)

  const format = new Intl.NumberFormat(i18n.language)

  // Vorschau (`dry_run`) nach jeder Aenderung von Zeitraum oder Umfang,
  // entprellt. Ohne gueltige Auswahl wird nicht gezaehlt.
  useEffect(() => {
    const current = JSON.parse(debouncedKey) as Selection
    const since = sinceOf(current, new Date())
    if (since === null || (current.scope === 'agent' && current.agentId === '')) return
    let cancelled = false
    api
      .previewRevokeAuto({ since, ...scopeOf(current, admin) })
      .then((result) => {
        if (cancelled) return
        setCountErrorKey(null)
        setChanged(false)
        setPreview({
          key: debouncedKey,
          since,
          count: result.count,
          hidden: result.hidden_count,
          sample: result.sample,
        })
      })
      .catch(() => {
        if (!cancelled) setCountErrorKey(debouncedKey)
      })
    return () => {
      cancelled = true
    }
  }, [api, debouncedKey, admin])

  const valid =
    sinceOf(effective, new Date()) !== null && (effective.scope === 'all' || agentId !== '')
  const countError = countErrorKey === key
  const ready = preview !== null && preview.key === key && !countError

  const submit = async () => {
    if (!ready) return
    setBusy(true)
    try {
      const result = await api.revokeAuto({
        since: preview.since,
        ...scopeOf(effective, admin),
        expected_count: preview.count,
      })
      notify.success(
        t('pullback.done', { count: result.count, formatted: format.format(result.count) }),
      )
      onDone()
      onClose()
    } catch (cause: unknown) {
      const count = countMismatchOf(cause)
      if (count === null) {
        notify.error(t('batch.failedAll'))
        return
      }
      // Neue Zahl zeigen und neu bestaetigen lassen — nie still wiederholen.
      // Die Vorschau zaehlt mit demselben Zeitpunkt neu, damit Liste und Zahl
      // zusammenpassen; faellt sie aus, gilt die Zahl aus der 409.
      let next: Preview = { ...preview, count }
      try {
        const fresh = await api.previewRevokeAuto({
          since: preview.since,
          ...scopeOf(effective, admin),
        })
        next = { ...preview, count: fresh.count, hidden: fresh.hidden_count, sample: fresh.sample }
      } catch {
        // Zahl aus der 409 genuegt.
      }
      setPreview(next)
      setChanged(true)
    } finally {
      setBusy(false)
    }
  }

  const set = (patch: Partial<Selection>) => setSelection((current) => ({ ...current, ...patch }))
  const sample = ready ? preview.sample.filter((memory) => visibleToMe(memory, userId)) : []
  const visibleCount = ready ? preview.count - preview.hidden : 0
  const rest = Math.max(0, visibleCount - sample.length)
  const nameOf = (memory: MemoryRead) => {
    if (memory.scope === 'user') return t('detail.scope.user')
    const id = memory.agent_id ?? memory.created_by_agent_id
    return agents.find((agent) => agent.id === id)?.name ?? null
  }
  const minDate = localDate(new Date(today.getTime() - MAX_DAYS_BACK * DAY_MS))
  // `min-w-0`: Grid- und Flex-Kinder wachsen sonst mit langen Agentennamen ueber den Rand.
  const radioRow = 'flex min-h-11 min-w-0 items-center gap-3 md:min-h-8'

  const buttons =
    ready && preview.count === 0 ? (
      <Button type="button" variant="outline" onClick={onClose} data-testid="pullback-close">
        {t('common:actions.close')}
      </Button>
    ) : (
      <>
        <Button type="button" variant="outline" disabled={busy} onClick={onClose}>
          {t('common:actions.cancel')}
        </Button>
        <Button
          type="button"
          variant="destructive"
          disabled={!ready || busy}
          aria-describedby={ready ? undefined : waitId}
          aria-busy={busy || undefined}
          onClick={() => void submit()}
          data-testid="pullback-submit"
        >
          {t('pullback.submit', {
            count: ready ? preview.count : 0,
            formatted: format.format(ready ? preview.count : 0),
          })}
        </Button>
        {ready ? null : (
          <span id={waitId} className="sr-only">
            {t('pullback.waitReason')}
          </span>
        )}
      </>
    )

  return (
    <>
      {/* Nur dieser Teil scrollt; Kopf und Buttonzeile bleiben sichtbar. */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-5 overflow-y-auto overscroll-contain">
        <fieldset className="flex min-w-0 flex-col gap-1">
          <legend id={periodId} className="mb-1 text-sm font-medium">
            {t('pullback.period')}
          </legend>
          <RadioGroup
            aria-labelledby={periodId}
            value={selection.period}
            onValueChange={(value) => set({ period: value as Period })}
            className="min-w-0 grid-cols-1 gap-0"
          >
            {(['24h', '7d'] as const).map((value) => (
              <div key={value} className={radioRow}>
                <RadioGroupItem id={`${periodId}-${value}`} value={value} />
                <Label htmlFor={`${periodId}-${value}`} className="font-normal">
                  {t(value === '24h' ? 'pullback.period24h' : 'pullback.period7d')}
                </Label>
              </div>
            ))}
            <div className={`${radioRow} flex-wrap`}>
              <RadioGroupItem id={`${periodId}-since`} value="since" />
              <Label htmlFor={`${periodId}-since`} className="font-normal">
                {t('pullback.since')}
              </Label>
              <Input
                type="date"
                aria-label={t('pullback.sinceDate')}
                className="min-h-11 w-auto md:min-h-9"
                value={selection.sinceDate}
                min={minDate}
                max={localDate(today)}
                disabled={selection.period !== 'since'}
                onChange={(event) => set({ sinceDate: event.target.value })}
                data-testid="pullback-since"
              />
            </div>
          </RadioGroup>
        </fieldset>

        <fieldset className="flex min-w-0 flex-col gap-1">
          <legend id={scopeId} className="mb-1 text-sm font-medium">
            {t('pullback.scope')}
          </legend>
          <RadioGroup
            aria-labelledby={scopeId}
            value={selection.scope}
            onValueChange={(value) => set({ scope: value as Scope })}
            className="min-w-0 grid-cols-1 gap-0"
          >
            <div className={radioRow}>
              <RadioGroupItem id={`${scopeId}-all`} value="all" />
              <Label htmlFor={`${scopeId}-all`} className="font-normal break-words">
                {t(admin ? 'pullback.scopeAll' : 'pullback.scopeAllEditor')}
              </Label>
            </div>
            <div className={`${radioRow} flex-wrap`}>
              <RadioGroupItem
                id={`${scopeId}-agent`}
                value="agent"
                disabled={agents.length === 0}
              />
              <Label htmlFor={`${scopeId}-agent`} className="font-normal">
                {t('pullback.scopeAgent')}
              </Label>
              <Select
                aria-label={t('pullback.agent')}
                className="min-h-11 w-auto max-w-full min-w-0 text-ellipsis md:min-h-9"
                value={agentId}
                disabled={selection.scope !== 'agent'}
                onChange={(event) => set({ agentId: event.target.value })}
                data-testid="pullback-agent"
              >
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </Select>
            </div>
          </RadioGroup>
          {admin ? null : (
            <p className="text-sm text-muted-foreground" data-testid="pullback-editor-note">
              {t('pullback.editorNote')}
            </p>
          )}
        </fieldset>

        <div className="flex min-w-0 flex-col gap-2" data-testid="pullback-preview">
          <p id={statusId} className="text-sm font-medium" aria-live="polite">
            {countError
              ? t('pullback.countError')
              : !valid
                ? null
                : !ready
                  ? t('pullback.counting')
                  : preview.count === 0
                    ? t('pullback.none')
                    : t('pullback.affects', {
                        count: preview.count,
                        formatted: format.format(preview.count),
                      })}
          </p>
          {sample.length > 0 ? (
            <ul className="flex min-w-0 list-disc flex-col gap-1 pl-5 text-sm">
              {sample.map((memory) => {
                const name = nameOf(memory)
                return (
                  <li key={memory.id} className="break-words" data-testid="pullback-sample">
                    „{memory.fact}“
                    {name !== null ? (
                      <span className="text-muted-foreground"> · {name}</span>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          ) : null}
          {ready && rest > 0 ? (
            <p className="text-sm text-muted-foreground">
              {t('approval.groupConfirm.more', { count: rest })}
            </p>
          ) : null}
          {ready && preview.hidden > 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="pullback-hidden">
              {t('pullback.hidden', {
                count: preview.hidden,
                formatted: format.format(preview.hidden),
              })}
            </p>
          ) : null}
          {changed && ready ? (
            <p className="text-sm font-medium" role="status" data-testid="pullback-count-changed">
              {t('approval.countChanged', { count: preview.count })}
            </p>
          ) : null}
        </div>
      </div>
      {children(buttons)}
    </>
  )
}
