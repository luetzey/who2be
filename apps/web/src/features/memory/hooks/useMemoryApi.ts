import { useCallback, useEffect, useMemo, useState } from 'react'

import { ApiError } from '@/api/client'
import type {
  Agent,
  MemoryBatchItemResult,
  MemoryFilter,
  MemoryProposalRead,
  MemoryRead,
} from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useSession } from '@/auth/session-context'

// Seitengroesse der Warteschlange (Spec S1′ „Viele“: 50 je Seite).
export const QUEUE_PAGE_SIZE = 50
// Zurueckgehaltene laedt die Seite immer vollstaendig zuerst — bis zu dieser
// Grenze; darueber nennt sie die Restmenge und bietet den Agent-Filter an.
export const HELD_LOAD_LIMIT = 200
// Stapel-Obergrenze des Servers (`ids` hoechstens 100) und der Auswahl.
export const SELECTION_LIMIT = 100
// Obergrenze Nutzergedaechtnis ist 500 (ADR 6.4) = 10 Seiten zu 50.
const MY_MEMORY_PAGES = 10

export interface QueueFilters {
  q: string
  agentId: string
}

/** Ein Vorschlag samt dem Fakt, auf den er zielt (fuer den Wort-Diff). */
export interface ProposalWithTarget {
  proposal: MemoryProposalRead
  // `null`, wenn der Ziel-Eintrag nicht ladbar war — dann zeigt die Zeile den
  // neuen Text ohne Diff.
  currentFact: string | null
  // Wo das Ziel gefunden wurde: im eigenen Nutzergedaechtnis (`user`), im
  // Agentengedaechtnis (`agent`) oder gar nicht (`null`). Bestimmt die Gruppe.
  targetScope: 'user' | 'agent' | null
}

export interface ApprovalQueueData {
  held: MemoryRead[]
  heldTotal: number | null
  items: MemoryRead[]
  hasMore: boolean
  loadingMore: boolean
  loadMore: () => void
  proposals: ProposalWithTarget[]
  // Zahl der nicht zurueckgehaltenen neuen Eintraege je Gruppe (Server-Zaehler,
  // nicht die geladene Teilmenge). Schluessel `mine` bzw. Agent-ID.
  groupCounts: Record<string, number>
  agents: Agent[]
  loading: boolean
  error: ApiError | Error | null
  reload: () => void
  canManageAgents: boolean
  userId: string | null
}

export const MINE_GROUP = 'mine'

function toError(cause: unknown): Error {
  return cause instanceof Error ? cause : new Error(String(cause))
}

/**
 * Nur Zeilen, die die Person sehen darf. Der Server liefert fremdes
 * Nutzergedaechtnis nie (ADR-0053 3.1.1, auch nicht an admin); der Client
 * verwirft es trotzdem, falls es doch einmal in der Antwort steckt — die
 * Oberflaeche zeigt fremde Inhalte unter keinen Umstaenden an.
 */
export function visibleToMe(memory: MemoryRead, userId: string | null): boolean {
  if (memory.scope !== 'user') return true
  return userId !== null && memory.subject_user_id === userId
}

/** Lernvorschlaege stehen nie in der Warteschlange (Delta S1). */
function isQueueEntry(memory: MemoryRead): boolean {
  return memory.kind !== 'lesson'
}

/** Gruppenschluessel einer Zeile: eigenes Nutzergedaechtnis oder Agent. */
export function groupKeyOf(memory: MemoryRead): string {
  if (memory.scope === 'user') return MINE_GROUP
  return memory.agent_id ?? memory.created_by_agent_id ?? ''
}

function matchesQuery(proposal: ProposalWithTarget, q: string): boolean {
  if (q === '') return true
  const needle = q.toLocaleLowerCase()
  return [proposal.proposal.new_fact, proposal.proposal.reason, proposal.currentFact].some(
    (value) => value?.toLocaleLowerCase().includes(needle) ?? false,
  )
}

