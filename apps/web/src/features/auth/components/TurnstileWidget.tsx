import { useEffect, useRef } from 'react'

// Cloudflare Turnstile (Issue #539, Owner-Entscheidung Option A).
//
// Bewusst OHNE npm-Wrapper (`@marsidev/react-turnstile` o. ae.): die
// Widget-API kennt drei Aufrufe (`render`, `reset`, `remove`), und im
// Regelfall — kein Site-Key gesetzt — waere die Abhaengigkeit reiner
// Bundle-Ballast plus eine zusaetzliche Supply-Chain-/Lizenz-Flaeche.
//
// Das Script wird LAZY geladen: ohne gerendertes Widget geht kein einziger
// Request an Cloudflare. Das ist auch der datenschutzrechtlich relevante
// Punkt (Drittland-Empfaenger, siehe docs/compliance/legal-texts-checklist.md
// §2) — ohne aktiviertes Captcha entsteht kein Drittlandtransfer.

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit'
const SCRIPT_ID = 'cf-turnstile-script'

interface TurnstileRenderOptions {
  sitekey: string
  callback: (token: string) => void
  'expired-callback': () => void
  'error-callback': () => void
  theme?: 'light' | 'dark' | 'auto'
  language?: string
  action?: string
}

interface TurnstileApi {
  render: (container: HTMLElement, options: TurnstileRenderOptions) => string
  reset: (widgetId?: string) => void
  remove: (widgetId?: string) => void
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
  }
}

/**
 * Laedt das Turnstile-Script genau einmal pro Dokument.
 *
 * Der „schon geladen?"-Zustand lebt bewusst im DOM (das `<script>`-Element
 * plus sein `data-loaded`-Marker) statt in einer Modulvariable: eine solche
 * Variable ueberlebt weder ein zweites Bundle noch einen HMR-Austausch des
 * Moduls, und sie liesse sich in Tests nicht zuruecksetzen — dann haengt ein
 * Aufrufer an einem Promise, das zu einem laengst entfernten Element gehoert.
 */
function loadTurnstileScript(): Promise<void> {
  if (window.turnstile !== undefined) {
    return Promise.resolve()
  }
  return new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(SCRIPT_ID)
    if (existing !== null) {
      if ((existing as HTMLScriptElement).dataset.loaded === 'true') {
        resolve()
        return
      }
      existing.addEventListener('load', () => resolve())
      existing.addEventListener('error', () => reject(new Error('turnstile script failed')))
      return
    }
    const script = document.createElement('script')
    script.id = SCRIPT_ID
    script.src = SCRIPT_SRC
    script.async = true
    script.defer = true
    script.addEventListener('load', () => {
      script.dataset.loaded = 'true'
      resolve()
    })
    script.addEventListener('error', () => {
      // Element entfernen, damit ein spaeterer Versuch (neuer Mount nach
      // kurzem Netzausfall) wieder frisch laden kann, statt sich an ein
      // totes Element zu haengen.
      script.remove()
      reject(new Error('turnstile script failed'))
    })
    document.head.appendChild(script)
  })
}

interface TurnstileWidgetProps {
  /** Site-Key aus `config.turnstileSiteKey`. Nicht-leer vorausgesetzt. */
  siteKey: string
  /**
   * Cloudflare-`action` — taucht in der Turnstile-Analytics und in
   * Rate-Limiting-Regeln auf. Bewusst OHNE Default: mit vier Masken am selben
   * Site-Key (Signup, Login, Resend, Passwort-vergessen) waere ein stiller
   * Default genau die Vermischung, die die Auswertung wertlos macht.
   */
  action: 'signup' | 'login' | 'resend' | 'recover'
  /** Erfolgreich geloestes Captcha — liefert das einmalig gueltige Token. */
  onToken: (token: string) => void
  /**
   * Token abgelaufen oder Challenge fehlgeschlagen. Der Aufrufer muss das
   * zuvor erhaltene Token verwerfen: GoTrue lehnt es ab, und ein Formular,
   * das ein totes Token mitschickt, sieht fuer den Nutzer wie ein
   * unerklaerlicher Serverfehler aus.
   */
  onExpire: () => void
  className?: string
}

/**
 * Rendert das Turnstile-Widget und meldet das Token nach oben.
 *
 * Eine Instanz pro Seite. Der Aufrufer entscheidet ueber das Ob (Site-Key
 * gesetzt?), diese Komponente nur ueber das Wie.
 */
export function TurnstileWidget({
  siteKey,
  action,
  onToken,
  onExpire,
  className,
}: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  // Callbacks per Ref, damit ein neu erzeugtes Handler-Literal des Aufrufers
  // nicht das Widget neu rendert (Turnstile vergibt dann ein neues, fuer den
  // Nutzer sichtbar zurueckspringendes Widget).
  const onTokenRef = useRef(onToken)
  const onExpireRef = useRef(onExpire)
  // Zuweisung im Effekt, nicht im Render-Body: ein Ref-Schreibzugriff
  // waehrend des Renders ist in React 19 ein Lint-Fehler (`react-hooks/refs`)
  // und im Concurrent-Rendering nicht zugesichert. Unkritisch fuer die
  // Reihenfolge — die Callbacks werden erst aufgerufen, wenn Cloudflare das
  // geladene Widget aufloest, also lange nach dem Commit.
  useEffect(() => {
    onTokenRef.current = onToken
    onExpireRef.current = onExpire
  })

  useEffect(() => {
    let widgetId: string | undefined
    let cancelled = false

    loadTurnstileScript()
      .then(() => {
        if (cancelled || containerRef.current === null || window.turnstile === undefined) {
          return
        }
        widgetId = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          action,
          callback: (token: string) => onTokenRef.current(token),
          'expired-callback': () => onExpireRef.current(),
          'error-callback': () => onExpireRef.current(),
        })
      })
      .catch(() => {
        // Script nicht erreichbar (Netz, Adblocker, CSP). Kein Token → der
        // Submit-Button bleibt gesperrt und die Signup-Seite zeigt den
        // Hinweis des Aufrufers. Absichtlich fail-closed: ein Signup ohne
        // Token wuerde bei aktiviertem Captcha ohnehin an GoTrue scheitern,
        // nur mit einer unverstaendlicheren Meldung.
        if (!cancelled) {
          onExpireRef.current()
        }
      })

    return () => {
      cancelled = true
      if (widgetId !== undefined && window.turnstile !== undefined) {
        window.turnstile.remove(widgetId)
      }
    }
  }, [siteKey, action])

  return <div ref={containerRef} className={className} data-testid="turnstile-widget" />
}
