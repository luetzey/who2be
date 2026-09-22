import { describe, expect, it } from 'vitest'

import { captchaOption, isCaptchaError, translateAuthError } from './captcha'

// Uebersetzt Schluessel identisch zurueck — so ist im Test sichtbar, WELCHER
// Schluessel gezogen wurde, statt nur dass irgendein Text ankam.
const t = (key: string) => key

describe('isCaptchaError', () => {
  it('erkennt den stabilen GoTrue-Code', () => {
    // errorcodes.go:44 (v2.158.1) — der Code ist der verlaessliche Teil.
    expect(isCaptchaError({ code: 'captcha_failed' })).toBe(true)
  })

  it('erkennt die Meldung, wenn der Client-Typ den Code nicht traegt', () => {
    expect(
      isCaptchaError(new Error('captcha protection: request disallowed (invalid-input-response)')),
    ).toBe(true)
  })

  it('haelt fremde Fehler heraus', () => {
    expect(isCaptchaError(new Error('Invalid login credentials'))).toBe(false)
    expect(isCaptchaError({ code: 'email_not_confirmed' })).toBe(false)
  })

  it('faellt bei Nicht-Objekten nicht um', () => {
    expect(isCaptchaError(null)).toBe(false)
    expect(isCaptchaError(undefined)).toBe(false)
    expect(isCaptchaError('captcha')).toBe(false)
    expect(isCaptchaError(42)).toBe(false)
  })
})

describe('translateAuthError', () => {
  it('ersetzt die Captcha-Abweisung durch die lokalisierte Meldung', () => {
    expect(translateAuthError({ code: 'captcha_failed' }, t)).toBe('captcha.failed')
  })

  it('laesst jeden anderen GoTrue-Text im Wortlaut stehen', () => {
    expect(translateAuthError(new Error('User already registered'), t)).toBe(
      'User already registered',
    )
  })

  it('stringifiziert, was keine Error-Instanz ist', () => {
    expect(translateAuthError('kaputt', t)).toBe('kaputt')
  })

  it('liest die Meldung aus einem nackten `{ message }` statt "[object Object]" zu zeigen', () => {
    expect(translateAuthError({ message: 'over_email_send_rate_limit' }, t)).toBe(
      'over_email_send_rate_limit',
    )
  })
})

describe('captchaOption', () => {
  it('liefert bei null ein LEERES Objekt, nicht `{ captchaToken: undefined }`', () => {
    const option = captchaOption(null)
    expect(option).toEqual({})
    // Genau diese Zusicherung traegt „ohne Captcha bleibt alles wie vorher":
    // ein gesetztes Feld mit Wert `undefined` wuerde `toHaveBeenCalledWith`
    // brechen, obwohl es zur Laufzeit dasselbe waere.
    expect(option).not.toHaveProperty('captchaToken')
  })

  it('traegt das Token, wenn eines da ist', () => {
    expect(captchaOption('token-abc')).toEqual({ captchaToken: 'token-abc' })
  })
})
