import { describe, expect, it } from 'vitest'

import { safeInternalPath } from './safePath'

describe('safeInternalPath', () => {
  it.each([
    ['/w/ws-1/personas/p1'],
    ['/w/ws-1/personas/p1?tab=versions&diff=2'],
    ['/invitations/abc/accept?via=magic#top'],
    ['/'],
  ])('laesst den In-App-Pfad %s durch', (path) => {
    expect(safeInternalPath(path)).toBe(path)
  })

  // Negativproben aus der Karte t_dfd5ff9f plus die bekannten Umgehungen.
  it.each([
    ['absolute URL', 'https://evil.example'],
    ['protokoll-relativ', '//evil.example'],
    ['Backslash', '/\\evil.example'],
    ['Backslash-Slash', '/\\/evil.example'],
    ['javascript:', 'javascript:alert(1)'],
    ['javascript: mit Slash davor', '/javascript://%0Aalert(1)'],
    ['Tab im Pfad (Browser streicht ihn)', '/\t/evil.example'],
    ['Zeilenumbruch', '/\n/evil.example'],
    ['Protokoll im Pfad', '/redirect?to=https://evil.example'],
    ['relativer Pfad', 'w/ws-1/personas'],
    ['leer', ''],
  ])('verwirft %s', (_label, raw) => {
    expect(safeInternalPath(raw)).toBeNull()
  })

  it('verwirft null und undefined', () => {
    expect(safeInternalPath(null)).toBeNull()
    expect(safeInternalPath(undefined)).toBeNull()
  })
})
