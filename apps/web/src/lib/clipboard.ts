/**
 * Browser-Clipboard mit Fallback fuer Non-Secure-Contexts.
 *
 * `navigator.clipboard` ist nur in Secure-Contexts verfuegbar (HTTPS oder
 * literal `localhost`/`127.0.0.1`). Eine selbst-gehostete Who2Be-Instanz auf
 * z.B. `http://app.intranet.firma:8088` faellt aus dieser Definition heraus —
 * dort ist `navigator.clipboard` `undefined` und ein direkter `.writeText()`
 * crasht mit `TypeError: Cannot read properties of undefined`.
 *
 * Strategie:
 *  1. Falls vorhanden: moderne Clipboard-API.
 *  2. Sonst: `document.execCommand('copy')` ueber eine unsichtbare Textarea
 *     (deprecated, aber in allen relevanten Engines noch unterstuetzt).
 *  3. Sonst (z.B. Headless ohne Document): hard fail mit eindeutiger Message,
 *     damit Caller einen Error-Toast statt eines kryptischen Stacktraces zeigen.
 */
import i18n from '@/i18n'

export async function copyToClipboard(text: string): Promise<void> {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return
    } catch {
      // Permissions-Policy oder andere Verbote — auf execCommand-Fallback gehen.
    }
  }
  if (typeof document === 'undefined') {
    throw new Error(i18n.t('common:errors.clipboardUnavailable'))
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  // Sichtbar genug, dass `execCommand('copy')` greift; visuell verborgen.
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '0'
  textarea.style.width = '1px'
  textarea.style.height = '1px'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  textarea.setSelectionRange(0, text.length)
  let ok: boolean
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  } finally {
    document.body.removeChild(textarea)
  }
  if (!ok) {
    throw new Error(i18n.t('common:errors.clipboardUnavailable'))
  }
}
