import type { EntityExport, EntityExportFormat } from '@/api/types'

/**
 * Loest einen Browser-Download fuer einen Einzel-Element-Export aus (Plan
 * 2026-06-05). Muster wie der GDPR-Export in `AccountPage`: Blob →
 * `URL.createObjectURL` → `<a download>`. `json` wird huebsch eingerueckt,
 * `markdown` als Roh-Text geschrieben.
 */
export function downloadExport(
  payload: EntityExport | string,
  format: EntityExportFormat,
  entity: string,
  nameOrId: string,
): void {
  const isMarkdown = format === 'markdown'
  const content =
    typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2)
  const type = isMarkdown ? 'text/markdown' : 'application/json'
  const ext = isMarkdown ? 'md' : 'json'
  const safeName = nameOrId.trim().replace(/[^\w-]+/g, '-').toLowerCase() || 'export'
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `who2be-${entity}-${safeName}.${ext}`
  anchor.click()
  URL.revokeObjectURL(url)
}
