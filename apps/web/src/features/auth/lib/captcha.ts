// Gemeinsame Captcha-Logik fuer alle Auth-Pfade, die GoTrue hinter der
// Captcha-Middleware fuehrt (Issue #539 / Folgebefund).
//
// GoTrue v2.158.1 haengt `verifyCaptcha` an `/signup`, `/recover`, `/resend`,
// `/magiclink`, `/otp`, `/token` und `/sso` (internal/api/api.go:138-267);
// `isIgnoreCaptchaRoute` (middleware.go:190-196) nimmt nur `/token` mit
// `grant_type != password` aus. Die App ruft davon `/signup`, `/token`
// (Passwort-Login), `/resend` und `/recover` auf — alle vier brauchen dasselbe
// Verhalten, deshalb liegt es hier und nicht in einer der Seiten.

/**
 * Erkennt die Captcha-Abweisung von GoTrue.
 *
 * GoTrue meldet sie mit `code: "captcha_failed"` und der Meldung
 * „captcha protection: request disallowed (…)" (v2.158.1,
 * internal/api/errorcodes.go:44, middleware.go:184-186). Das ist eine
 * Server-Diagnose, keine Nutzer-Nachricht. Der Code wird bevorzugt, weil er
 * stabil ist; die Regex faengt aeltere/abweichende Antworten und den Fall ab,
 * dass der Client-Typ das Feld nicht traegt.
 */
export function isCaptchaError(cause: unknown): boolean {
  if (typeof cause !== 'object' || cause === null) return false
  const code = (cause as { code?: unknown }).code
  if (code === 'captcha_failed') return true
  const message = (cause as { message?: unknown }).message
  return typeof message === 'string' && /captcha/i.test(message)
}

/**
 * Uebersetzt den GoTrue-Fehler in eine Meldung, die ein Mensch versteht.
 *
 * Alles ausser dem Captcha-Fall bleibt bewusst unveraendert beim
 * Original-Text — eine pauschale „Es ist ein Fehler aufgetreten"-Huelle wuerde
 * hier mehr Information vernichten als sie an Klarheit bringt.
 */
export function translateAuthError(cause: unknown, t: (key: string) => string): string {
  if (isCaptchaError(cause)) {
    return t('captcha.failed')
  }
  if (cause instanceof Error) {
    return cause.message
  }
  // Nicht jeder Fehlerwert kommt als Error-Instanz an: `AuthError` ueberlebt
  // eine Strukturkopie nicht, und einzelne Supabase-Pfade reichen ein nacktes
  // `{ message }` durch. `String(cause)` machte daraus „[object Object]" —
  // die Meldung zu lesen ist hier die einzig ehrliche Antwort.
  const message = (cause as { message?: unknown } | null)?.message
  return typeof message === 'string' ? message : String(cause)
}

/**
 * Baut den `captchaToken`-Teil der Supabase-Optionen.
 *
 * Bewusst ein Spread-Fragment statt `{ captchaToken: token ?? undefined }`:
 * ein explizit auf `undefined` gesetztes Feld ist fuer die Laufzeit derselbe
 * Zustand, aber nicht fuer einen `toHaveBeenCalledWith`-Vergleich — und genau
 * das ist die Zusicherung, die „ohne Captcha bleibt alles wie vorher"
 * ueberhaupt pruefbar macht.
 */
export function captchaOption(token: string | null): { captchaToken?: string } {
  return token !== null ? { captchaToken: token } : {}
}
