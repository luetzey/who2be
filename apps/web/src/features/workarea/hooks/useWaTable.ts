import { useEffect, useState } from 'react'

import type { TableColumn, TableDescription, TableQueryResult } from '@/api/types'
import { useApi } from '@/api/useApi'
import i18n from '@/i18n'

/** Zeilen-Cap der Daten-Vorschau. Ein Mensch scrollt keine 200 Zeilen. */
export const PREVIEW_LIMIT = 50

function describeError(cause: unknown, fallbackKey: string): string {
  return cause instanceof Error ? cause.message : i18n.t(fallbackKey)
}

/**
 * SQL der Daten-Vorschau.
 *
 * Warum die UI hier ueberhaupt SQL baut: der Query-Endpunkt ist der einzige
 * Lesepfad in die Tabellendaten und nimmt ohnehin beliebiges (read-only)
 * SQL entgegen — es gibt keinen "gib mir die letzten N Zeilen"-Endpunkt, an
 * dem hier vorbeizukommen waere.
 *
 * Warum das unbedenklich ist: Tabellenname und Spaltennamen stammen nicht aus
 * Benutzereingabe, sondern aus der Katalog-/describe-Antwort des Servers.
 * Dort sind sie beim Anlegen gegen die Identifier-Allowlist validiert
 * (`^[a-z][a-z0-9_]*$`, siehe `tablestore/schema.py`) — kein Quote-Zeichen,
 * kein Whitespace, kein Unicode-Trick moeglich. Die UI setzt sie nur noch in
 * doppelte Anfuehrungszeichen. Serverseitig laeuft die Query zusaetzlich
 * read-only (`mode=ro` + `query_only` + Opcode-Allowlist).
 *
 * Warum kein `SELECT *`: das zoege die internen Store-Spalten
 * (`_dedupe_hash`, `_source_artifact`) in die Ansicht — dieselbe Ueberlegung,
 * aus der der Export serverseitig explizit selektiert. `occurred_at` ist
 * Pflicht-Systemspalte jeder Tabelle, die Sortierung ist damit fachlich und
 * nicht Insert-Reihenfolge.
 */
export function buildPreviewSql(tableName: string, columns: TableColumn[]): string {
  const selectList = columns.map((column) => `"${column.name}"`).join(', ')
  return `SELECT ${selectList} FROM "${tableName}" ORDER BY "occurred_at" DESC`
}

export interface UseWaTableResult {
  description: TableDescription | null
  preview: TableQueryResult | null
  loading: boolean
  error: string | null
  previewLoading: boolean
  previewError: string | null
}

/**
 * Schema + Daten-Vorschau einer Tabelle.
 *
 * Zwei getrennte Ladepfade, weil sie unterschiedlich scheitern duerfen: ein
 * kaputtes describe macht die Seite unbrauchbar, eine abgelehnte Query (408
 * Zeitbudget, 413 Ergebnisgroesse, 400 SQL) nicht — dann bleiben Schema und
 * Konventionen lesbar und nur die Vorschau traegt den Serverhinweis.
 *
 * `tableName` kommt aus dem Katalog (`useWaTables`), nicht aus describe. Ohne
 * ihn gibt es keine FROM-Klausel, also laeuft die Vorschau erst, wenn er da
 * ist — der describe-Aufruf haengt bewusst NICHT am Namen, sonst liefe er ein
 * zweites Mal, sobald der Katalog nachlaedt.
 */
export function useWaTable(tableId: string, tableName: string | null): UseWaTableResult {
  const api = useApi()
  const [description, setDescription] = useState<TableDescription | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<TableQueryResult | null>(null)
  const [previewLoading, setPreviewLoading] = useState(true)
  const [previewError, setPreviewError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .describeWaTable(tableId)
      .then((described) => {
        if (!cancelled) setDescription(described)
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(describeError(cause, 'workarea:tables.loadError'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [api, tableId])

  const columns = description?.schema.columns ?? null
  useEffect(() => {
    if (tableName === null || columns === null) return
    let cancelled = false
    setPreviewLoading(true)
    setPreviewError(null)
    api
      .queryWaTable(tableId, {
        sql: buildPreviewSql(tableName, columns),
        format: 'json',
        limit: PREVIEW_LIMIT,
      })
      .then((result) => {
        if (!cancelled) setPreview(result)
      })
      .catch((cause: unknown) => {
        if (!cancelled) setPreviewError(describeError(cause, 'workarea:tables.previewError'))
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [api, tableId, tableName, columns])

  return { description, preview, loading, error, previewLoading, previewError }
}
