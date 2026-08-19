import { ChevronDown, Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { EntityExport, EntityExportFormat } from '@/api/types'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { downloadExport } from '@/lib/download'
import { notify } from '@/lib/feedback'

interface EntityExportButtonProps {
  /** Entity-Segment fuer den Datei-Namen (`who2be-{entityKind}-{name}.{ext}`),
   * exakt die heutigen Ist-Werte je Feature: 'persona' / 'playbook' /
   * 'resource' / 'external-tool'. */
  entityKind: string
  /** Anzeigename der Entitaet (Aufrufer uebergibt bereits den Fallback auf die
   * ID, falls der Name leer ist — Muster `persona.name || persona.id`). */
  name: string
  /** Laedt den Export-Payload fuer das gewaehlte Format vom Backend. */
  onExport: (format: EntityExportFormat) => Promise<EntityExport | string>
  /** Praefix fuer die `data-testid`-Werte (`${testIdPrefix}-trigger` / `-json` / `-markdown`). */
  testIdPrefix: string
}

/**
 * Generischer Export-Button (Dropdown JSON/Markdown) fuer eine versionierte
 * Entitaet, loest einen Browser-Download aus (Plan 2026-06-05, Muster
 * `AccountPage`-DataExport). Export ist Lesen — auch Viewer duerfen exportieren.
 */
export function EntityExportButton({
  entityKind,
  name,
  onExport,
  testIdPrefix,
}: EntityExportButtonProps) {
  const { t } = useTranslation('common')
  const [busy, setBusy] = useState(false)

  const handleExport = async (format: EntityExportFormat) => {
    setBusy(true)
    try {
      const payload = await onExport(format)
      downloadExport(payload, format, entityKind, name)
      notify.success(t('entityExport.success'))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('entityExport.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={busy}
          data-testid={`${testIdPrefix}-trigger`}
        >
          <Download className="h-4 w-4" />
          {t('entityExport.label')}
          <ChevronDown className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onSelect={() => void handleExport('json')}
          data-testid={`${testIdPrefix}-json`}
        >
          {t('entityExport.json')}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => void handleExport('markdown')}
          data-testid={`${testIdPrefix}-markdown`}
        >
          {t('entityExport.markdown')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
