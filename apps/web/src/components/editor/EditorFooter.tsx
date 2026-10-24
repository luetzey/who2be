// EditorFooter — Fußzeile unter den BlockNote-Editoren (Editor-Paket P3,
// Spec §3.1). Links steht die geschätzte Länge: „≈ N Zeichen · ≈ M Token
// (geschätzt)“, ab 8 000 Token dahinter „· lang“. Prüfstand und Speicherstatus
// folgen in späteren Paketen (P5).
//
// Richtwerte (ADR-0063, Builder schlank B5): Mit `budget` zeigt die Fußzeile
// zusätzlich Wörter und Richtwert, etwa „412 Wörter · Richtwert 400“. Ab der
// Warnschwelle steht dort „über dem Richtwert 400, …“ in der Kontrastfarbe
// `text-brand` (#1046): der Text trägt die Warnung, die Farbe nur zusätzlich.
// Die Zahlen kommen aus `contentBudgets.generated.ts` (erzeugt aus
// `who2be_models.content_budgets`), die Zählung folgt der API (`countWords`).
// Gespeichert wird immer; es gibt keine Grenze.
//
// Barrierefreiheit: Die sichtbare Zeile ist bewusst KEINE Live-Region, sonst
// spräche der Screenreader bei jedem Tastendruck. Eine eigene, unsichtbare
// Region mit `aria-live="polite"` meldet die Länge erst, wenn sich die Zahl
// gegenüber dem Stand beim Öffnen geändert hat, und frühestens
// ANNOUNCE_DELAY_MS nach der letzten Änderung (gedrosselt). Beim Öffnen
// meldet sie nichts.

import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useInRouterContext, useParams } from 'react-router-dom'

import { InfoTooltip } from '@/components/ui/info-tooltip'
import { cn } from '@/lib/utils'

import { CONTENT_BUDGETS } from './contentBudgets.generated'
import {
  type BudgetElement,
  CHARS_PER_TOKEN,
  countWords,
  estimateLength,
  formatCount,
  LENGTH_HELP_HREF,
  overBudget,
} from './estimate'

/** Ruhezeit nach der letzten Änderung, bevor die Live-Region spricht. */
export const ANNOUNCE_DELAY_MS = 1000

/** Hinweistext zu Messwert und Richtwert, z. B. „412 Wörter · Richtwert 400“. */
function useBudgetText(element: BudgetElement, value: number): { text: string; over: boolean } {
  const { t, i18n } = useTranslation('editor')
  const budget: { target: number | null; warn: number } = CONTENT_BUDGETS[element]
  const over = overBudget(element, value)
  const params = {
    count: value,
    value: formatCount(value, i18n.language),
    target: formatCount(budget.target ?? budget.warn, i18n.language),
  }
  const measure = t(`footer.budget.measure.${element}`, params)
  const rest = over ? t(`footer.budget.over.${element}`, params) : t('footer.budget.target', params)
  return { text: `${measure} · ${rest}`, over }
}

export interface BudgetNoteProps {
  element: BudgetElement
  value: number
  className?: string
}

/** Richtwert-Zeile, auch einzeln nutzbar (Moduskarte: drei Felder zusammen, Zahl der Modi). */
export function BudgetNote({ element, value, className }: BudgetNoteProps) {
  const { text, over } = useBudgetText(element, value)
  return (
    <span
      className={cn(className, over && 'font-medium text-brand')}
      data-testid={`budget-note-${element}`}
      data-over={over ? 'true' : 'false'}
    >
      {text}
    </span>
  )
}

export interface EditorFooterProps {
  /** Aktueller Dokumentstand (BlockNote-Blöcke). */
  blocks: unknown
  /** Richtwert in Wörtern für dieses Dokument (Persona-Profil, Playbook-Body). */
  budget?: 'profile' | 'playbook_body'
}

export function EditorFooter({ blocks, budget }: EditorFooterProps) {
  const { t, i18n } = useTranslation('editor')
  // Im Workspace direkt auf die Hilfe-Seite; sonst der Kurzlink, den die
  // Route `/help/*` auf den Standard-Workspace auflöst.
  const inRouter = useInRouterContext()
  const { workspaceId } = useParams<{ workspaceId?: string }>()
  const helpHref = workspaceId ? `/w/${workspaceId}${LENGTH_HELP_HREF}` : LENGTH_HELP_HREF
  const estimate = useMemo(() => estimateLength(blocks), [blocks])
  const words = useMemo(() => (budget ? countWords(blocks) : 0), [blocks, budget])
  const format = useMemo(() => new Intl.NumberFormat(i18n.language), [i18n.language])
  const chars = format.format(estimate.chars)
  const tokens = format.format(estimate.tokens)
  const summary = t('footer.length', { chars, tokens })

  // Stand beim Öffnen: solange die Zählung gleich bleibt, wird nichts gemeldet.
  const openedKeyRef = useRef(`${estimate.chars}`)
  const [announcement, setAnnouncement] = useState('')
  const announceText = t('footer.announce', { chars, tokens })
  const key = `${estimate.chars}`

  useEffect(() => {
    if (key === openedKeyRef.current) return undefined
    const timer = window.setTimeout(() => {
      // Nach der ersten Meldung zählt jede weitere Änderung neu.
      openedKeyRef.current = ''
      setAnnouncement(announceText)
    }, ANNOUNCE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [key, announceText])

  return (
    <div
      className="mt-1 flex flex-wrap items-center gap-x-1 px-1 text-xs text-muted-foreground"
      data-testid="editor-footer"
    >
      <span data-testid="editor-footer-length">{summary}</span>
      {estimate.long ? <span data-testid="editor-footer-long">{t('footer.long')}</span> : null}
      <InfoTooltip label={t('footer.helpLabel')} className="h-5 w-5">
        <p>{t('footer.tooltip', { perToken: CHARS_PER_TOKEN })}</p>
        {estimate.long ? <p className="mt-1">{t('footer.longTooltip')}</p> : null}
      </InfoTooltip>
      {budget ? (
        <span className="flex basis-full flex-wrap items-center gap-x-2 sm:basis-auto">
          <span aria-hidden="true" className="hidden sm:inline">
            ·
          </span>
          <BudgetNote element={budget} value={words} />
          {/* Ohne Router (Einzeltests der Editoren) entfällt nur der Link. */}
          {inRouter ? (
            <Link
              to={helpHref}
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-4 hover:text-foreground"
              data-testid="editor-footer-budget-help"
            >
              {t('footer.budget.helpLink')}
            </Link>
          ) : null}
        </span>
      ) : null}
      <span className="sr-only" aria-live="polite" data-testid="editor-footer-live">
        {announcement}
      </span>
    </div>
  )
}
