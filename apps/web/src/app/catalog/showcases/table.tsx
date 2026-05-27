import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

import { ShowcaseRow, ShowcaseSection } from '../ShowcaseSection'

interface Row {
  name: string
  version: string
  status: 'active' | 'draft' | 'revoked'
}

const ROWS: readonly Row[] = [
  { name: 'backend-reviewer', version: 'v1.2.0', status: 'active' },
  { name: 'frontend-reviewer', version: 'v0.4.0', status: 'draft' },
  { name: 'legacy-bot', version: 'v0.1.0', status: 'revoked' },
]

const STATUS_VARIANT: Record<Row['status'], 'default' | 'secondary' | 'destructive'> = {
  active: 'default',
  draft: 'secondary',
  revoked: 'destructive',
}

export function TableShowcase() {
  return (
    <ShowcaseSection
      id="table"
      title="Table"
      description="Tabellarische Daten. Slots: TableHeader/TableRow/TableHead, TableBody/TableRow/TableCell."
    >
      <ShowcaseRow>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Version</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {ROWS.map((row) => (
              <TableRow key={row.name}>
                <TableCell className="font-medium">{row.name}</TableCell>
                <TableCell>{row.version}</TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[row.status]}>{row.status}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ShowcaseRow>
    </ShowcaseSection>
  )
}
