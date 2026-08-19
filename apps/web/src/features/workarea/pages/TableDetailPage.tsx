import { ChevronDown, Download, Table2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useParams } from 'react-router-dom'

import type { TableExportFormat } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { MetaPill } from '@/components/data/MetaPill'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { downloadFile } from '@/lib/download'
import { notify } from '@/lib/feedback'

import { PREVIEW_LIMIT, useWaTable } from '../hooks/useWaTable'
import { useWaTables } from '../hooks/useWaTables'

// Dateinamens-Sanitizing wie in `downloadExport` — der Tabellenname geht in
// einen Dateinamen ein, nicht in einen Pfad, und bleibt ASCII-konservativ.
function safeFileName(name: string): string {
  return name.trim().replace(/[^\w-]+/g, '-').toLowerCase() || 'export'
}

/**
 * Eine Tabelle des Arbeitsbereichs: Schema, Quell-Konventionen, Daten-Vorschau
 * und Export (ADR-0049).
 *
 * Bewusst read-only — kein Bearbeiten, kein Loeschen, kein `variant="brand"`.
 * Geschrieben wird ueber MCP (`create_table`/`insert_rows`); die Web-Ansicht
 * ist der Nachvollzug fuer den Menschen, nicht ein zweiter Schreibpfad.
 */
export function TableDetailPage() {
  const { t } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  const api = useApi()
  const { areaId, tableId } = useParams<{ areaId: string; tableId: string }>()
  const [busy, setBusy] = useState(false)

  // Der Katalog der Area ist die einzige Quelle des Tabellen-NAMENS (describe
  // liefert ihn nicht) — und er ist ohnehin sichtbarkeits-gefiltert, eine
  // fremde Tabelle taucht darin schlicht nicht auf.
  const { tables, loading: catalogLoading, error: catalogError } = useWaTables(areaId ?? '')
  const table = tables.find((candidate) => candidate.id === tableId) ?? null
  const { description, preview, loading, error, previewLoading, previewError } = useWaTable(
    tableId ?? '',
    table?.name ?? null,
  )

  if (areaId === undefined || tableId === undefined) {
    return <Navigate to={wsPath('/workarea')} replace />
  }

  const onExport = async (format: TableExportFormat) => {
    if (table === null) return
    setBusy(true)
    try {
      const blob = await api.exportWaTable(table.id, format)
      downloadFile(blob, `who2be-table-${safeFileName(table.name)}.${format}`)
      notify.success(t('tables.exportSuccess'))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('tables.exportError'))
    } finally {
      setBusy(false)
    }
  }

  const rows = preview?.rows ?? []

  return (
    <Container>
      <DataView
        loading={(catalogLoading && table === null) || (loading && description === null)}
        error={catalogError ?? error}
        empty={!catalogLoading && table === null}
        emptyTitle={t('tables.notFound')}
      >
        {table !== null && description !== null ? (
          <Stack gap="lg">
            <DetailHeader
              backHref={wsPath(`/workarea/areas/${areaId}`)}
              backLabel={t('tables.back')}
              icon={Table2}
              iconTone="catalog"
              title={table.name}
              actions={
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy}
                      data-testid="export-table-trigger"
                    >
                      <Download className="h-4 w-4" />
                      {t('tables.export')}
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem
                      onSelect={() => void onExport('csv')}
                      data-testid="export-table-csv"
                    >
                      {t('tables.exportCsv')}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onSelect={() => void onExport('xlsx')}
                      data-testid="export-table-xlsx"
                    >
                      {t('tables.exportXlsx')}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              }
            />

            <Card>
              <CardHeader>
                <CardTitle>{t('tables.schemaTitle')}</CardTitle>
                <CardDescription>{t('tables.schemaDescription')}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <div className="flex flex-wrap gap-2">
                  <MetaPill tone="date">
                    {t('tables.rowCount', { rows: description.row_count })}
                  </MetaPill>
                  {description.schema.match_column !== null ? (
                    <MetaPill tone="muted">
                      {t('tables.matchColumn', { column: description.schema.match_column })}
                    </MetaPill>
                  ) : null}
                  {description.schema.category_column !== null ? (
                    <MetaPill tone="muted">
                      {t('tables.categoryColumn', {
                        column: description.schema.category_column,
                      })}
                    </MetaPill>
                  ) : null}
                </div>
                <Table aria-label={t('tables.schemaTitle')}>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('tables.schemaColumn')}</TableHead>
                      <TableHead>{t('tables.schemaType')}</TableHead>
                      <TableHead>{t('tables.schemaNullable')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {description.schema.columns.map((column) => (
                      <TableRow key={column.name}>
                        <TableCell className="font-medium">{column.name}</TableCell>
                        <TableCell>{column.type}</TableCell>
                        <TableCell>
                          {column.nullable ? t('tables.nullableYes') : t('tables.nullableNo')}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            {description.conventions.length > 0 ? (
              <Card>
                <CardHeader>
                  <CardTitle>{t('tables.conventionsTitle')}</CardTitle>
                  <CardDescription>{t('tables.conventionsDescription')}</CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="flex flex-col gap-4">
                    {description.conventions.map((convention) => (
                      <div key={convention.id} className="flex flex-col gap-2">
                        <dt className="text-sm font-medium">{convention.source_name}</dt>
                        <dd className="flex flex-wrap gap-2">
                          {Object.entries(convention.convention).map(([key, value]) => (
                            <MetaPill key={key} tone="muted">
                              {key}: {formatCell(value, t('tables.cellNull'))}
                            </MetaPill>
                          ))}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader>
                <CardTitle>{t('tables.previewTitle')}</CardTitle>
                <CardDescription>
                  {t('tables.previewNote', {
                    limit: PREVIEW_LIMIT,
                    total: description.row_count,
                  })}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <DataView
                  loading={previewLoading}
                  error={previewError}
                  empty={rows.length === 0}
                  emptyTitle={t('tables.previewEmpty')}
                >
                  {/* Der horizontale Scroll steckt im `Table`-Primitive
                      (`overflow-auto`-Wrapper) — breite Tabellen scrollen in
                      sich, die Seite selbst nie. */}
                  <Table aria-label={t('tables.previewTitle')}>
                    <TableHeader>
                      <TableRow>
                        {(preview?.columns ?? []).map((column) => (
                          <TableHead key={column}>{column}</TableHead>
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((row, rowIndex) => (
                        // Die Vorschau hat keinen Zeilen-Schluessel: der Store
                        // gibt bewusst keine rowid heraus. Der Index ist hier
                        // stabil, weil die Liste nur komplett ersetzt wird.
                        <TableRow key={rowIndex}>
                          {row.map((cell, cellIndex) => (
                            <TableCell key={cellIndex} className="whitespace-nowrap">
                              {formatCell(cell, t('tables.cellNull'))}
                            </TableCell>
                          ))}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </DataView>
                {preview?.truncated === true ? (
                  <p className="text-xs text-muted-foreground">{t('tables.previewTruncated')}</p>
                ) : null}
              </CardContent>
            </Card>
          </Stack>
        ) : null}
      </DataView>
    </Container>
  )
}

// Zellwerte kommen als `unknown` (SQLite-Typaffinitaet) — Datum/Zahl/Text
// bleiben unformatiert stehen, weil die Quell-Konvention (siehe
// `conventions`) bestimmt, wie sie zu lesen sind. Eine UI-seitige
// Lokalisierung wuerde genau diese Angabe ueberschreiben.
function formatCell(value: unknown, nullLabel: string): string {
  if (value === null || value === undefined) return nullLabel
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}
