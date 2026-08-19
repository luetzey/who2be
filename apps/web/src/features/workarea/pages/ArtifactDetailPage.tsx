import { ChevronDown, Download, FileText, Link2, Printer, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'

import type { ArtifactExportFormat } from '@/api/types'
import { useApi } from '@/api/useApi'
import { useCurrentWorkspaceRole } from '@/auth/useCurrentWorkspaceRole'
import { useWorkspacePath } from '@/auth/useWorkspacePath'
import { DataView } from '@/components/data/DataView'
import { DetailHeader } from '@/components/data/DetailHeader'
import { MetaPill } from '@/components/data/MetaPill'
import { Container } from '@/components/layout/Container'
import { Stack } from '@/components/layout/Stack'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { downloadFile } from '@/lib/download'
import { notify } from '@/lib/feedback'
import { cn } from '@/lib/utils'

import { useArtifact } from '../hooks/useArtifact'
import { useWorkAreaArtifacts } from '../hooks/useWorkAreaArtifacts'
import { buildAnchor, parseAnchoredMarkdown } from '../lib/blocks'

// Dateinamens-Sanitizing wie in `downloadExport` (`lib/download.ts`) bzw.
// `TableDetailPage::safeFileName` — der Titel geht in einen Dateinamen ein,
// nicht in einen Pfad, und bleibt ASCII-konservativ.
function safeFileName(name: string): string {
  return name.trim().replace(/[^\w-]+/g, '-').toLowerCase() || 'export'
}

// `format` ist der Query-Wert des Export-Endpunkts ('markdown'), die
// Dateiendung bleibt die uebliche Kurzform ('.md').
const EXPORT_EXTENSIONS: Record<ArtifactExportFormat, string> = {
  markdown: 'md',
  html: 'html',
}

export function ArtifactDetailPage() {
  const { t } = useTranslation('workarea')
  const wsPath = useWorkspacePath()
  const navigate = useNavigate()
  const location = useLocation()
  const api = useApi()
  const isViewer = useCurrentWorkspaceRole() === 'viewer'
  const { areaId, artifactId } = useParams<{ areaId: string; artifactId: string }>()
  const [exportBusy, setExportBusy] = useState(false)

  const { artifact, loading, error } = useArtifact(artifactId ?? '')
  // Metadaten (Typ, Sensibilitaet, Zeitpunkt, Quelle) liefert nur die
  // Area-Liste — der Inhalts-Endpunkt traegt sie bewusst nicht mit. Deshalb ist
  // der Weg ueber einen Bereich die vollstaendige Ansicht.
  //
  // Es gibt aber auch den bereichslosen Aufruf: ein KB-Beleg der Form
  // `artifact:<uuid>#<block>` kennt die Area nicht, und es gibt keinen
  // Endpunkt, der sie nachschlaegt. Statt den Beleg unverlinkt zu lassen,
  // zeigen wir dann Inhalt + Anker ohne die Metadaten — das ist genau das,
  // wofuer ein Beleg-Link da ist.
  const { artifacts } = useWorkAreaArtifacts(areaId ?? '')
  const meta =
    areaId !== undefined
      ? (artifacts.find((candidate) => candidate.id === artifactId) ?? null)
      : null

  // `#block` in der URL (aus einem Suchtreffer): zum Block springen. Erst wenn
  // der Inhalt da ist — vorher existiert das Ziel-Element noch nicht.
  const fragment = location.hash.replace(/^#/, '')
  useEffect(() => {
    if (artifact === null || fragment === '') return
    const target = document.getElementById(`block-${fragment}`)
    // Nicht jede Umgebung kennt `scrollIntoView` (jsdom etwa nicht). Der Sprung
    // ist Komfort — die Hervorhebung des Blocks traegt die Information und
    // funktioniert auch ohne. Ein harter Aufruf wuerde die Seite ohne Not
    // zerlegen.
    if (typeof target?.scrollIntoView === 'function') {
      target.scrollIntoView({ block: 'center' })
    }
  }, [artifact, fragment])

  if (artifactId === undefined) {
    return <Navigate to={wsPath('/workarea')} replace />
  }
  const backHref = areaId !== undefined ? `/workarea/areas/${areaId}` : '/workarea'

  const blocks = artifact !== null ? parseAnchoredMarkdown(artifact.markdown) : []

  const copyAnchor = async (blockId: string) => {
    const anchor = buildAnchor(artifactId, blockId)
    try {
      await navigator.clipboard.writeText(anchor)
      notify.success(t('artifact.anchorCopied', { anchor }))
    } catch {
      // Ohne Clipboard-Freigabe (oder in unsicherem Kontext) schlaegt das fehl —
      // kein Grund, die Seite zu stoeren, aber sagen muss man es.
      notify.error(t('artifact.anchorCopyFailed'))
    }
  }

  const remove = async () => {
    if (meta !== null && !window.confirm(t('artifact.deleteConfirm', { title: meta.title }))) {
      return
    }
    try {
      await api.deleteWaArtifact(artifactId)
      notify.success(t('artifact.deletedToast'))
      navigate(wsPath(backHref))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('artifact.deleteFailed'))
    }
  }

  // Export ist Lesen — der Dropdown steht auch Viewern offen (kein
  // Rollen-Gate, anders als beim Loeschen).
  const onExport = async (format: ArtifactExportFormat) => {
    if (artifact === null) return
    setExportBusy(true)
    try {
      const blob = await api.exportWaArtifact(artifactId, format)
      const ext = EXPORT_EXTENSIONS[format]
      downloadFile(blob, `who2be-artifact-${safeFileName(artifact.title)}.${ext}`)
      notify.success(t('export.success'))
    } catch (cause: unknown) {
      notify.error(cause instanceof Error ? cause.message : t('export.error'))
    } finally {
      setExportBusy(false)
    }
  }

  // Kein Server-PDF: der Browser-Druckdialog bietet "Als PDF speichern" —
  // das Print-Stylesheet (globals.css) blendet dafuer das App-Chrome aus.
  const onPrint = () => {
    window.print()
  }

  return (
    <Container>
      <DataView loading={loading && artifact === null} error={error}>
        {artifact !== null ? (
          <Stack gap="lg">
            <DetailHeader
              backHref={wsPath(backHref)}
              backLabel={areaId !== undefined ? t('artifact.back') : t('detail.back')}
              icon={FileText}
              iconTone="resource"
              title={artifact.title}
              badges={
                <>
                  <Badge variant="outline">{t('artifact.revision', { rev: artifact.rev })}</Badge>
                  {meta?.sensitivity === 'sensitive' ? (
                    <Badge variant="destructive">{t('artifacts.sensitive')}</Badge>
                  ) : null}
                </>
              }
              actions={
                // `print:hidden` (Tailwind-v4-Variante) statt einer globalen
                // Regel: Loeschen und Export sind Seiten-Aktionen, keine
                // Druck-Inhalte. Das App-Chrome (AppShell/Footer) ist nicht
                // Teil dieser Seite und wird stattdessen in globals.css ueber
                // wenige Element-Selektoren ausgeblendet.
                <div className="flex flex-wrap items-center gap-2 print:hidden">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        variant="outline"
                        disabled={exportBusy}
                        data-testid="export-artifact-trigger"
                      >
                        <Download className="h-4 w-4" />
                        {t('export.label')}
                        <ChevronDown className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onSelect={() => void onExport('markdown')}
                        data-testid="export-artifact-markdown"
                      >
                        {t('export.markdown')}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={() => void onExport('html')}
                        data-testid="export-artifact-html"
                      >
                        {t('export.html')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onSelect={onPrint} data-testid="export-artifact-print">
                        <Printer className="h-4 w-4" />
                        {t('export.printPdf')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button
                    type="button"
                    variant="destructive"
                    disabled={isViewer}
                    title={isViewer ? t('artifact.viewerReadOnly') : undefined}
                    onClick={() => void remove()}
                  >
                    <Trash2 className="h-4 w-4" />
                    {t('artifact.delete')}
                  </Button>
                </div>
              }
            />
            {meta?.source_url !== null && meta?.source_url !== undefined ? (
              <MetaPill tone="muted">{t('artifacts.source', { source: meta.source_url })}</MetaPill>
            ) : null}
            <Card>
              <CardContent className="flex flex-col gap-4 pt-6">
                <p className="text-xs text-muted-foreground">{t('artifact.rawNotice')}</p>
                {blocks.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t('artifact.emptyBody')}</p>
                ) : (
                  <ol className="flex flex-col gap-3">
                    {blocks.map((block, index) => (
                      <li
                        key={block.blockId ?? `unanchored-${index}`}
                        id={block.blockId !== null ? `block-${block.blockId}` : undefined}
                        className={cn(
                          'flex items-start gap-3 rounded-md p-2',
                          // Der aus einem Suchtreffer angesprungene Block wird
                          // hervorgehoben — Rahmen UND Flaeche, damit die
                          // Markierung nicht allein an der Farbe haengt.
                          block.blockId !== null && block.blockId === fragment
                            ? 'bg-brand/10 ring-2 ring-ring'
                            : null,
                        )}
                      >
                        <pre className="min-w-0 flex-1 font-sans text-sm whitespace-pre-wrap">
                          {block.text}
                        </pre>
                        {block.blockId !== null ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="print:hidden"
                            aria-label={t('artifact.anchorCopy')}
                            title={t('artifact.anchorCopy')}
                            onClick={() => void copyAnchor(block.blockId as string)}
                          >
                            <Link2 className="h-4 w-4" />
                          </Button>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                )}
              </CardContent>
            </Card>
          </Stack>
        ) : null}
      </DataView>
    </Container>
  )
}
