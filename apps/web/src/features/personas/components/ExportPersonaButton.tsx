import { ChevronDown, Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { EntityExportFormat, Persona } from '@/api/types'
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

interface ExportPersonaButtonProps {
  persona: Persona
}

/**
 * Exportiert eine Persona als JSON oder Markdown und loest einen Browser-Download
 * aus (Plan 2026-06-05, Muster `AccountPage`-DataExport). Export ist Lesen —
 * auch Viewer duerfen exportieren.
 */
export function ExportPersonaButton({ persona }: ExportPersonaButtonProps) {
  const { t } = useTranslation('personas')
  const api = useApi()
  const [busy, setBusy] = useState(false)

  const onExport = async (format: EntityExportFormat) => {
    setBusy(true)
    try {
      const payload = await api.exportPersona(persona.id, format)
      downloadExport(payload, format, 'persona', persona.name || persona.id)
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
        <Button type="button" variant="outline" disabled={busy} data-testid="export-persona-trigger">
          <Download className="h-4 w-4" />
          {t('export.label')}
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onSelect={() => void onExport('json')}
          data-testid="export-persona-json"
        >
          {t('export.json')}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => void onExport('markdown')}
          data-testid="export-persona-markdown"
        >
          {t('export.markdown')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
