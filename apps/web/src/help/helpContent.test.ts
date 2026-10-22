import { describe, expect, it } from 'vitest'

import {
  buildHelpIndex,
  findPage,
  helpIndex,
  internalHelpLinks,
  newsFor,
  safeHelpHref,
  searchHelp,
  toHelpLocale,
} from './helpIndex'

/*
 * Inhaltstest Hilfe-Bereich (Onboarding P4). Der echte Index muss fehlerfrei
 * sein; mit Testdaten wird belegt, dass ein neues Tutorial bzw. eine neue Seite
 * allein aus Dateien entsteht und ungueltiges Frontmatter rot wird.
 * Die Paritaet Tutorial-Text ↔ Server-Katalog prueft
 * `packages/models/tests/test_tutorial_help_parity.py`.
 */

const tutorial = (lang: string, extra = '', steps = ['eins', 'zwei']) =>
  [
    '---',
    'tutorial: demo',
    `title: Demo ${lang}`,
    'description: Ein Test-Tutorial.',
    'duration: 3',
    ...(extra === '' ? [] : [extra]),
    '---',
    '',
    'Einleitung.',
    '',
    ...steps.flatMap((id) => [`## Schritt ${id} [#${id}]`, '', `Text zu ${id}.`, '']),
  ].join('\n')

const page = (lang: string, overrides: Record<string, string> = {}, body = '') => {
  const fields = {
    title: `Persona ${lang}`,
    description: 'Was eine Persona ist.',
    section: 'bausteine',
    order: '1',
    updated: '2026-10-21',
    audience: 'all',
    ...overrides,
  }
  return [
    '---',
    ...Object.entries(fields)
      .filter(([, value]) => value !== '')
      .map(([key, value]) => `${key}: ${value}`),
    '---',
    '',
    'Eine Persona beschreibt Rolle und Ton.',
    '',
    '## Felder [#felder]',
    '',
    body || 'Identität, Ton, Grenzen.',
    '',
  ].join('\n')
}

const validFiles = {
  '/src/help/tutorials/demo.de.md': tutorial('de'),
  '/src/help/tutorials/demo.en.md': tutorial('en'),
  '/src/help/bausteine/persona.de.md': page('de'),
  '/src/help/bausteine/persona.en.md': page('en'),
}

describe('helpIndex: ausgelieferter Inhalt', () => {
  it('ist fehlerfrei und enthält das Tutorial „Erste Schritte“ in beiden Sprachen', () => {
    expect(helpIndex.errors).toEqual([])
    for (const locale of ['de', 'en']) {
      const entry = helpIndex.tutorials.find((t) => t.slug === 'getting-started' && t.locale === locale)
      expect(entry?.blocks.map((b) => b.id)).toEqual([
        'builder-ready',
        'connect-claude',
        'build-own-agent',
        'learn-feedback',
      ])
    }
    // „Was ist neu“: mindestens ein Eintrag, in beiden Sprachen gleich viele.
    expect(newsFor(helpIndex, 'de').length).toBeGreaterThan(0)
    expect(newsFor(helpIndex, 'en').length).toBe(newsFor(helpIndex, 'de').length)
  })
})

describe('buildHelpIndex: neues Tutorial und neue Seite nur aus Dateien', () => {
  it('nimmt beide ohne Code-Änderung auf', () => {
    const index = buildHelpIndex(validFiles)
    expect(index.errors).toEqual([])
    // Gleiches Ergebnis mit den relativen Schluesseln von `import.meta.glob`.
    const relative = Object.fromEntries(
      Object.entries(validFiles).map(([path, raw]) => [path.replace('/src/help/', './'), raw]),
    )
    expect(buildHelpIndex(relative)).toEqual(index)
    expect(index.tutorials.map((t) => `${t.slug}.${t.locale}`)).toEqual(['demo.de', 'demo.en'])
    const de = index.tutorials.find((t) => t.locale === 'de')
    expect(de).toMatchObject({ title: 'Demo de', durationMinutes: 3, intro: 'Einleitung.' })
    expect(de?.blocks.map((b) => b.id)).toEqual(['eins', 'zwei'])
    expect(findPage(index, 'en', 'persona')).toMatchObject({
      section: 'bausteine',
      audience: 'all',
      updated: '2026-10-21',
    })
  })
})

