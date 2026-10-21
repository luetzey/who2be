import { useCallback, useEffect, useRef, useState } from 'react'

import { type Api, subscribeApiMutations } from '@/api/client'
import type { InboxCounts } from '@/api/types'
import { useApi } from '@/api/useApi'

/**
 * Entprellung nach eigenen Schreibanfragen: eine Aktion loest oft mehrere
 * Requests aus (z. B. Stapel-Freigabe plus Nachladen), gezaehlt wird einmal.
 */
export const INBOX_MUTATION_DEBOUNCE_MS = 300

export interface InboxCountsState {
  /** `null`, solange nichts geladen ist oder die Zahl nicht ladbar war. */
  counts: InboxCounts | null
  /** `true` nur, wenn der letzte Abruf fuer diesen Schluessel scheiterte. */
  failed: boolean
  /** Sofort neu zaehlen (z. B. nach einer Aktion ausserhalb des API-Clients). */
  reload: () => void
}

interface Result {
  api: Api
  agentId: string | undefined
  counts: InboxCounts | null
  failed: boolean
}

/**
 * Aufgaben-Zaehler (Navigation & Transparenz W1, Spec §2.3/§2.5/§3.1): EINE
 * Quelle fuer Glocke, Dashboard-Zeile und Agent-Ueberblick — drei Orte, eine
 * Zahl. Ohne `agentId` workspace-weit, mit `agentId` fuer einen Agenten.
 *
 * Aktualisierung nach Weiche N5 a, ausdruecklich ohne Polling:
 * - beim Laden (Mount) und bei Workspace-/Token-Wechsel (neues `api`),
 * - bei Rueckkehr in den Tab (`visibilitychange` → sichtbar),
 * - nach jeder eigenen erfolgreichen Schreibanfrage ueber den API-Client
 *   (`subscribeApiMutations`, entprellt) — so erledigt jede Aktion, die eine
 *   Art abschliesst, ihre Zahl mit, ohne dass die Fachseite davon weiss.
 *
 * Laden und Fehler liefern `counts: null` — die Glocke zeigt dann keinen
 * Zaehler statt einer falschen „0“. Ein Nachladen behaelt die alte Zahl, bis
 * die neue da ist (kein Flackern); ein Ergebnis fuer einen anderen Workspace
 * oder Agenten gilt nie.
 */
export function useInboxCounts(agentId?: string): InboxCountsState {
  const api = useApi()
  const [result, setResult] = useState<Result | null>(null)
  // Laufende Anfragen werden ueber eine fortlaufende Nummer verworfen, wenn
  // eine juengere gestartet wurde (Antworten koennen sich ueberholen).
  const seq = useRef(0)

  const load = useCallback(() => {
    const current = ++seq.current
    // Ueber `Promise.resolve().then` statt direkt: auch ein synchroner Wurf
    // beim Anfragebau landet im Fehlerzweig (Glocke ohne Zaehler) und reisst
    // nie die Kopfleiste mit, und die Zaehlung reiht sich hinter die
    // Anfragen der Seite ein, die im selben Commit starten.
    Promise.resolve()
      .then(() => api.getInboxCounts(agentId))
      .then((counts) => {
        if (current === seq.current) setResult({ api, agentId, counts, failed: false })
      })
      .catch(() => {
        if (current === seq.current) setResult({ api, agentId, counts: null, failed: true })
      })
  }, [api, agentId])

  useEffect(() => {
    // Ref-Objekt lokal halten: der Abbau zaehlt dieselbe Folge weiter.
    const counter = seq
    load()
    const onVisibility = () => {
      if (document.visibilityState === 'visible') load()
    }
    let timer: ReturnType<typeof setTimeout> | undefined
    const unsubscribe = subscribeApiMutations(() => {
      clearTimeout(timer)
      timer = setTimeout(load, INBOX_MUTATION_DEBOUNCE_MS)
    })
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      // Antworten nach dem Abbau (oder nach einem Schluesselwechsel) nicht
      // mehr uebernehmen.
      counter.current++
      clearTimeout(timer)
      unsubscribe()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [load])

  const fresh = result !== null && result.api === api && result.agentId === agentId
  return {
    counts: fresh ? result.counts : null,
    failed: fresh ? result.failed : false,
    reload: load,
  }
}
