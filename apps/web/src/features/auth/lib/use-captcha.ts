import { useCallback, useState } from 'react'

import { config } from '@/config'

import { captchaOption } from './captcha'

export interface CaptchaState {
  /** Ist ein Site-Key konfiguriert? Nur dann wird ueberhaupt ein Widget gezeigt. */
  required: boolean
  /** Aktuelles Token, `null` = noch nicht geloest bzw. verbraucht/abgelaufen. */
  token: string | null
  /**
   * Remount-Schluessel fuer das Widget. Turnstile-Tokens sind EINMALIG
   * gueltig; nach jedem verbrauchten Token muss die Challenge neu gestellt
   * werden. Ein `key`-Wechsel ist dafuer der ehrlichste Weg — er erzwingt den
   * Cleanup (`turnstile.remove`) und einen frischen `render`, statt auf eine
   * imperative Handle-API zu bauen, die nur fuer diesen einen Fall existiert.
   */
  nonce: number
  /** Callback fuer `TurnstileWidget.onToken`. */
  setToken: (token: string) => void
  /** Callback fuer `TurnstileWidget.onExpire` — Token verwerfen, Widget stehen lassen. */
  clearToken: () => void
  /**
   * Token verwerfen UND das Widget neu stellen. Nach jedem Request, der das
   * Token verbraucht hat — auch nach einem erfolgreichen: GoTrue loest es
   * serverseitig ein, ein zweiter Request mit demselben Token scheitert.
   */
  reset: () => void
  /**
   * `{ captchaToken }` oder ein leeres Objekt zum Spreaden in die
   * Supabase-Optionen. Ohne Site-Key ist es immer leer, der Aufruf bleibt
   * damit byte-identisch zum Zustand vor Issue #539.
   */
  option: () => { captchaToken?: string }
  /** Submit sperren: Site-Key gesetzt, aber noch kein Token geloest. */
  blocked: boolean
}

/**
 * Haelt den Captcha-Zustand einer Auth-Maske (Issue #539 / Folgebefund).
 *
 * Vier Masken brauchen exakt denselben Dreiklang aus Token, Remount-Nonce und
 * „ist ueberhaupt ein Site-Key gesetzt?" — Signup, Login, „Mail erneut
 * senden" und Passwort-vergessen. Dieser Hook ist die eine Stelle dafuer; die
 * Seite entscheidet nur noch ueber Platzierung und `action`.
 */
export function useCaptcha(): CaptchaState {
  const required = config.turnstileSiteKey !== ''
  const [token, setTokenState] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)

  const setToken = useCallback((value: string) => setTokenState(value), [])
  const clearToken = useCallback(() => setTokenState(null), [])
  const reset = useCallback(() => {
    if (!required) return
    setTokenState(null)
    setNonce((value) => value + 1)
  }, [required])
  const option = useCallback(() => captchaOption(token), [token])

  return {
    required,
    token,
    nonce,
    setToken,
    clearToken,
    reset,
    option,
    blocked: required && token === null,
  }
}