describe('buildHelpIndex: ungültiger Inhalt wird rot', () => {
  const cases: Array<[string, Record<string, string>, RegExp]> = [
    [
      'Frontmatter fehlt',
      { ...validFiles, '/src/help/tutorials/demo.de.md': 'Kein Frontmatter' },
      /Frontmatter fehlt/,
    ],
    [
      'Pflichtfeld fehlt',
      { ...validFiles, '/src/help/bausteine/persona.de.md': page('de', { updated: '' }) },
      /Pflichtfeld "updated" fehlt/,
    ],
    [
      'unbekanntes Feld',
      { ...validFiles, '/src/help/tutorials/demo.de.md': tutorial('de', 'audience: everyone') },
      /unbekanntes Feld "audience"/,
    ],
    [
      'duration keine Zahl',
      {
        ...validFiles,
        '/src/help/tutorials/demo.de.md': tutorial('de').replace('duration: 3', 'duration: kurz'),
      },
      /duration muss eine ganze Zahl/,
    ],
    [
      'tutorial passt nicht zum Dateinamen',
      {
        ...validFiles,
        '/src/help/tutorials/demo.de.md': tutorial('de').replace('tutorial: demo', 'tutorial: x'),
      },
      /passt nicht zum Dateinamen/,
    ],
    [
      'unbekannter Abschnitt',
      { ...validFiles, '/src/help/bausteine/persona.de.md': page('de', { section: 'sonstiges' }) },
      /kein fester Abschnitt/,
    ],
    [
      'falsches Datum',
      { ...validFiles, '/src/help/bausteine/persona.de.md': page('de', { updated: '21.10.2026' }) },
      /JJJJ-MM-TT/,
    ],
    [
      'Sprache fehlt',
      { '/src/help/tutorials/demo.de.md': tutorial('de') },
      /tutorial "demo" fehlt in en/,
    ],
    [
      'Anker DE ≠ EN',
      {
        ...validFiles,
        '/src/help/tutorials/demo.en.md': tutorial('en', '', ['eins', 'drei']),
      },
      /Anker DE \[eins,zwei\] ≠ EN \[eins,drei\]/,
    ],
    [
      'Überschrift ohne Anker',
      {
        ...validFiles,
        '/src/help/bausteine/persona.de.md': page('de', {}, '## Ohne Anker'),
      },
      /Überschrift ohne Anker/,
    ],
    [
      'HTML im Text',
      {
        ...validFiles,
        '/src/help/bausteine/persona.de.md': page('de', {}, '<script>alert(1)</script>'),
      },
      /HTML ist nicht erlaubt/,
    ],
    [
      'unsicherer Link',
      {
        ...validFiles,
        '/src/help/bausteine/persona.de.md': page('de', {}, '[klick](javascript:alert(1))'),
      },
      /Link "javascript:alert\(1" ist nicht erlaubt/,
    ],
    [
      'Link auf unbekannten Anker',
      {
        ...validFiles,
        '/src/help/bausteine/persona.de.md': page('de', {}, 'Siehe [Felder](/help/persona#fehlt).'),
      },
      /Anker "#fehlt" fehlt in "persona"/,
    ],
    [
      'reservierter Slug',
      {
        ...validFiles,
        '/src/help/bausteine/tutorials.de.md': page('de'),
        '/src/help/bausteine/tutorials.en.md': page('en'),
      },
      /für eine Route reserviert/,
    ],
  ]

  it.each(cases)('%s', (_name, files, expected) => {
    const index = buildHelpIndex(files)
    expect(index.errors.join('\n')).toMatch(expected)
  })

  it('lässt ungültige Dateien aus dem Index heraus', () => {
    const index = buildHelpIndex({
      ...validFiles,
      '/src/help/bausteine/persona.de.md': page('de', { audience: 'alle' }),
    })
    expect(findPage(index, 'de', 'persona')).toBeNull()
    expect(findPage(index, 'en', 'persona')).not.toBeNull()
  })

  it('ignoriert Überschriften in Code-Blöcken', () => {
    const index = buildHelpIndex({
      ...validFiles,
      '/src/help/bausteine/persona.de.md': page('de', {}, '```\n# kein Titel\n```'),
    })
    expect(index.errors).toEqual([])
  })
})

