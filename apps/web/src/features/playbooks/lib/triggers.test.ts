import { describe, expect, it } from 'vitest'

import { joinTriggers, splitTriggers } from './triggers'

describe('splitTriggers', () => {
  it('liefert ein leeres Array fuer null, leer und nur Whitespace', () => {
    expect(splitTriggers(null)).toEqual([])
    expect(splitTriggers('')).toEqual([])
    expect(splitTriggers('   ')).toEqual([])
  })

  it('zerlegt eine Komma-Liste in Trim-getrimmte Eintraege', () => {
    expect(splitTriggers('passwort vergessen, reset link, mail')).toEqual([
      'passwort vergessen',
      'reset link',
      'mail',
    ])
  })

  it('schluckt Anfuehrungszeichen aus der alten Eingabeform', () => {
    expect(splitTriggers('"passwort vergessen", "reset link"')).toEqual([
      'passwort vergessen',
      'reset link',
    ])
  })

  it('filtert Leereintraege (Mehrfach-Komma) raus', () => {
    expect(splitTriggers('a, , b,,c')).toEqual(['a', 'b', 'c'])
  })

  it('zerlegt auch Semikolon-Listen (Legacy-Eingabeform, WP-D1)', () => {
    expect(splitTriggers('passwort vergessen; reset link;mail')).toEqual([
      'passwort vergessen',
      'reset link',
      'mail',
    ])
  })

  it('zerlegt gemischte Komma-/Semikolon-Listen und filtert Leereintraege', () => {
    expect(splitTriggers('a, b; c;, d')).toEqual(['a', 'b', 'c', 'd'])
    expect(splitTriggers(' ; , ')).toEqual([])
  })
})

describe('joinTriggers', () => {
  it('verbindet Eintraege mit ", "', () => {
    expect(joinTriggers(['a', 'b', 'c'])).toBe('a, b, c')
  })

  it('liefert null, wenn keine relevanten Eintraege uebrig sind', () => {
    expect(joinTriggers([])).toBeNull()
    expect(joinTriggers(['  ', ''])).toBeNull()
  })

  it('trimmt einzelne Eintraege', () => {
    expect(joinTriggers([' a ', 'b'])).toBe('a, b')
  })
})
