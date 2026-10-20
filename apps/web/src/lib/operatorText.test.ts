import { describe, expect, test } from 'vitest'

import {
  FREE_TEXT_MAX_LENGTH,
  pickLocalizedText,
  resolveFreeText,
  resolveNoticeLevel,
} from './operatorText'

describe('resolveFreeText', () => {
  test('trimmt und laesst kurze Texte unveraendert', () => {
    expect(resolveFreeText('  Wartung "heute"\nZeile 2  ')).toBe('Wartung "heute"\nZeile 2')
    expect(resolveFreeText(undefined)).toBe('')
  })

  test('kappt auf die Obergrenze (Code-Points) und haengt … an', () => {
    const result = resolveFreeText('😀'.repeat(FREE_TEXT_MAX_LENGTH + 50))

    expect(Array.from(result)).toHaveLength(FREE_TEXT_MAX_LENGTH)
    expect(result.endsWith('…')).toBe(true)
    expect(resolveFreeText('x'.repeat(FREE_TEXT_MAX_LENGTH))).toHaveLength(FREE_TEXT_MAX_LENGTH)
  })
})

describe('pickLocalizedText', () => {
  test('aktive Sprache, sonst die andere', () => {
    expect(pickLocalizedText({ de: 'DE', en: 'EN' }, 'en-US')).toBe('EN')
    expect(pickLocalizedText({ de: 'DE', en: 'EN' }, 'de')).toBe('DE')
    expect(pickLocalizedText({ de: 'DE', en: '' }, 'en')).toBe('DE')
    expect(pickLocalizedText({ de: '', en: 'EN' }, 'de')).toBe('EN')
    expect(pickLocalizedText({ de: '', en: '' }, 'en')).toBe('')
  })

  test('fehlendes Objekt ergibt Leerstring', () => {
    expect(pickLocalizedText(undefined, 'de')).toBe('')
  })
})

describe('resolveNoticeLevel', () => {
  test('nur warning ist warning, alles andere info', () => {
    expect(resolveNoticeLevel('warning')).toBe('warning')
    expect(resolveNoticeLevel('info')).toBe('info')
    expect(resolveNoticeLevel('ALERT')).toBe('info')
    expect(resolveNoticeLevel(undefined)).toBe('info')
  })
})