const news = (
  lang: string,
  fields: Record<string, string> = {},
  body = 'Ein Satz zur Neuerung.',
) => {
  const all = {
    date: '2026-11-13',
    type: 'new',
    title: `Hilfe-Bereich ${lang}`,
    link: '/help/persona#felder',
    ...fields,
  }
  return [
    '---',
    ...Object.entries(all)
      .filter(([, value]) => value !== '')
      .map(([key, value]) => `${key}: ${value}`),
    '---',
    '',
    body,
    '',
  ].join('\n')
}

const newsFiles = {
  ...validFiles,
  '/src/help/news/2026-11-13-hilfe.de.md': news('de'),
  '/src/help/news/2026-11-13-hilfe.en.md': news('en'),
  '/src/help/news/2026-10-02-start.de.md': news('de', { date: '2026-10-02', type: 'improved', link: '' }),
  '/src/help/news/2026-10-02-start.en.md': news('en', { date: '2026-10-02', type: 'improved', link: '' }),
}

describe('buildHelpIndex: „Was ist neu“ nur aus Dateien', () => {
  it('nimmt Einträge ohne Code-Änderung auf, neueste zuerst, je Sprache', () => {
    const index = buildHelpIndex(newsFiles)
    expect(index.errors).toEqual([])
    expect(newsFor(index, 'de').map((n) => n.slug)).toEqual(['2026-11-13-hilfe', '2026-10-02-start'])
    expect(newsFor(index, 'en')[0]).toMatchObject({
      kind: 'news',
      date: '2026-11-13',
      type: 'new',
      title: 'Hilfe-Bereich en',
      link: '/help/persona#felder',
      body: 'Ein Satz zur Neuerung.',
    })
    expect(newsFor(index, 'de')[1].link).toBeNull()
    // News sind keine Seiten und keine Suchtreffer.
    expect(index.pages.map((p) => p.slug)).not.toContain('2026-11-13-hilfe')
  })

  const cases: Array<[string, Record<string, string>, RegExp]> = [
    [
      'Sprache fehlt',
      { ...validFiles, '/src/help/news/2026-11-13-hilfe.de.md': news('de') },
      /news "2026-11-13-hilfe" fehlt in en/,
    ],
    [
      'unbekannter Typ',
      { ...newsFiles, '/src/help/news/2026-11-13-hilfe.de.md': news('de', { type: 'fix' }) },
      /type "fix" ist nicht new, improved oder changed/,
    ],
    [
      'Datum passt nicht zum Dateinamen',
      { ...newsFiles, '/src/help/news/2026-11-13-hilfe.de.md': news('de', { date: '2026-11-14' }) },
      /muss mit dem Datum "2026-11-14-" beginnen/,
    ],
    [
      'Pflichtfeld fehlt',
      { ...newsFiles, '/src/help/news/2026-11-13-hilfe.de.md': news('de', { title: '' }) },
      /Pflichtfeld "title" fehlt/,
    ],
    [
      'unbekanntes Feld',
      { ...newsFiles, '/src/help/news/2026-11-13-hilfe.de.md': news('de', { audience: 'all' }) },
      /unbekanntes Feld "audience"/,
    ],
    [
      'link nach außen',
      {
        ...newsFiles,
        '/src/help/news/2026-11-13-hilfe.de.md': news('de', { link: 'https://who2be.de' }),
      },
      /link "https:\/\/who2be.de" muss \/help\/<slug>/,
    ],
    [
      'link auf unbekannte Seite',
      { ...newsFiles, '/src/help/news/2026-11-13-hilfe.de.md': news('de', { link: '/help/fehlt' }) },
      /link auf unbekannte Seite "fehlt"/,
    ],
    [
      'link auf unbekannten Anker',
      {
        ...newsFiles,
        '/src/help/news/2026-11-13-hilfe.de.md': news('de', { link: '/help/persona#weg' }),
      },
      /Anker "#weg" fehlt in "persona"/,
    ],
    [
      'Überschrift im Text',
      {
        ...newsFiles,
        '/src/help/news/2026-11-13-hilfe.de.md': news('de', {}, '## Mehr [#mehr]\n\nText'),
      },
      /haben keine Überschriften/,
    ],
    [
      'unsicherer Link im Text',
      {
        ...newsFiles,
        '/src/help/news/2026-11-13-hilfe.de.md': news('de', {}, '[x](javascript:alert(1))'),
      },
      /Link "javascript:alert\(1" ist nicht erlaubt/,
    ],
    [
      'Text fehlt',
      { ...newsFiles, '/src/help/news/2026-11-13-hilfe.de.md': news('de', {}, '') },
      /Text fehlt/,
    ],
  ]

  it.each(cases)('%s wird rot', (_name, files, expected) => {
    const index = buildHelpIndex(files)
    expect(index.errors.join('\n')).toMatch(expected)
  })

  it('lässt ungültige Einträge aus dem Index heraus', () => {
    const index = buildHelpIndex({
      ...newsFiles,
      '/src/help/news/2026-11-13-hilfe.de.md': news('de', { type: 'fix' }),
    })
    expect(newsFor(index, 'de').map((n) => n.slug)).toEqual(['2026-10-02-start'])
  })
})

