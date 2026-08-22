import { act } from 'react'
import { afterEach, describe, expect, it } from 'vitest'

import i18n from '@/i18n'

// Regressionstest fuer den `documentElement.lang`-Sync (WP2, Issue #408):
// Screenreader-Aussprache und Browser-Uebersetzungsangebot haengen daran, und
// `htmlTag` ist die letzte Stufe der Detektor-Kette in `src/i18n/index.ts` —
// ohne Sync wuerde das Attribut dauerhaft auf dem statischen `index.html`-Wert
// stehen bleiben.

afterEach(async () => {
  await act(async () => {
    await i18n.changeLanguage('de')
  })
})

describe('documentElement.lang sync', () => {
  it('folgt der aktiven Sprache nach einem Wechsel auf Englisch', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(document.documentElement.lang).toBe('en')
  })

  it('folgt zurueck auf Deutsch', async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })
    expect(document.documentElement.lang).toBe('en')

    await act(async () => {
      await i18n.changeLanguage('de')
    })

    expect(document.documentElement.lang).toBe('de')
  })
})
