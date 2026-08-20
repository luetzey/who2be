import type { Playbook } from '@/api/types'

/**
 * WP-D3/#393 — clientseitige Gruppierung der Playbooks-Liste.
 *
 * Der Modus kommt als `?group=`-URL-Wert (Anzeige-Praeferenz, kein Filter):
 * `none` = flache Liste, `type` = nach Playbook-Typ, `composite` =
 * Composite vs. Standalone, `tag` = nach Tag (Mehrfach-Tags: ein Playbook
 * erscheint in JEDER seiner Tag-Gruppen). Reine Funktionen — die Page
 * rendert pro Gruppe einen Sektions-Header mit Zaehler.
 */
export type PlaybookGroupMode = 'none' | 'type' | 'composite' | 'tag'

/** Rohen URL-Wert validieren — alles Unbekannte faellt auf `none` zurueck. */
export function parseGroupMode(raw: string): PlaybookGroupMode {
  return raw === 'type' || raw === 'composite' || raw === 'tag' ? raw : 'none'
}

export interface PlaybookGroup {
  /**
   * Stabiler Gruppen-Key: im `type`-Modus der rohe Typ-Wert ('' = ohne Typ),
   * im `composite`-Modus 'composite' | 'standalone', im `tag`-Modus der rohe
   * Tag-Wert ('' = ohne Tag), im `none`-Modus 'all'. Die Page uebersetzt Keys
   * in Anzeige-Labels.
   */
  key: string
  items: Playbook[]
}

export function groupPlaybooks(items: Playbook[], mode: PlaybookGroupMode): PlaybookGroup[] {
  if (mode === 'tag') {
    const buckets = new Map<string, Playbook[]>()
    for (const playbook of items) {
      const tags = playbook.tags.length > 0 ? playbook.tags : ['']
      for (const tag of tags) {
        const bucket = buckets.get(tag)
        if (bucket) {
          bucket.push(playbook)
        } else {
          buckets.set(tag, [playbook])
        }
      }
    }
    // Alphabetisch nach Tag; Playbooks ohne Tag ('') ans Ende.
    return Array.from(buckets.entries())
      .sort(([a], [b]) => {
        if (a === '') return 1
        if (b === '') return -1
        return a.localeCompare(b)
      })
      .map(([key, groupItems]) => ({ key, items: groupItems }))
  }
  if (mode === 'composite') {
    const composite = items.filter((playbook) => playbook.is_composite === true)
    const standalone = items.filter((playbook) => playbook.is_composite !== true)
    return [
      { key: 'composite', items: composite },
      { key: 'standalone', items: standalone },
    ].filter((group) => group.items.length > 0)
  }
  if (mode === 'type') {
    const buckets = new Map<string, Playbook[]>()
    for (const playbook of items) {
      const bucket = buckets.get(playbook.type)
      if (bucket) {
        bucket.push(playbook)
      } else {
        buckets.set(playbook.type, [playbook])
      }
    }
    // Alphabetisch nach Typ; Playbooks ohne Typ (Draft-Zustand '') ans Ende.
    return Array.from(buckets.entries())
      .sort(([a], [b]) => {
        if (a === '') return 1
        if (b === '') return -1
        return a.localeCompare(b)
      })
      .map(([key, groupItems]) => ({ key, items: groupItems }))
  }
  return [{ key: 'all', items }]
}