describe('safeHelpHref', () => {
  it.each([
    ['https://who2be.de', 'https://who2be.de'],
    ['/help/persona#felder', '/help/persona#felder'],
    ['#felder', '#felder'],
    ['javascript:alert(1)', null],
    ['data:text/html,x', null],
    ['//evil.example', null],
    ['mailto:a@b.de', null],
    ['', null],
  ])('%s → %s', (input, expected) => {
    expect(safeHelpHref(input)).toBe(expected)
  })
})

describe('searchHelp', () => {
  const index = buildHelpIndex(validFiles)

  it('findet über Titel, Beschreibung und Text, nur in der Sprache', () => {
    expect(searchHelp(index, 'de', 'persona').map((e) => `${e.slug}.${e.locale}`)).toEqual([
      'persona.de',
    ])
    expect(searchHelp(index, 'de', 'zwei').map((e) => e.slug)).toEqual(['demo'])
    expect(searchHelp(index, 'en', 'identität ton').map((e) => e.slug)).toEqual(['persona'])
  })

  it('verlangt jedes Wort und mindestens zwei Zeichen', () => {
    expect(searchHelp(index, 'de', 'persona unbekannt')).toEqual([])
    expect(searchHelp(index, 'de', 'p')).toEqual([])
  })
})

describe('Hilfsfunktionen', () => {
  it('internalHelpLinks erkennt Seiten- und Tutorial-Links', () => {
    expect(internalHelpLinks('[a](/help/persona#x) [b](/help/tutorials/demo) [c](https://x.y)')).toEqual([
      { slug: 'persona', anchor: 'x' },
      { slug: 'demo', anchor: null },
    ])
  })

  it('toHelpLocale fällt auf de zurück', () => {
    expect(toHelpLocale('en-US')).toBe('en')
    expect(toHelpLocale('fr')).toBe('de')
    expect(toHelpLocale(undefined)).toBe('de')
  })
})
