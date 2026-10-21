// EditorFooter — Fußzeile unter den BlockNote-Editoren (Editor-Paket P3,
// Spec §3.1). Links steht die geschätzte Länge: „≈ N Zeichen · ≈ M Token
// (geschätzt)“, ab 8 000 Token dahinter „· lang“. Prüfstand und Speicherstatus
// folgen in späteren Paketen (P5).
//
// Barrierefreiheit: Die sichtbare Zeile ist bewusst KEINE Live-Region, sonst
// spräche der Screenreader bei jedem Tastendruck. Eine eigene, unsichtbare
// Region mit `aria-live="polite"` meldet die Länge erst, wenn sich die Zahl
// gegenüber dem Stand beim Öffnen geändert hat, und frühestens
// ANNOUNCE_DELAY_MS nach der letzten Änderung (gedrosselt). Beim Öffnen
// meldet sie nichts.

import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { InfoTooltip } from '@/components/ui/info-tooltip'

import { CHARS_PER_TOKEN, estimateLength } from './estimate'

/** Ruhezeit nach der letzten Änderung, bevor die Live-Region spricht. */
export const ANNOUNCE_DELAY_MS = 1000

export interface EditorFooterProps {
  /** Aktueller Dokumentstand (BlockNote-Blöcke). */
  blocks: unknown
}

export function EditorFooter({ blocks }: EditorFooterProps) {
  const { t, i18n } = useTranslation('editor')
  const estimate = useMemo(() => estimateLength(blocks), [blocks])
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
      <span className="sr-only" aria-live="polite" data-testid="editor-footer-live">
        {announcement}
      </span>
    </div>
  )
}
