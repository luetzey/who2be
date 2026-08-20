import type { Resource } from '@/api/types'

/**
 * #393 — clientseitige Gruppierung der Resources-Liste, analog zu
 * `features/playbooks/lib/grouping.ts`.
 *
 * Der Modus kommt als `?group=`-URL-Wert (Anzeige-Praeferenz, kein Filter):
 * `none` = flache Liste, `tag` = nach Tag (Mehrfach-Tags: eine Resource
 * erscheint in JEDER ihrer Tag-Gruppen; Resources ohne Tag landen in einer
 * „Ohne Tag"-Gruppe). Reine Funktionen — die Page rendert pro Gruppe einen
 * Sektions-Header mit Zaehler.
 */
export type ResourceGroupMode = 'none' | 'tag'

/** Rohen URL-Wert validieren — alles Unbekannte faellt auf `none` zurueck. */
export function parseGroupMode(raw: string): ResourceGroupMode {
  return raw === 'tag' ? raw : 'none'
}

export interface ResourceGroup {
  /**
   * Stabiler Gruppen-Key: im `tag`-Modus der rohe Tag-Wert ('' = ohne Tag),
   * im `none`-Modus 'all'. Die Page uebersetzt Keys in Anzeige-Labels.
   */
  key: string
  items: Resource[]
}

export function groupResources(items: Resource[], mode: ResourceGroupMode): ResourceGroup[] {
  if (mode === 'tag') {
    const buckets = new Map<string, Resource[]>()
    for (const resource of items) {
      const tags = resource.content.tags ?? []
      const bucketTags = tags.length > 0 ? tags : ['']
      for (const tag of bucketTags) {
        const bucket = buckets.get(tag)
        if (bucket) {
          bucket.push(resource)
        } else {
          buckets.set(tag, [resource])
        }
      }
    }
    // Alphabetisch nach Tag; Resources ohne Tag ('') ans Ende.
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
