import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { clearRememberMarker } from '@/lib/remember-session'
import { supabase } from '@/lib/supabase'
import { notify } from '@/lib/feedback'

import { buildRedirectTo } from '../lib/redirect'
import { isAppleAuthEnabled } from '../lib/password-auth'

// Monochrome Brand-Glyphen als currentColor-SVG — kein Brand-Hex, erbt die
// Textfarbe des Buttons und bleibt damit im Token-System (Dark/Light).
// lucide-react (1.x) fuehrt keine Brand-Icons mehr, daher inline.
function GoogleGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="currentColor">
      <path d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z" />
    </svg>
  )
}

function GithubGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="currentColor">
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222 0 1.606-.014 2.898-.014 3.293 0 .322.216.694.825.576C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  )
}

function AppleGlyph() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4" fill="currentColor">
      <path d="M17.05 12.536c.019 2.86 2.5 3.81 2.53 3.823-.02.064-.4 1.37-1.32 2.72-.795 1.166-1.62 2.33-2.92 2.354-1.277.024-1.688-.758-3.148-.758-1.46 0-1.917.734-3.126.782-1.254.048-2.208-1.262-3.01-2.424-1.75-2.534-3.086-7.16-1.29-10.286.89-1.552 2.484-2.535 4.213-2.56 1.232-.024 2.395.83 3.148.83.753 0 2.166-1.026 3.652-.875.622.026 2.37.226 3.492 1.7-.09.057-2.085 1.219-2.06 3.635zM14.68 3.9c.666-.806 1.115-1.929.993-3.047-.986.04-2.18.657-2.868 1.462-.617.713-1.157 1.856-1.012 2.951 1.1.085 2.221-.559 2.888-1.366z" />
    </svg>
  )
}

// Social-Login (Track K): GoTrue External Provider. supabase-js leitet den
// Browser auf `${SUPABASE_URL}/auth/v1/authorize?provider=…&redirect_to=…`,
// GoTrue spricht mit Google/GitHub/Apple und schickt den Browser danach an
// unsere `redirect_to` (die Callback-Route) zurueck — Tokens kommen im URL-Hash
// (implicit flow). `redirect_to` ist immer ein In-App-Pfad auf unserem Origin.
//
// Apple laeuft denselben Weg, mit zwei Eigenheiten, die GoTrue v2.196.0 selbst
// abfaengt und die hier nur der Nachvollziehbarkeit wegen stehen:
//   * Apple antwortet per POST auf die Callback-Route (`response_mode=form_post`,
//     internal/api/provider/apple.go) — GoTrue registriert GET und POST.
//   * Name und E-Mail liefert Apple NUR beim allerersten Login, im POST-Feld
//     `user`; GoTrue liest es dort aus (internal/api/external_oauth.go) und legt
//     es in die User-Metadaten. Unsere Callback-Seite muss nichts nachholen.
type Provider = 'google' | 'github' | 'apple'

// `disabled` gated den Social-Login z. B. solange die Signup-Consent-Checkbox
// nicht gesetzt ist (WP-I). Default false → Login bleibt unveraendert.
export function OAuthButtons({
  next,
  disabled = false,
}: {
  next?: string | null
  disabled?: boolean
}) {
  const { t } = useTranslation('auth')
  const [pending, setPending] = useState<Provider | null>(null)

  async function signInWith(provider: Provider) {
    setPending(provider)
    // Nur die Login-Checkbox darf "angemeldet bleiben" einschalten. Ein aus
    // einer frueheren Sitzung stehengebliebener Marker haette die
    // OAuth-Session sonst ungefragt auf die Platte gelegt (Security-Review
    // MEDIUM-6).
    clearRememberMarker()
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo: buildRedirectTo('/auth/callback', next) },
    })
    if (error) {
      setPending(null)
      notify.error(error.message)
    }
    // Kein Reset im Erfolgsfall: der Browser navigiert weg zum Provider.
  }

  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={() => void signInWith('google')}
        disabled={disabled || pending !== null}
      >
        <GoogleGlyph />
        {t('oauth.google')}
      </Button>
      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={() => void signInWith('github')}
        disabled={disabled || pending !== null}
      >
        <GithubGlyph />
        {t('oauth.github')}
      </Button>
      {isAppleAuthEnabled() ? (
        <Button
          type="button"
          variant="outline"
          className="w-full"
          onClick={() => void signInWith('apple')}
          disabled={disabled || pending !== null}
        >
          <AppleGlyph />
          {t('oauth.apple')}
        </Button>
      ) : null}
    </div>
  )
}
