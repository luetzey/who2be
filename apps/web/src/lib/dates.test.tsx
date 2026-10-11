import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ProvenanceEntry } from '@/api/types'
import { ProvenanceList } from '@/components/version/ProvenanceList'
import { ActivityRow } from '@/features/dashboard/components/ActivityRow'
import i18n from '@/i18n'

import { formatDate, formatDateTime, uiLocale } from './dates'

// Befund aus dem E2E-Lauf: Browser en-US, UI deutsch -> "10/9/2026, 7:11:53 AM".
// Die Default-Locale von Node/ICU haengt an der Maschine (LANG). Damit der Test
// ueberall dasselbe prueft, zwingen wir argumentlose `toLocale*String()`-Aufrufe
// auf en-US — genau das tut ein en-US-Browser. Explizit uebergebene Locales
// laufen unveraendert durch.
const ISO = '2026-10-09T07:11:53Z'

function forceBrowserLocale(locale: string) {
  const original = {
    toLocaleString: Date.prototype.toLocaleString,
    toLocaleDateString: Date.prototype.toLocaleDateString,
  }
  vi.spyOn(Date.prototype, 'toLocaleString').mockImplementation(function (
    this: Date,
    locales?: Intl.LocalesArgument,
    options?: Intl.DateTimeFormatOptions,
  ) {
    return original.toLocaleString.call(this, locales ?? locale, options)
  })
  vi.spyOn(Date.prototype, 'toLocaleDateString').mockImplementation(function (
    this: Date,
    locales?: Intl.LocalesArgument,
    options?: Intl.DateTimeFormatOptions,
  ) {
    return original.toLocaleDateString.call(this, locales ?? locale, options)
  })
}

const date = new Date(ISO)
const deDate = date.toLocaleDateString('de')
const deDateTime = date.toLocaleString('de')
const enDate = date.toLocaleDateString('en-US')
const enDateTime = date.toLocaleString('en-US')

beforeEach(async () => {
  await i18n.changeLanguage('de')
  forceBrowserLocale('en-US')
})

afterEach(async () => {
  vi.restoreAllMocks()
  await i18n.changeLanguage('de')
})

describe('lib/dates — Browser en-US, UI deutsch', () => {
  it('die Simulation greift: argumentlos kommt das en-US-Format', () => {
    // Vorbedingung: ohne diese Gegenprobe waere der Test auch mit altem Code gruen.
    expect(date.toLocaleString()).toBe(enDateTime)
    expect(deDateTime).not.toBe(enDateTime)
  })

  it('formatDate/formatDateTime folgen der UI-Sprache', () => {
    expect(uiLocale()).toBe('de')
    expect(formatDate(ISO)).toBe(deDate)
    expect(formatDateTime(ISO)).toBe(deDateTime)
    expect(formatDateTime(ISO)).not.toMatch(/AM|PM/)
  })

  it('nimmt Date, String und Zeitstempel und reicht Optionen durch', () => {
    expect(formatDate(date)).toBe(deDate)
    expect(formatDate(date.getTime())).toBe(deDate)
    expect(formatDate(ISO, { dateStyle: 'long' })).toBe(
      date.toLocaleDateString('de', { dateStyle: 'long' }),
    )
  })

  it('schaltet mit der UI-Sprache auf Englisch um', async () => {
    await i18n.changeLanguage('en')
    expect(uiLocale()).toBe('en')
    expect(formatDate(ISO)).toBe(date.toLocaleDateString('en'))
    expect(formatDateTime(ISO)).toBe(date.toLocaleString('en'))
  })
})

describe('Stellen in der Oberflaeche — Browser en-US, UI deutsch', () => {
  it('ProvenanceList zeigt den Zeitpunkt deutsch', () => {
    const entry: ProvenanceEntry = {
      id: 'h1',
      entity_type: 'playbook',
      entity_id: 'pb1',
      version: 1,
      from_status: 'draft',
      to_status: 'active',
      changed_by: 'u1',
      changed_at: ISO,
      note: null,
    }
    render(<ProvenanceList entries={[entry]} />)
    expect(screen.getByText(deDateTime)).toBeInTheDocument()
    expect(screen.queryByText(enDateTime)).not.toBeInTheDocument()
  })

  it('ActivityRow zeigt die Zeit deutsch', () => {
    render(
      <ActivityRow
        activity={{ ts: ISO, entity_type: 'playbook', entity_id: 'pb1', event: 'created' }}
      />,
    )
    const time = document.querySelector('time')
    expect(time).toHaveTextContent(deDateTime)
    expect(time).not.toHaveTextContent(enDate)
  })
})
