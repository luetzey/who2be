import { Table2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { EmptyState } from '@/components/data/EmptyState'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

import { useWaTables } from '../hooks/useWaTables'

interface TableListProps {
  areaId: string
}

/**
 * Tabellen-Katalog eines Arbeitsbereichs (ADR-0049).
 *
 * Read-only ohne Anlege-Aktion: Tabellen entstehen ueber MCP (`create_table`),
 * weil erst der Agent weiss, welches Schema seine Quelle braucht. Ein
 * Anlege-Dialog in der Web-UI wuerde ein Schema erzwingen, bevor es Daten gibt.
 * Deshalb spiegelt der EmptyState hier auch keinen Header-CTA (§9.4) — es gibt
 * bewusst keinen.
 */
export function TableList({ areaId }: TableListProps) {
  const { t, i18n } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  const { tables, loading, error } = useWaTables(areaId)

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">{t('tables.description')}</p>
      {/* Der EmptyState traegt ein Icon, das `DataView` nicht durchreicht —
          deshalb hier als Kind statt ueber `empty`/`emptyTitle`. */}
      <DataView loading={loading} error={error}>
        {tables.length === 0 ? (
          <EmptyState
            icon={Table2}
            title={t('tables.emptyTitle')}
            description={t('tables.emptyDescription')}
          />
        ) : (
          <Table aria-label={t('tables.title')}>
            <TableHeader>
              <TableRow>
                <TableHead>{t('tables.name')}</TableHead>
                <TableHead>{t('tables.columns')}</TableHead>
                <TableHead>{t('tables.created')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tables.map((table) => (
                <TableRow key={table.id}>
                  <TableCell>
                    <Link
                      to={wsPath(`/workarea/areas/${areaId}/tables/${table.id}`)}
                      className="font-medium underline-offset-4 hover:underline"
                    >
                      {table.name}
                    </Link>
                  </TableCell>
                  {/* `row_count` ist im Katalog-Pfad immer `null` (die Zahl
                      liegt in der SQLite-Datei) — die Spaltenzahl ist die
                      Kennzahl, die hier ohne Zusatz-Roundtrip zu haben ist. */}
                  <TableCell>{table.schema.columns.length}</TableCell>
                  <TableCell>
                    {new Date(table.created_at).toLocaleDateString(i18n.language)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DataView>
    </div>
  )
}
