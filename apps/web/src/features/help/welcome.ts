import type { Tutorial } from '@/api/client'

/*
 * Taktung und Erfolgs-Regel der Begruessung (Onboarding P6), getrennt vom
 * Dialog, damit Tests und Komponente dieselben Werte nutzen.
 */

// Warten auf den ersten Abruf (Owner O6 a): alle 5 s und bei Rueckkehr in den
// Tab, hoechstens 10 Minuten; nach 2 Minuten zusaetzlich „Ja, weiter“.
export const WELCOME_POLL_INTERVAL_MS = 5_000
export const WELCOME_CONFIRM_AFTER_MS = 2 * 60_000
export const WELCOME_POLL_LIMIT_MS = 10 * 60_000

const SUCCESS_STEP_TYPE = 'first_mcp_call'

/** Erledigt = der automatische Verbinden-Schritt des Tutorials ist abgehakt. */
export function connectStepDone(tutorial: Pick<Tutorial, 'steps'> | undefined): boolean {
  const step = tutorial?.steps.find((item) => item.type === SUCCESS_STEP_TYPE)
  return step?.state === 'done'
}
