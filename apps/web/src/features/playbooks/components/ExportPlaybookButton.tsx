import { ChevronDown, Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { EntityExportFormat, Playbook } from '@/api/types'
import { useApi } from '@/api/useApi'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { downloadExport } from '@/lib/download'
import { notify } from '@/lib/feedback'

interface ExportPlaybookButtonProps {
  playbook: Playbook
}

/**
 * Exportiert ein Playbook als JSON oder Markdown und loest einen Browser-Download
 * aus (Plan 2026-06-05, Muster `AccountPage`-DataExport). Export ist Lesen —
 * auch Viewer duerfen exportieren.
 */
export function ExportPlaybookButton({ playbook }: ExportPlaybookButtonProps) {
  const { t } = useTranslation('playbooks')
  const api = useApi()
  const [busy, setBusy] = useState(false)

  const onExport = async (format: EntityExportFormat) => {
    setBusy(true)
    try {
      const payload = await api.exportPlaybook(playbook.id, format)
      downloadExport(payload, format, 'playbook', playbook.name || playbook.id)
      notify.success(t('export.success'))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('export.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button type="button" variant="outline" disabled={busy} data-testid="export-playbook-trigger">
          <Download className="h-4 w-4" />
          {t('export.label')}
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onSelect={() => void onExport('json')}
          data-testid="export-playbook-json"
        >
          {t('export.json')}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => void onExport('markdown')}
          data-testid="export-playbook-markdown"
        >
          {t('export.markdown')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