/**
 * Daten der Warteschlange „Zur Freigabe“ (Spec S1′): zurueckgehaltene oben
 * (bis 200), neue Eintraege seitenweise (Cursor), offene Vorschlaege und die
 * Gruppenzaehler. Viewer sehen nur das eigene Nutzergedaechtnis — der Hook
 * fragt fuer sie ausschliesslich `scope=user` an.
 */
export function useApprovalQueue({ q, agentId }: QueueFilters): ApprovalQueueData {
  const api = useApi()
  const role = useCurrentWorkspaceRole()
  const { me } = useSession()
  const userId = me?.user_id ?? null
  // editor+ (Muster AgentMemorySection): Agentengedaechtnis und alle Agenten.
  const canManageAgents = role !== null && role !== 'viewer'

  const [held, setHeld] = useState<MemoryRead[]>([])
  const [heldTotal, setHeldTotal] = useState<number | null>(null)
  const [items, setItems] = useState<MemoryRead[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [proposals, setProposals] = useState<ProposalWithTarget[]>([])
  const [groupCounts, setGroupCounts] = useState<Record<string, number>>({})
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<ApiError | Error | null>(null)
  const [nonce, setNonce] = useState(0)

  const baseFilter = useMemo<MemoryFilter>(() => {
    const filter: MemoryFilter = { status: 'pending' }
    if (q !== '') filter.q = q
    if (!canManageAgents) {
      filter.scope = 'user'
    } else if (agentId !== '') {
      filter.agent_id = agentId
    }
    return filter
  }, [q, agentId, canManageAgents])

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        // Zurueckgehaltene seitenweise (bis HELD_LOAD_LIMIT) — parallel zum
        // Rest, nicht davor (die Seiten selbst haengen am Cursor).
        const loadHeld = async (): Promise<MemoryRead[]> => {
          const rows: MemoryRead[] = []
          let heldCursor: string | undefined
          do {
            const page = await api.listMemories(
              { ...baseFilter, held: true },
              { limit: QUEUE_PAGE_SIZE, cursor: heldCursor },
            )
            rows.push(...page.items)
            heldCursor = page.next_cursor ?? undefined
          } while (heldCursor !== undefined && rows.length < HELD_LOAD_LIMIT)
          return rows
        }

        const [heldRows, firstPage, heldCount, mineCount, agentCount, proposalRows, agentRows] =
          await Promise.all([
            loadHeld(),
            api.listMemories({ ...baseFilter, held: false }, { limit: QUEUE_PAGE_SIZE }),
            api.countMemories({ ...baseFilter, held: true }),
            agentId === '' || !canManageAgents
              ? api.countMemories({ ...baseFilter, held: false, scope: 'user' })
              : Promise.resolve(null),
            canManageAgents
              ? api.countMemories({ ...baseFilter, held: false, scope: 'agent' }, ['agent'])
              : Promise.resolve(null),
            api.listMemoryProposals({
              status: 'pending',
              agent_id: canManageAgents && agentId !== '' ? agentId : undefined,
            }),
            canManageAgents ? api.listAgents() : Promise.resolve([] as Agent[]),
          ])

        // Fakt vorher je Vorschlag, getrennt nach Fundort: Ein Vorschlag kann
        // aufs Agentengedaechtnis (`propose`) ODER aufs eigene
        // Nutzergedaechtnis der Person zielen — das Ziel entscheidet die
        // Gruppe, nicht `agent_id`. Fehlschlaege kosten nur den Diff.
        //
        // Bekannte Grenze (bis L5, workspace-weite Vorschlaege mit Ziel-Fakt):
        // je Agent mit offenem Vorschlag wird die ganze Legacy-Liste
        // `/agents/{id}/memories` ohne Paging geladen. Bei vielen Agenten oder
        // Eintraegen ist das teuer; L5 ersetzt diesen Umweg.
        const agentFacts = new Map<string, string>()
        const userFacts = new Map<string, string>()
        const agentIds = canManageAgents
          ? [...new Set(proposalRows.map((proposal) => proposal.agent_id))]
          : []
        const sources = await Promise.allSettled(
          agentIds.map((id) => api.listAgentMemories(id)),
        )
        for (const source of sources) {
          if (source.status !== 'fulfilled' || !Array.isArray(source.value)) continue
          for (const memory of source.value) {
            // Die Legacy-Liste kann Nutzergedaechtnis enthalten; das zaehlt
            // nicht als Agentenziel.
            if (memory.scope === 'user') continue
            agentFacts.set(memory.id, memory.fact)
          }
        }
        // Eigenes Nutzergedaechtnis seitenweise (je 50), bis alle uebrigen
        // Ziele aufgeloest sind — hoechstens MY_MEMORY_PAGES Seiten.
        const missing = new Set(
          proposalRows.map((proposal) => proposal.memory_id).filter((id) => !agentFacts.has(id)),
        )
        let myCursor: string | undefined
        for (let page = 0; missing.size > 0 && page < MY_MEMORY_PAGES; page++) {
          try {
            const result = await api.listMyMemories({ limit: QUEUE_PAGE_SIZE, cursor: myCursor })
            for (const memory of result.items ?? []) {
              userFacts.set(memory.id, memory.fact)
              missing.delete(memory.id)
            }
            if (!result.next_cursor) break
            myCursor = result.next_cursor
          } catch {
            break
          }
        }

        if (cancelled) return
        const counts: Record<string, number> = {}
        if (mineCount !== null) counts[MINE_GROUP] = mineCount.total
        for (const [key, value] of Object.entries(agentCount?.groups?.agent ?? {})) {
          counts[key] = value
        }
        const withTargets = proposalRows
          .filter((proposal) => proposal.status === 'pending')
          .map((proposal): ProposalWithTarget => {
            const userFact = userFacts.get(proposal.memory_id)
            const agentFact = agentFacts.get(proposal.memory_id)
            return {
              proposal,
              currentFact: userFact ?? agentFact ?? null,
              targetScope: userFact !== undefined ? 'user' : agentFact !== undefined ? 'agent' : null,
            }
          })
          .filter((entry) => matchesQuery(entry, q))

        setHeld(heldRows.filter((m) => visibleToMe(m, userId) && isQueueEntry(m)))
        setHeldTotal(heldCount.total)
        setItems(firstPage.items.filter((m) => visibleToMe(m, userId) && isQueueEntry(m)))
        setCursor(firstPage.next_cursor)
        setGroupCounts(counts)
        setProposals(withTargets)
        setAgents(agentRows)
      } catch (cause: unknown) {
        if (!cancelled) setError(toError(cause))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [api, baseFilter, canManageAgents, agentId, q, userId, nonce])

  const loadMore = useCallback(() => {
    if (cursor === null || loadingMore) return
    setLoadingMore(true)
    api
      .listMemories({ ...baseFilter, held: false }, { limit: QUEUE_PAGE_SIZE, cursor })
      .then((page) => {
        setItems((current) => [
          ...current,
          ...page.items.filter((m) => visibleToMe(m, userId) && isQueueEntry(m)),
        ])
        setCursor(page.next_cursor)
      })
      .catch((cause: unknown) => setError(toError(cause)))
      .finally(() => setLoadingMore(false))
  }, [api, baseFilter, cursor, loadingMore, userId])

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  return {
    held,
    heldTotal,
    items,
    hasMore: cursor !== null,
    loadingMore,
    loadMore,
    proposals,
    groupCounts,
    agents,
    loading,
    error,
    reload,
    canManageAgents,
    userId,
  }
}

/** Fehlgeschlagene Eintraege eines Stapels, nach ID. */
export function failuresOf(results: MemoryBatchItemResult[]): Map<string, MemoryBatchItemResult> {
  return new Map(results.filter((result) => !result.ok).map((result) => [result.id, result]))
}

/** Neue Trefferzahl aus 409 `memory_batch_count_mismatch`, sonst `null`. */
export function countMismatchOf(cause: unknown): number | null {
  if (!(cause instanceof ApiError) || cause.status !== 409) return null
  const body = cause.body as { reason?: unknown; params?: { count?: unknown } } | null
  if (body?.reason !== 'memory_batch_count_mismatch') return null
  return typeof body.params?.count === 'number' ? body.params.count : null
}
