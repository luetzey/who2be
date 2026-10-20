import { Info, TriangleAlert, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { config } from '@/config'
import { pickLocalizedText } from '@/lib/operatorText'
import { cn } from '@/lib/utils'

/** sessionStorage-Schluessel; der Wert ist der weggeklickte Text. */
export const NOTICE_DISMISSED_KEY = 'who2be.notice.dismissed'

function readDismissed(): string | null {
  try {
    return window.sessionStorage.getItem(NOTICE_DISMISSED_KEY)
  } catch {
    return null
  }
}

interface NoticeBannerProps {
  /**
   * In der App (angemeldet) wegklickbar, bis die Sitzung des Tabs endet. Auf
   * der Login-Seite nicht: dort ist der Hinweis der Grund, warum jemand
   * vielleicht gerade nicht hineinkommt.
   */
  dismissible?: boolean
  className?: string
}

/**
 * Betreiber-Hinweis (`WHO2BE_NOTICE_DE`/`_EN`, `WHO2BE_NOTICE_LEVEL`) fuer
 * Wartung, Neustart oder Systemverbesserungen (Karte t_27d7c6ad). Ohne Text
 * rendert die Komponente nichts.
 *
 * Der Text kommt aus der Runtime-Config und wird ausschliesslich als React-
 * Textknoten gerendert: kein HTML, kein Markdown, keine Links. Zeilenumbrueche
 * bleiben ueber `whitespace-pre-line` sichtbar.
 *
 * Rolle je Level: `info` → `status` (hoeflich angesagt), `warning` → `alert`.
 *
 * Wegklicken merkt sich den TEXT, nicht nur "weggeklickt": setzt der Betreiber
 * einen neuen Hinweis, erscheint er wieder.
 */
export function NoticeBanner({ dismissible = false, className }: NoticeBannerProps) {
  const { t, i18n } = useTranslation('layout')
  const text = pickLocalizedText(config.notice, i18n.resolvedLanguage ?? i18n.language)
  const [dismissed, setDismissed] = useState<string | null>(() => readDismissed())

  if (text === '' || (dismissible && dismissed === text)) {
    return null
  }

  const warning = config.noticeLevel === 'warning'
  const Icon = warning ? TriangleAlert : Info

  const dismiss = () => {
    try {
      window.sessionStorage.setItem(NOTICE_DISMISSED_KEY, text)
    } catch {
      // Kein sessionStorage (Privatmodus o. ae.): nur fuer diese Ansicht weg.
    }
    setDismissed(text)
  }

  return (
    <div
      role={warning ? 'alert' : 'status'}
      data-testid="notice-banner"
      data-level={config.noticeLevel}
      className={cn(
        'flex w-full items-start gap-3 border px-4 py-3 text-sm',
        warning
          ? 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200'
          : 'border-border bg-muted text-foreground',
        className,
      )}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <p className="min-w-0 flex-1 break-words whitespace-pre-line">{text}</p>
      {dismissible ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="-my-1.5 h-8 w-8 shrink-0"
          aria-label={t('notice.dismiss')}
          onClick={dismiss}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </Button>
      ) : null}
    </div>
  )
}
