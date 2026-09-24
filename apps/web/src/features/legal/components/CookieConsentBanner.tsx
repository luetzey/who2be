import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

import { useCookieConsent } from '../hooks/useCookieConsent'
import { Placeholder } from './Placeholder'

/**
 * CSS-Variable, unter der das Banner seine **gemessene** Hoehe an das Dokument
 * meldet. Verbraucht wird sie in `styles/globals.css` an zwei Stellen
 * (`body { padding-bottom }` und `html { scroll-padding-bottom }`) — siehe
 * die Begruendung am Effekt unten.
 */
export const BANNER_HEIGHT_VAR = '--cookie-banner-height'

/**
 * Cookie-Consent-Banner (Opt-in). Erscheint global, solange keine Entscheidung
 * getroffen wurde. „Nur notwendige" lehnt optionales Tracking ab, „Alle
 * akzeptieren" willigt ein — bis dahin laeuft **kein** Tracking. Der Banner
 * blockiert die App nicht (kein Modal), bleibt aber sichtbar bis zur Wahl.
 */
export function CookieConsentBanner() {
  const { isDecided, accept, reject } = useCookieConsent()
  const { t } = useTranslation('legal')
  const [card, setCard] = useState<HTMLDivElement | null>(null)

  /*
   * Befund B7 (Welle 7 / K2b): das Banner liegt `fixed` ueber dem Seitenfuss
   * und traegt `pointer-events-auto` — es faengt Klicks also tatsaechlich ab.
   * Auf 320px war die primaere Formularaktion darunter nicht mehr erreichbar
   * (Lauf 35928126972: „subtree intercepts pointer events"). Statt das Banner
   * zu verkleinern oder wegzuschalten — beides waere eine Aenderung am
   * Consent-Verhalten bzw. nur eine Verkleinerung der Trefferflaeche —
   * reserviert es sich jetzt den Platz, den es belegt.
   *
   * Gemessen statt geraten: die Hoehe haengt an Textlaenge, Sprache,
   * Nutzer-Schriftgroesse und Viewport-Breite (unterhalb `sm` stapelt die
   * Karte). Ein fester Wert waere sofort falsch; der `ResizeObserver` bleibt
   * bei jeder dieser Aenderungen korrekt.
   *
   * Ref-Callback per `useState` statt `useRef`: nur so laeuft der Effekt
   * erneut, wenn der Knoten wechselt — `useRef` benachrichtigt nicht.
   */
  useEffect(() => {
    if (card === null) {
      return
    }
    const root = document.documentElement
    const observer = new ResizeObserver(() => {
      // Aussenabstand des Wrappers (`p-4` = 16px oben und unten) gehoert zur
      // belegten Flaeche: die Karte sitzt 16px ueber der Viewport-Unterkante.
      const { height } = card.getBoundingClientRect()
      root.style.setProperty(BANNER_HEIGHT_VAR, `${Math.ceil(height) + 32}px`)
    })
    observer.observe(card)
    // Die Rueckgabe ist der einzige Ort, an dem die Reservierung zurueckgenommen
    // wird — und sie deckt beide Faelle ab: Entscheidung getroffen (Komponente
    // rendert `null`, Effekt wird aufgeraeumt) und Unmount. Ein zusaetzliches
    // `removeProperty` im `card === null`-Zweig waere tote Redundanz; die
    // Mutationsprobe zeigte, dass dann keiner der beiden Pfade einzeln bewacht
    // ist. Ohne diese Zeile behielte jede Seite dauerhaft einen toten Rand —
    // genau das faengt der Test „nimmt die Reservierung nach der Entscheidung
    // zurueck".
    return () => {
      observer.disconnect()
      root.style.removeProperty(BANNER_HEIGHT_VAR)
    }
  }, [card])

  const cardRef = useCallback((node: HTMLDivElement | null) => setCard(node), [])

  if (isDecided) {
    return null
  }

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4">
      <Card
        ref={cardRef}
        role="region"
        aria-label={t('cookie.regionLabel')}
        className="pointer-events-auto flex w-full max-w-2xl flex-col gap-4 p-4 shadow-modal sm:flex-row sm:items-center"
      >
        <div className="flex-1 space-y-1">
          <p className="text-sm font-medium">{t('cookie.title')}</p>
          <p className="text-sm text-muted-foreground">
            {t('cookie.body')}{' '}
            <Placeholder>{t('cookie.bodyServices')}</Placeholder>
            {') '}
            {t('cookie.bodyEnd')}{' '}
            <Link
              to="/legal/datenschutz"
              className="font-medium text-foreground underline-offset-4 hover:underline"
            >
              {t('cookie.privacyLink')}
            </Link>
            .
          </p>
        </div>
        {/* #567 (§4.4 Punkt 4): die beiden `size="sm"`-Buttons massen gerendert
            36px — §11 (Floor 32px) eingehalten, das 40px-Kriterium dieses
            Issues nicht. Unterhalb `md` daher `h-10`; unterhalb `sm`, wo der
            Banner stapelt, teilen sie sich die volle Kartenbreite (die Reihe
            mass mit `shrink-0` 256px bei 254px Innenraum). */}
        <div className="flex gap-2 sm:shrink-0">
          <Button
            variant="outline"
            size="sm"
            className="h-10 flex-1 sm:flex-none md:h-9"
            onClick={reject}
          >
            {t('cookie.rejectButton')}
          </Button>
          <Button
            variant="brand"
            size="sm"
            className="h-10 flex-1 sm:flex-none md:h-9"
            onClick={accept}
          >
            {t('cookie.acceptButton')}
          </Button>
        </div>
      </Card>
    </div>
  )
}
