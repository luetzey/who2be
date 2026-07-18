import { ChevronDown, Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { EntityExportFormat, ExternalTool } from '@/api/types'
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

interface ExportToolButtonProps {
  tool: ExternalTool
}

/**
 * Exportiert ein externes Tool als JSON oder Markdown und loest einen
 * Browser-Download aus. Export ist Lesen — auch Viewer duerfen exportieren.
 * Spiegelt `features/resources/components/ExportResourceButton.tsx` 1:1.
 */
export function ExportToolButton({ tool }: ExportToolButtonProps) {
  const { t } = useTranslation('tools')
  const api = useApi()
  const [busy, setBusy] = useState(false)

  const onExport = async (format: EntityExportFormat) => {
    setBusy(true)
    try {
      const payload = await api.exportExternalTool(tool.id, format)
      downloadExport(payload, format, 'external-tool', tool.name || tool.id)
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
        <Button type="button" variant="outline" disabled={busy} data-testid="export-tool-trigger">
          <Download className="h-4 w-4" />
          {t('export.label')}
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onSelect={() => void onExport('json')}
          data-testid="export-tool-json"
        >
          {t('export.json')}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => void onExport('markdown')}
          data-testid="export-tool-markdown"
        >
          {t('export.markdown')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
